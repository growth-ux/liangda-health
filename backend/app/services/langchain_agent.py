import re
from collections.abc import Iterable
import json
import logging
from typing import Literal

from langchain.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """你是粮达健康的家庭健康智能营销 Agent。
你的任务是结合家人的健康档案、报告依据和近期状态，生成餐单建议，并在合适时提示可选的商品推荐方向。

要求：
1. 用简体中文回答。
2. 不做诊断，不替代医生。
3. 面向普通家庭用户说话，语气像日常健康顾问，不要像医生、病历、论文或专业报告。
4. 回复要短一点、口语一点，优先说用户马上能理解和执行的做法；除非用户追问，不展开复杂医学机制。
5. 少用专业术语和判断性表达。必须提到专业词时，用一句日常话解释。
6. 不要直接说“你可能患有 XXX”。改用“可能和 XXX 有关”“常见原因有 XXX”“只靠描述不好判断”。
7. 一般问题控制在 100-200 字；复杂问题最多分 4 点。不要输出大段分析。
8. 常见回复结构：先回应用户情况，再给 2-3 条简单建议，最后说明什么情况需要线下就医。
9. 推荐餐单时必须调用 meal_plan 工具，不要只凭模型自由生成。
10. 用户问具体家人时，识别该家人的 member_id 并调用 meal_plan(scope="member")。
11. 用户问全家、我们家、今晚做什么适合全家时，调用 meal_plan(scope="family")。
12. 只有用户明确要求基于报告、体检结果、某份报告时，才调用 kb_search 工具。
   检索报告时必须显式传入 member_id，不要在不知道是哪位家人的情况下盲猜。
13. 如果引用报告内容，说明来自哪份报告或页码。
14. 回答要简洁、具体、可执行。
15. 当信息不足时，直接说明还缺什么信息。
{members_block}
16. 【硬性禁止】在面向用户的回复文本中，绝不能出现任何内部标识符，包括但不限于 member_id（mem 开头的字符串、member_id=xxx 形式）、session_id、message_id、user_id、工具返回的原始 ID 字段等。称呼家人一律用姓名或"爸爸/妈妈/女儿/儿子/爷爷/奶奶"等家庭称呼。这些 ID 只能出现在工具调用的参数里，不能出现在用户能看到的任何文字中。
17. 用户问及任何家人的饮食偏好、食物排斥、阶段目标或历史互动时，必须真正执行 memory_search 工具调用（用工具调用语法发起一次 function call），再根据工具返回的搜索结果回答。
    严禁在文本中假装"未检索到相关记忆"或"已查过"而绕过工具调用；如果真的没有命中，再说明暂无记录。
18. 调用 memory_search 时，如果用户明确指向某位家人，必须传入该家人的 member_id；如果用户明确说全家、我们家或家里人，才不传 member_id 以检索家庭级记忆；无法明确归属时不要伪造 member_id。
19. 记忆只能用于个性化表达，不能覆盖过敏、健康禁忌、报告事实和健康安全约束。
20. 跨家人报告对比问题需要分别对每位家人调用 kb_search，然后合成答案。
21. 当用户询问吃什么、早餐、午餐、晚餐、一日三餐或全家共餐时，必须先调用 meal_plan 工具生成餐单。
22. meal_plan 工具返回餐单后，必须把 meal_plan 工具返回的餐单文本原样作为 meal_plan_text 参数继续调用 mall_recommend 工具。
23. mall_recommend 工具的推荐结果会由系统作为商品卡片自动附加到回复上，**不要**把商品名、价格、推荐理由写进自己的文本回复里；只输出餐单和自然的总结文字。如果 mall_recommend 返回 Error，简单说明”暂时无法推荐商品”即可。
24. mall_recommend 的 scope 和 member_id 必须与 meal_plan 保持一致；全家餐单使用 scope=”family”，不传 member_id。
25. **【硬性要求】** Agent 完成一次用户回复必须调用 `respond` 工具，**不能**直接用普通文本对用户说话。`respond` 工具参数：
   - `kind`：5 选 1——`meal_plan`（用户问餐单/三餐/早午晚吃什么）/ `qa`（用户简单问答）/ `greeting`（首问/寒暄）/ `kb_interpretation`（用户问"为什么/要不要紧"且你刚调过 kb_search）/ `general_advice`（其他健康建议）
   - `summary_text`：口语化总结（1-2 句，≤ 400 字），会流式产出给用户
   - `payload`：按 kind 决定的结构化字段（见各 kind 定义）
   各 kind payload 要求：
   - `meal_plan.payload`：`scope` (family/member) / `target_member_name` / `meal_items[]` (slot/title/summary) / `member_adjustments[]` (member_name/note/tags) / `avoid_tags[]` / `extra_note`
   - `qa.payload`：`question_topic` / `answer` / `tips[]`
   - `greeting.payload`：`message` / `suggested_topics[]`
   - `kb_interpretation.payload`：`topic` / `evidence[]` (source/excerpt) / `suggestions[]` (text/priority) / `red_flags[]`
   - `general_advice.payload`：`topic` / `advice` / `cautions[]`
26. 完成工具链（meal_plan / kb_search 等）后，**立即**调用 `respond`，不要再继续说话。
27. 调完 `respond` 后不要再追加任何普通文本。
"""


def _build_members_block(members: list) -> str:
    if not members:
        return "15. 当前没有可用家人，无法检索报告。\n"
    lines = ["15. 当前可用家人列表："]
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


class ResponseSchemaError(Exception):
    pass


@tool
def _respond(
    kind: Literal["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"],
    summary_text: str,
    payload: dict,
) -> str:
    """返回对用户可见的回复。LLM 必须调用本工具才能完成回复——不能直接对用户说话。

    Args:
        kind: 回复类型枚举，meal_plan/qa/greeting/kb_interpretation/general_advice。
        summary_text: 口语化总结（1-2 句，≤ 400 字），会流式输出。
        payload: 按 kind 决定的结构化内容，前端按它渲染卡片。
    """
    return "ok"


# 工具名固定为 "respond"，方便上游按名字识别
_RESPOND_TOOL = _respond.from_function(
    func=_respond.func,
    name="respond",
    description=_respond.description,
    parse_docstring=True,
)


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
        card = _extract_card(response["messages"])
        if card is None:
            logger.warning("agent run no respond tool call in messages; raising")
            raise ResponseSchemaError("LLM 未调用 respond 工具")
        result = {
            "content": card.get("summary_text", ""),
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
            "product_recommendations": product_recs,
            "card": card,
        }
        logger.info(
            "agent run done kind=%s summary_chars=%s prompt_tokens=%s completion_tokens=%s item_count=%s",
            card.get("kind"),
            len(card.get("summary_text", "")),
            result["token_prompt"],
            result["token_completion"],
            len((product_recs or {}).get("items") or []),
        )
        return result

    def stream(self, messages: list[dict[str, str]]) -> Iterable[tuple[Literal["delta", "product_recommendations", "card"], object]]:
        self._ensure_api_key()
        logger.info("agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        respond_done = False
        respond_args_state: dict[str, str] = {}
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            # 1) mall_recommend 工具：JSON 字符串 → 现有 product_recommendations 事件
            payload = _try_parse_mall_recommend_payload(chunk)
            if payload is not None and payload.get("items"):
                logger.info("agent stream emit product_recommendations item_count=%s", len(payload["items"]))
                yield ("product_recommendations", payload)
                continue

            # 2) respond 工具的 ToolMessage → 整体解析为 card 事件
            if chunk.__class__.__name__ == "ToolMessage" and getattr(chunk, "name", None) == "respond":
                card = _parse_respond_payload(chunk) or _parse_respond_payload_from_args_state(
                    respond_args_state,
                    tool_call_id=getattr(chunk, "tool_call_id", None),
                )
                if card is None:
                    raw_content = getattr(chunk, "content", "")
                    logger.warning(
                        "agent stream respond payload invalid; raising. tool_call_id=%s raw_content=%r args_state_keys=%s",
                        getattr(chunk, "tool_call_id", None),
                        raw_content[:500] if isinstance(raw_content, str) else str(raw_content)[:500],
                        list(respond_args_state.keys()),
                    )
                    raise ResponseSchemaError("respond 工具参数不符合 StructuredResponse schema")
                respond_done = True
                logger.info("agent stream emit card kind=%s", card.get("kind"))
                yield ("card", card)
                return

            # 3) AIMessageChunk 含 respond 工具的 tool_call_chunk → 提取 summary_text 字段增量
            if chunk.__class__.__name__ == "AIMessageChunk":
                tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
                respond_chunk_text = _extract_respond_summary_text_delta(tool_call_chunks, respond_args_state)
                if respond_chunk_text:
                    yield ("delta", respond_chunk_text)
                # AIMessageChunk.content 文本 → 仅在 respond 未完成时走 delta；否则丢弃 + warn
                if not respond_done:
                    text = _content_to_text(getattr(chunk, "content", ""))
                    if text:
                        yield ("delta", text)
                else:
                    text = _content_to_text(getattr(chunk, "content", ""))
                    if text:
                        logger.warning("agent stream drop post-respond AIMessageChunk chars=%s", len(text))
                continue

            logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
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

        tools.append(_RESPOND_TOOL)

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


def _extract_card(messages) -> dict | None:
    """从 agent.invoke 的完整消息列表中找出 respond 工具的结果并解析。"""
    respond_args_by_id = _extract_respond_tool_call_args(messages)
    for message in messages:
        if message.__class__.__name__ != "ToolMessage":
            continue
        if getattr(message, "name", None) != "respond":
            continue
        return _parse_respond_payload(message) or _parse_respond_payload_from_args_state(
            respond_args_by_id,
            tool_call_id=getattr(message, "tool_call_id", None),
        )
    return None


def _parse_respond_payload(tool_message) -> dict | None:
    """从 respond 工具的 ToolMessage 中解析结构化 payload。

    ToolMessage.content 是 LLM 填入 respond 工具的 JSON 字符串（LangChain 会把 args 序列化为 content）。
    用 Pydantic 严格校验；返回 None 表示解析失败（由调用方决定抛错）。
    """
    raw = getattr(tool_message, "content", "")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return _validate_respond_payload(data)


def _validate_respond_payload(data: dict) -> dict | None:
    from app.schemas.agent_response import StructuredResponse

    try:
        validated = StructuredResponse.model_validate(data)
    except Exception as exc:
        # 诊断：把校验失败原因和原始数据打出来，便于排查 LLM 输出
        try:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                logger.warning(
                    "respond payload Pydantic validation failed: errors=%s payload=%s",
                    exc.errors()[:3],
                    json.dumps(data, ensure_ascii=False)[:500],
                )
        except Exception:
            pass
        return None
    return validated.model_dump()


def _parse_respond_payload_from_args_state(state: dict[str, str], tool_call_id: str | None = None) -> dict | None:
    """从 respond tool_call args 中解析结构化回复。

    真实工具执行后的 ToolMessage.content 是 _respond 的返回值 "ok"；
    LLM 填入的参数在前面的 AIMessage/tool_call_chunks 里。
    """
    candidates: list[str] = []
    if tool_call_id and tool_call_id in state:
        candidates.append(state[tool_call_id])
    candidates.extend(raw for key, raw in state.items() if key != tool_call_id)

    for raw in candidates:
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        card = _validate_respond_payload(data)
        if card is not None:
            return card
    if state:
        # 诊断：args_state 有内容但都校验失败
        logger.warning(
            "respond args_state present but no candidate validated: state_keys=%s tool_call_id=%s last_raw=%s",
            list(state.keys()),
            tool_call_id,
            json.dumps(list(state.values())[-1], ensure_ascii=False)[:300] if state else "",
        )
    return None


def _extract_respond_tool_call_args(messages) -> dict[str, str]:
    """从完整 AIMessage 列表里提取 respond tool_call 参数，供 ToolMessage(content="ok") 反查。"""
    result: dict[str, str] = {}
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None) or []
        for index, tool_call in enumerate(tool_calls):
            name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
            if name != "respond":
                continue
            args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", None)
            if isinstance(args, dict):
                raw_args = json.dumps(args, ensure_ascii=False)
            elif isinstance(args, str):
                raw_args = args
            else:
                continue
            tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
            result[tool_call_id or f"index:{index}"] = raw_args
    return result


def _extract_respond_summary_text_delta(tool_call_chunks: list, state: dict[str, str]) -> str:
    """从 AIMessageChunk.tool_call_chunks 中挑出 respond 工具的 args，提取 summary_text 字段的增量。

    state[id] 存的是上一次累积的 args 字符串。
    返回本次新增的 token 文本（已解 JSON 转义）。
    """
    # summary_text 值的尾部可能是已关闭的 "（前一个 chunk 收到的），
    # 也可能是尚未关闭（当前 chunk 还在写入 token）—— 允许这两种结尾。
    SUMMARY_RE = re.compile(r'"summary_text"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|\Z)')

    def _tc_attr(tc, key, default=None):
        if isinstance(tc, dict):
            return tc.get(key, default)
        return getattr(tc, key, default)

    def _decode(captured: str) -> str:
        # 只在含转义（反斜杠）时按 unicode_escape 解码，避免对原始 UTF-8 误伤
        if "\\" in captured:
            try:
                return bytes(captured, "utf-8").decode("unicode_escape", errors="ignore")
            except Exception:
                return captured
        return captured

    for index, tc in enumerate(tool_call_chunks):
        tc_index = _tc_attr(tc, "index", index)
        tc_id = f"index:{tc_index}" if tc_index is not None else (_tc_attr(tc, "id") or "default")
        name = _tc_attr(tc, "name")
        if name != "respond" and tc_id not in state:
            continue
        prev_args = state.get(tc_id, "")
        new_args = prev_args + (_tc_attr(tc, "args", "") or "")
        state[tc_id] = new_args
        m = SUMMARY_RE.search(new_args)
        if not m:
            continue
        decoded = _decode(m.group(1))
        # 增量 = decoded 减去上次的 decoded 长度
        prev_match = SUMMARY_RE.search(prev_args)
        if prev_match:
            prev_decoded = _decode(prev_match.group(1))
            return decoded[len(prev_decoded):]
        return decoded
    return ""
