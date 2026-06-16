from collections.abc import Iterable
import json
import logging
from typing import Literal

from app.core.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """你是粮达健康的家庭健康智能营销 Agent。
你的任务是结合家人的健康档案、报告依据和近期状态，生成餐单建议，并在合适时提示可选的商品推荐方向。

要求：
1. 用简体中文回答。
2. 不做诊断，不替代医生。
3. 推荐餐单时必须调用 meal_plan 工具，不要只凭模型自由生成。
4. 用户问具体家人时，识别该家人的 member_id 并调用 meal_plan(scope="member")。
5. 用户问全家、我们家、今晚做什么适合全家时，调用 meal_plan(scope="family")。
6. 只有用户明确要求基于报告、体检结果、某份报告时，才调用 kb_search 工具。
   检索报告时必须显式传入 member_id，不要在不知道是哪位家人的情况下盲猜。
7. 如果引用报告内容，说明来自哪份报告或页码。
8. 回答要简洁、具体、可执行。
9. 当信息不足时，直接说明还缺什么信息。
{members_block}
9a. 【硬性禁止】在面向用户的回复文本中，绝不能出现任何内部标识符，包括但不限于 member_id（mem 开头的字符串、member_id=xxx 形式）、session_id、message_id、user_id、工具返回的原始 ID 字段等。称呼家人一律用姓名或"爸爸/妈妈/女儿/儿子/爷爷/奶奶"等家庭称呼。这些 ID 只能出现在工具调用的参数里，不能出现在用户能看到的任何文字中。
10. 用户问及任何家人的饮食偏好、食物排斥、阶段目标或历史互动时，必须真正执行 memory_search 工具调用（用工具调用语法发起一次 function call），再根据工具返回的搜索结果回答。
    严禁在文本中假装"未检索到相关记忆"或"已查过"而绕过工具调用；如果真的没有命中，再说明暂无记录。
11. 调用 memory_search 时，如果用户明确指向某位家人，必须传入该家人的 member_id；如果用户明确说全家、我们家或家里人，才不传 member_id 以检索家庭级记忆；无法明确归属时不要伪造 member_id。
12. 记忆只能用于个性化表达，不能覆盖过敏、健康禁忌、报告事实和健康安全约束。
13. 跨家人报告对比问题需要分别对每位家人调用 kb_search，然后合成答案。
14. 当用户询问吃什么、早餐、午餐、晚餐、一日三餐或全家共餐时，必须先调用 meal_plan 工具生成餐单。
15. meal_plan 工具返回餐单后，必须把 meal_plan 工具返回的餐单文本原样作为 meal_plan_text 参数继续调用 mall_recommend 工具。
16. mall_recommend 工具的推荐结果会由系统作为商品卡片自动附加到回复上，**不要**把商品名、价格、推荐理由写进自己的文本回复里；只输出餐单和自然的总结文字。如果 mall_recommend 返回 Error，简单说明”暂时无法推荐商品”即可。
17. mall_recommend 的 scope 和 member_id 必须与 meal_plan 保持一致；全家餐单使用 scope=”family”，不传 member_id。
"""


def _build_members_block(members: list) -> str:
    if not members:
        return "8. 当前没有可用家人，无法检索报告。\n"
    lines = ["8. 当前可用家人列表："]
    for index, member in enumerate(members, start=1):
        member_id = member.member_id if hasattr(member, "member_id") else member["member_id"]
        name = member.name if hasattr(member, "name") else member["name"]
        relation = member.relation if hasattr(member, "relation") else member.get("relation", "")
        lines.append(f"   {index}. {name}（member_id={member_id}，{relation}）")
    lines.append('   如果用户问"爸爸"对应到相应的家人，以此类推。')
    lines.append('   如果指代不明（如"他/她"无上下文），必须先反问"您说的\'他/她\'是指哪位家人？"，不要主动猜测。')
    return "\n".join(lines) + "\n"


class LlmConfigError(Exception):
    pass


class LangChainAgentRunner:
    def __init__(
        self,
        kb_tool=None,
        meal_plan_tool=None,
        memory_tool=None,
        mall_recommend_tool=None,
        member_provider=None,
    ):
        self.kb_tool = kb_tool
        self.meal_plan_tool = meal_plan_tool
        self.memory_tool = memory_tool
        self.mall_recommend_tool = mall_recommend_tool
        self.member_provider = member_provider or (lambda: [])

    def _system_prompt(self) -> str:
        members = self.member_provider()
        return SYSTEM_PROMPT_TEMPLATE.format(members_block=_build_members_block(members))

    def _ensure_api_key(self) -> None:
        if not settings.llm_api_key:
            raise LlmConfigError("未配置模型 API Key")

    def _append_kb_context(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        # LLM now drives KB search via the kb_search tool (with explicit member_id).
        # This auto-injection path is retained as a no-op for backward compatibility.
        return messages

    def run(self, messages: list[dict[str, str]]) -> dict[str, object]:
        self._ensure_api_key()
        logger.info("agent run start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        response = agent.invoke({"messages": self._to_langchain_messages(prepared_messages)})
        response_message = response["messages"][-1]
        token_usage = (
            response_message.response_metadata.get("token_usage", {})
            if response_message.response_metadata
            else {}
        )
        product_recs = _extract_product_recommendations(response["messages"])
        result = {
            "content": _content_to_text(response_message.content),
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
            "product_recommendations": product_recs,
        }
        logger.info(
            "agent run done output_chars=%s prompt_tokens=%s completion_tokens=%s item_count=%s",
            len(str(result["content"])),
            result["token_prompt"],
            result["token_completion"],
            len((product_recs or {}).get("items") or []),
        )
        return result

    def stream(self, messages: list[dict[str, str]]) -> Iterable[tuple[Literal["delta", "product_recommendations"], object]]:
        self._ensure_api_key()
        logger.info("agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            # mall_recommend 工具结果以独立结构化事件产出（不在 LLM 文本流里出现）
            payload = _try_parse_mall_recommend_payload(chunk)
            if payload is not None and payload.get("items"):
                logger.info("agent stream emit product_recommendations item_count=%s", len(payload["items"]))
                yield ("product_recommendations", payload)
                continue
            if not _is_visible_assistant_chunk(chunk):
                logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
                continue
            content = getattr(chunk, "content", "")
            text = _content_to_text(content)
            if text:
                yield ("delta", text)
        logger.info("agent stream done")

    def _agent(self):
        from langchain.agents import create_agent

        return create_agent(
            model=self._model(),
            tools=self._tools(),
            system_prompt=self._system_prompt(),
        )

    def _tools(self):
        tools = []

        if self.meal_plan_tool is not None:
            def meal_plan(scope: str, member_id: str | None = None, goal: str | None = None, meal_type: str = "day") -> str:
                """根据单人或全家健康状态生成一日三餐或指定餐次建议。"""
                logger.info(
                    "agent tool call name=meal_plan scope=%s member_id=%s meal_type=%s has_goal=%s",
                    scope,
                    member_id,
                    meal_type,
                    bool(goal),
                )
                return self.meal_plan_tool.build(scope=scope, member_id=member_id, goal=goal, meal_type=meal_type)

            tools.append(meal_plan)

        if self.mall_recommend_tool is not None:
            def mall_recommend(
                scope: str,
                meal_plan_text: str,
                member_id: str | None = None,
                limit: int = 5,
            ) -> str:
                """根据 meal_plan 工具返回的餐单文本和健康画像推荐商城商品。"""
                logger.info(
                    "agent tool call name=mall_recommend scope=%s member_id=%s limit=%s meal_plan_chars=%s",
                    scope,
                    member_id,
                    limit,
                    len(meal_plan_text.strip()),
                )
                return self.mall_recommend_tool.recommend(
                    scope=scope,
                    member_id=member_id,
                    meal_plan_text=meal_plan_text,
                    limit=limit,
                )

            tools.append(mall_recommend)

        if self.memory_tool is not None:
            def memory_search(query: str, member_id: str | None = None, limit: int = 5) -> str:
                """检索家庭或指定家人的长期互动记忆，包括偏好、排斥、阶段目标和营销反馈。"""
                logger.info(
                    "agent tool call name=memory_search member_id=%s limit=%s query_chars=%s",
                    member_id,
                    limit,
                    len(query.strip()),
                )
                return self.memory_tool.search(query=query, member_id=member_id, limit=limit)

            tools.append(memory_search)

        if self.kb_tool is not None:
            def kb_search(query: str, member_id: str, top_k: int = 5) -> str:
                """检索指定家人的健康报告片段。"""
                logger.info(
                    "agent tool call name=kb_search member_id=%s top_k=%s query_chars=%s",
                    member_id,
                    top_k,
                    len(query.strip()),
                )
                return self.kb_tool.search(query=query, member_id=member_id, top_k=top_k)

            tools.append(kb_search)

        return tools

    def _model(self):
        from langchain.chat_models import init_chat_model

        return init_chat_model(
            model=settings.llm_model,
            model_provider="openai",
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )

    def _to_langchain_messages(self, messages: list[dict[str, str]]):
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        result = []
        for message in messages:
            if message["role"] == "assistant":
                result.append(AIMessage(content=message["content"]))
            elif message["role"] == "system":
                result.append(SystemMessage(content=message["content"]))
            else:
                result.append(HumanMessage(content=message["content"]))
        return result


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


def _is_visible_assistant_chunk(chunk) -> bool:
    return chunk.__class__.__name__ == "AIMessageChunk"


def _try_parse_mall_recommend_payload(chunk) -> dict | None:
    """识别 mall_recommend 工具返回的 ToolMessage，解析其 JSON content 为结构化 dict。

    非 mall_recommend 工具 / 解析失败 / 内容不是 JSON / 不含 items 一律返回 None。
    """
    if chunk.__class__.__name__ != "ToolMessage":
        return None
    tool_name = getattr(chunk, "name", None)
    if tool_name != "mall_recommend":
        return None
    raw = getattr(chunk, "content", "")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
        return None
    return parsed


def _extract_product_recommendations(messages) -> dict | None:
    """从 agent.invoke 的完整消息列表中找出 mall_recommend 的工具结果。"""
    for message in messages:
        if message.__class__.__name__ != "ToolMessage":
            continue
        if getattr(message, "name", None) != "mall_recommend":
            continue
        raw = getattr(message, "content", "")
        if not isinstance(raw, str):
            continue
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list) and parsed["items"]:
            return parsed
    return None
