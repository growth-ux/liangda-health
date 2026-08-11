import re
from collections.abc import Iterable
import json
import logging
from typing import Literal

from langchain.tools import tool

from app.core.config import settings
from app.services.agent.agent_evidence import AgentEvidenceCollector
from app.services.agent.llm_logging import log_llm_request

logger = logging.getLogger(__name__)


def _build_members_block(members: list) -> str:
    if not members:
        return "15. 当前没有可用家人，无法检索报告。\n"
    # 统计每个关系称呼出现次数：唯一就直接用，多个才反问
    relation_count: dict[str, int] = {}
    for member in members:
        relation = member.relation if hasattr(member, "relation") else member.get("relation", "")
        if relation:
            relation_count[relation] = relation_count.get(relation, 0) + 1
    lines = ["15. 当前可用家人列表："]
    for index, member in enumerate(members, start=1):
        member_id = member.member_id if hasattr(member, "member_id") else member["member_id"]
        name = member.name if hasattr(member, "name") else member["name"]
        relation = member.relation if hasattr(member, "relation") else member.get("relation", "")
        lines.append(f"   {index}. {name}（member_id={member_id}，{relation}）")
    lines.append("   称呼解析规则（不要机械反问，按顺序判断）：")
    lines.append('   - 用户用称呼（"爸爸/妈妈/儿子/女儿/爷爷/奶奶/外公/外婆/本人"等）时，先在列表里按关系字段匹配。')
    lines.append('   - 列表里**只有一个**家人对应该称呼时，直接把那位的 member_id 传给工具（kb_search / memory_search / meal_plan / mall_recommend），**不要反问**。')
    lines.append('   - 列表里有**多个**家人对应该称呼时（如同一个家既有亲爷爷也有外公都被叫"爷爷"），才反问"您说的XX是列表里哪一位？"，不要猜。')
    lines.append('   - 用户用姓名（如"张志远"）时按姓名精确匹配；匹配不到再反问。')
    lines.append('   - 用户用"他/她"时，优先看最近几条历史消息里点过名的家人；当前消息上下文能定位到具体家人就直接用，**完全没有上下文才反问**。')
    lines.append('   - 用户说"全家/我们家/家里人"时不传 member_id，走家庭级记忆/报告。')
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
        summary_text: Markdown 摘要（餐单/一般回复≤ 400 字，报告解读 kb_interpretation ≤ 1200 字），可用少量加粗、emoji 和短列表，会流式输出。
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


class BaseAgentRunner:
    SYSTEM_PROMPT_TEMPLATE = ""

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
        self._evidence_collector: AgentEvidenceCollector | None = None

    def _system_prompt(self) -> str:
        members = self.member_provider()
        return self.SYSTEM_PROMPT_TEMPLATE.format(members_block=_build_members_block(members))

    def _ensure_api_key(self) -> None:
        if not settings.llm_api_key:
            raise LlmConfigError("未配置模型 API Key")

    def _append_kb_context(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        # LLM now drives KB search via the kb_search tool (with explicit member_id).
        # This auto-injection path is retained as a no-op for backward compatibility.
        return messages

    def _attach_evidence_collector(self) -> AgentEvidenceCollector:
        collector = AgentEvidenceCollector()
        self._evidence_collector = collector
        for tool in (self.kb_tool, self.meal_plan_tool, self.memory_tool, self.mall_recommend_tool):
            if tool is not None:
                tool.evidence_collector = collector
        return collector

    def _apply_evidence_to_card(self, card: dict) -> dict:
        collector = self._evidence_collector
        if collector is None:
            return card
        evidence = collector.dump()
        if evidence is None:
            return card
        card["evidence"] = evidence.model_dump()
        return card

    def run(self, messages: list[dict[str, str]]) -> dict[str, object]:
        self._ensure_api_key()
        logger.info("agent run start message_count=%s model=%s", len(messages), settings.llm_model)
        self._attach_evidence_collector()
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        logger.info(
            "agent run invoke prepared_messages roles=%s last_user_chars=%s",
            [message["role"] for message in prepared_messages],
            len(prepared_messages[-1]["content"]) if prepared_messages else 0,
        )
        log_llm_request(
            logger,
            service="langchain_agent.run",
            payload={
                "model": settings.llm_model,
                "base_url": settings.llm_base_url,
                "temperature": settings.llm_temperature,
                "timeout": settings.llm_timeout_seconds,
                "system_prompt": self._system_prompt(),
                "messages": prepared_messages,
            },
        )
        response = agent.invoke({"messages": self._to_langchain_messages(prepared_messages)})
        response_message = response["messages"][-1]
        token_usage = (
            response_message.response_metadata.get("token_usage", {})
            if response_message.response_metadata
            else {}
        )
        product_recs = self._extract_products(response["messages"])
        card = _extract_card(response["messages"])
        if card is None:
            logger.warning("agent run no respond tool call in messages; raising")
            raise ResponseSchemaError("LLM 未调用 respond 工具")
        card = self._apply_evidence_to_card(card)
        # 临时诊断日志：记录总调度最终交给前端的完整结构化回复。
        logger.info(
            "agent run respond card raw kind=%s payload=%s summary=%s",
            card.get("kind"),
            json.dumps(card.get("payload"), ensure_ascii=False),
            card.get("summary_text", ""),
        )
        result = {
            "content": card.get("summary_text", ""),
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
            "product_recommendations": product_recs,
            "card": card,
        }
        logger.info(
            "agent run done kind=%s summary_chars=%s prompt_tokens=%s completion_tokens=%s item_count=%s card_keys=%s",
            card.get("kind"),
            len(card.get("summary_text", "")),
            result["token_prompt"],
            result["token_completion"],
            len((product_recs or {}).get("items") or []),
            list(card.keys()),
        )
        return result

    def _extract_products(self, messages) -> dict | None:
        return _extract_product_recommendations(messages)

    def stream(self, messages: list[dict[str, str]]) -> Iterable[tuple[Literal["delta", "product_recommendations", "card"], object]]:
        self._ensure_api_key()
        logger.info("agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        self._attach_evidence_collector()
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        logger.info(
            "agent stream invoke prepared_messages roles=%s last_user_chars=%s",
            [message["role"] for message in prepared_messages],
            len(prepared_messages[-1]["content"]) if prepared_messages else 0,
        )
        log_llm_request(
            logger,
            service="langchain_agent.stream",
            payload={
                "model": settings.llm_model,
                "base_url": settings.llm_base_url,
                "temperature": settings.llm_temperature,
                "timeout": settings.llm_timeout_seconds,
                "system_prompt": self._system_prompt(),
                "messages": prepared_messages,
            },
        )
        respond_args_state: dict[str, str] = {}
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            events, done = self._process_stream_chunk(chunk, respond_args_state)
            for event in events:
                yield event
            if done:
                return
        logger.warning(
            "agent stream finished without card args_state_keys=%s",
            list(respond_args_state.keys()),
        )
        fallback_card = self._fallback_evidence_card()
        if fallback_card is not None:
            logger.info("agent stream emit fallback evidence card")
            yield ("card", fallback_card)

    def _process_stream_chunk(
        self, chunk, respond_args_state: dict[str, str]
    ) -> tuple[list[tuple], bool]:
        """处理单个 stream chunk，返回 (events, 终止标志)。终止为 True 表示已产出 respond 卡片。"""
        events: list[tuple] = []

        # 1) mall_recommend 工具：JSON 字符串 → 现有 product_recommendations 事件
        payload = _try_parse_mall_recommend_payload(chunk)
        if payload is not None and payload.get("items"):
            logger.info("agent stream emit product_recommendations item_count=%s", len(payload["items"]))
            events.append(("product_recommendations", payload))
            return events, False

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
            card = self._apply_evidence_to_card(card)
            # 临时诊断日志：记录总调度最终交给前端的完整结构化回复，便于和专家原始输出对比。
            logger.info(
                "agent stream respond card raw kind=%s payload=%s summary=%s",
                card.get("kind"),
                json.dumps(card.get("payload"), ensure_ascii=False),
                card.get("summary_text", ""),
            )
            logger.info(
                "agent stream emit card kind=%s summary_chars=%s payload_keys=%s args_state_keys=%s",
                card.get("kind"),
                len(card.get("summary_text", "")),
                list((card.get("payload") or {}).keys()) if isinstance(card.get("payload"), dict) else [],
                list(respond_args_state.keys()),
            )
            events.append(("card", card))
            return events, True

        # 3) AIMessageChunk：respond args 增量 → delta；普通文本 → delta
        if chunk.__class__.__name__ == "AIMessageChunk":
            tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
            respond_chunk_text = _extract_respond_summary_text_delta(tool_call_chunks, respond_args_state)
            if respond_chunk_text:
                logger.info(
                    "agent stream emit delta from respond summary chars=%s args_state_keys=%s",
                    len(respond_chunk_text),
                    list(respond_args_state.keys()),
                )
                events.append(("delta", respond_chunk_text))
                # respond 工具已在 summary_text 中输出内容，跳过同一 chunk 的普通文本以避免重复
            else:
                text = _content_to_text(getattr(chunk, "content", ""))
                if text:
                    logger.info("agent stream emit delta from content chars=%s", len(text))
                    events.append(("delta", text))
            return events, False

        logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
        return events, False

    def _fallback_evidence_card(self) -> dict | None:
        """模型没调 respond 直接文本收尾时，补一张只承载证据链的空卡。

        summary_text 为空，前端不会渲染卡片主体，只用于挂载证据链 tab。
        """
        collector = self._evidence_collector
        if collector is None:
            return None
        evidence = collector.dump()
        if evidence is None:
            return None
        return {
            "kind": "general_advice",
            "summary_text": "",
            "payload": {"topic": "", "advice": "", "cautions": []},
            "evidence": evidence.model_dump(),
        }

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
                member_id: str | None = None,
                meal_plan_text: str = "",
                query_text: str = "",
                limit: int = 5,
            ) -> str:
                """根据 meal_plan 工具返回的餐单文本和健康画像推荐商城商品。
                当用户只问某一类商品（如油/米/调料）时，meal_plan_text 可为空，
                并把原问题放进 query_text，service 会按类目约束和成员健康画像一起匹配。
                """
                logger.info(
                    "agent tool call name=mall_recommend scope=%s member_id=%s limit=%s meal_plan_chars=%s query_chars=%s",
                    scope,
                    member_id,
                    limit,
                    len(meal_plan_text.strip()),
                    len(query_text.strip()),
                )
                return self.mall_recommend_tool.recommend(
                    scope=scope,
                    member_id=member_id,
                    meal_plan_text=meal_plan_text,
                    query_text=query_text,
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
        logger.warning(
            "respond payload fallback attempt kind=%s has_summary=%s payload_type=%s",
            data.get("kind"),
            bool(data.get("summary_text")),
            type(data.get("payload")).__name__,
        )
        return _build_generic_response_card(data)
    logger.info(
        "respond payload validated kind=%s summary_chars=%s payload_type=%s",
        validated.kind,
        len(validated.summary_text),
        type(validated.payload).__name__,
    )
    return _format_card_summary_text(validated.model_dump())


def _build_generic_response_card(data: dict) -> dict | None:
    from app.schemas.agent_response import StructuredResponse

    summary_text = data.get("summary_text")
    if not isinstance(summary_text, str) or not summary_text.strip():
        logger.warning("respond payload fallback skipped because summary_text missing")
        return None
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    topic = payload.get("topic") or payload.get("question_topic") or data.get("kind") or "健康建议"
    generic = {
        "kind": "general_advice",
        "summary_text": summary_text[:1200],
        "payload": {
            "topic": str(topic)[:80] if str(topic).strip() else "健康建议",
            "advice": summary_text[:1200],
            "cautions": [],
        },
    }
    try:
        card = _format_card_summary_text(StructuredResponse.model_validate(generic).model_dump())
        logger.warning(
            "respond payload downgraded to general_advice original_kind=%s topic=%s",
            data.get("kind"),
            generic["payload"]["topic"],
        )
        return card
    except Exception:
        logger.exception("respond payload fallback validation failed")
        return None


def _format_card_summary_text(card: dict) -> dict:
    summary = card.get("summary_text")
    if not isinstance(summary, str) or not summary.strip():
        return card
    card["summary_text"] = _format_summary_text(summary)
    return card


def _format_summary_text(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    formatted: list[str] = []
    heading_markers = ("家人和健康关注", "晚餐安排", "为什么这样安排")
    item_prefixes = ("主菜：", "配菜：", "汤品：", "水果：", "主食：")

    for line in lines:
        if not line:
            if formatted and formatted[-1] != "":
                formatted.append("")
            continue
        if line in heading_markers:
            formatted.append(f"**{line}**")
        elif line.startswith(item_prefixes):
            label, value = line.split("：", 1)
            formatted.append(f"✅ **{label}**：{value}")
        else:
            formatted.append(line)
    result = "\n".join(formatted)
    # 在句子边界截断，避免切断词语或句子中间
    max_length = 2000
    if len(result) > max_length:
        truncated = result[:max_length]
        # 优先在段落/句子边界截断
        for sep in ("\n\n", "\n", "。", "；", "！", "？", "，"):
            pos = truncated.rfind(sep)
            if pos > max_length // 2:
                truncated = truncated[:pos + len(sep)]
                break
        result = truncated.rstrip()
    return result


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
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "respond args candidate invalid json error=%s raw=%s",
                exc,
                raw,
            )
            continue
        if not isinstance(data, dict):
            logger.warning("respond args candidate is not object type=%s raw=%s", type(data).__name__, raw)
            continue
        card = _validate_respond_payload(data)
        if card is not None:
            return card
        logger.warning(
            "respond args candidate failed schema kind=%s raw=%s",
            data.get("kind"),
            raw,
        )
    if state:
        # 诊断：args_state 有内容但都校验失败
        logger.warning(
            "respond args_state present but no candidate validated: state_keys=%s tool_call_id=%s last_raw=%s",
            list(state.keys()),
            tool_call_id,
            json.dumps(list(state.values())[-1], ensure_ascii=False) if state else "",
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
    if result:
        logger.info("respond tool call args extracted ids=%s", list(result.keys()))
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
        # chunk 边界可能把 \n、\uXXXX 等转义切成两半导致解码失败；
        # 此时逐步截断到上一个反斜杠重试，保证 decoded 始终是正确前缀，
        # 绝不能回退返回原始串——长度基准一旦错乱，已输出的文本会被当成新增 delta 重发。
        text = captured
        while True:
            try:
                return json.loads(f'"{text}"')
            except (TypeError, json.JSONDecodeError):
                index = text.rfind("\\")
                if index <= 0:
                    return ""
                text = text[:index]

    def _resolve_state_keys(tc, current_state: dict[str, str]) -> list[str]:
        name = _tc_attr(tc, "name")
        tc_index = _tc_attr(tc, "index")
        tc_id = _tc_attr(tc, "id")
        index_key = f"index:{tc_index}" if tc_index is not None else None
        candidate_keys = [key for key in (index_key, tc_id) if key]

        if name == "respond":
            if candidate_keys:
                return candidate_keys
            return ["default"]

        existing = [key for key in candidate_keys if key in current_state]
        if existing:
            return existing

        # 某些兼容层后续 chunk 不再带 name/index，只剩下 call_id；此时沿用唯一活跃 respond 缓冲。
        if name is None and len(current_state) == 1:
            return [next(iter(current_state.keys()))]
        return []

    for index, tc in enumerate(tool_call_chunks):
        state_keys = _resolve_state_keys(tc, state)
        if not state_keys:
            continue
        raw_delta = _tc_attr(tc, "args", "") or ""
        primary_key = state_keys[0]
        prev_args = state.get(primary_key, "")
        # OpenAI 兼容接口通常返回新增片段，但部分模型会返回截至当前的完整参数。
        # 后一种格式若继续拼接，会把已输出的 summary_text 当成新文本再次发送。
        is_summary_snapshot = (
            prev_args
            and raw_delta.lstrip().startswith("{")
            and '"summary_text"' in raw_delta
        )
        new_args = raw_delta if (prev_args and raw_delta.startswith(prev_args)) or is_summary_snapshot else prev_args + raw_delta
        for key in dict.fromkeys(state_keys):
            state[key] = new_args
        logger.info(
            "respond args chunk appended state_keys=%s name=%s prev_chars=%s new_chars=%s",
            state_keys,
            _tc_attr(tc, "name"),
            len(prev_args),
            len(new_args),
        )
        # chunk 边界把 \n、\uXXXX 切成两半时，尾部会残留落单反斜杠：
        # 既不能解码，也会让正则把它当普通字符吃掉导致长度基准错乱。
        # 这里先视为未消费（等下个 chunk 补齐），prev 同样处理，保证两边基准一致。
        new_for_match = new_args
        tail_backslashes = len(new_for_match) - len(new_for_match.rstrip("\\"))
        if tail_backslashes % 2 == 1:
            new_for_match = new_for_match[:-1]
        m = SUMMARY_RE.search(new_for_match)
        if not m:
            continue
        decoded = _decode(m.group(1))
        prev_stripped = prev_args
        tail_backslashes = len(prev_stripped) - len(prev_stripped.rstrip("\\"))
        if tail_backslashes % 2 == 1:
            prev_stripped = prev_stripped[:-1]
        prev_match = SUMMARY_RE.search(prev_stripped)
        if prev_match:
            prev_decoded = _decode(prev_match.group(1))
            delta = decoded[len(prev_decoded):]
            if delta:
                logger.info("respond summary delta parsed state_key=%s delta_chars=%s", primary_key, len(delta))
            return delta
        logger.info("respond summary initial parsed state_key=%s chars=%s", primary_key, len(decoded))
        return decoded
    return ""
