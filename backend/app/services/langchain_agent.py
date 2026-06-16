from collections.abc import Iterable
import logging

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
    def __init__(self, kb_tool=None, meal_plan_tool=None, memory_tool=None, member_provider=None):
        self.kb_tool = kb_tool
        self.meal_plan_tool = meal_plan_tool
        self.memory_tool = memory_tool
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
        result = {
            "content": _content_to_text(response_message.content),
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
        }
        logger.info(
            "agent run done output_chars=%s prompt_tokens=%s completion_tokens=%s",
            len(str(result["content"])),
            result["token_prompt"],
            result["token_completion"],
        )
        return result

    def stream(self, messages: list[dict[str, str]]) -> Iterable[str]:
        self._ensure_api_key()
        logger.info("agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            if not _is_visible_assistant_chunk(chunk):
                logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
                continue
            content = getattr(chunk, "content", "")
            text = _content_to_text(content)
            if text:
                yield text
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
