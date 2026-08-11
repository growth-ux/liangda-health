"""Harness Runner：执行 Agent 并记录工具调用链路。"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.agent.langchain_agent import BaseAgentRunner
from app.services.agent.agent_tools import KbSearchTool, MallRecommendTool, MealPlanTool, MemorySearchTool
from app.services.meal.meal_plan_service import MealPlanService
from app.services.meal.meal_product_recommendation_service import MealProductRecommendationService
from app.services.common.memory_service import MemoryService
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.repositories.mall_repository import SqlAlchemyMallRepository as _MallRepo
from harness.case import EvalCase
from harness.checks import (
    CheckResult,
    check_evidence_hit,
    check_forbidden_product_tags,
    check_intent,
    check_member_isolation,
    check_must_not_show,
    check_respond_called,
    check_response_schema,
    check_safety_rule,
    check_tool_calls,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolCallTrace:
    """记录单次工具调用。"""
    step: int
    tool: str
    args: dict


@dataclass
class ContextSnapshot:
    """Agent 执行时使用的上下文快照。"""
    target_member: str | None = None
    target_member_id: str | None = None
    tool_names: list[str] = field(default_factory=list)
    actual_evidence: list[str] = field(default_factory=list)
    recommended_products: list[dict] = field(default_factory=list)
    member_health_tags: list[str] = field(default_factory=list)
    member_allergies: str = ""


@dataclass
class CaseResult:
    """单个 eval case 的完整执行结果。"""
    case: EvalCase
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    card: dict | None = None
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    token_prompt: int | None = None
    token_completion: int | None = None
    latency_ms: int = 0
    context_snapshot: ContextSnapshot = field(default_factory=ContextSnapshot)

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)

    @property
    def actual_tools(self) -> list[str]:
        return [tc.tool for tc in self.tool_calls]


def _extract_tool_calls_from_messages(messages) -> list[ToolCallTrace]:
    """从 LangChain response messages 提取工具调用链路。"""
    traces: list[ToolCallTrace] = []
    step = 0
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            step += 1
            traces.append(ToolCallTrace(step=step, tool=tc["name"], args=tc.get("args", {})))
    return traces


class _RecordingAgent:
    """包装真实 Agent，拦截 invoke() 以捕获 response messages。"""

    def __init__(self, real_agent):
        self._real = real_agent
        self.captured_messages = []

    def invoke(self, payload):
        response = self._real.invoke(payload)
        self.captured_messages = list(response.get("messages", []))
        return response

    def stream(self, payload, stream_mode=None):
        yield from self._real.stream(payload, stream_mode=stream_mode)


class HarnessRunner:
    """执行单个 eval case 并记录完整过程。"""

    def __init__(self, db: Session, member_ids: list[str], *, use_real_llm: bool = True):
        self.db = db
        self.member_ids = member_ids
        self.use_real_llm = use_real_llm
        self._mall_repo = _MallRepo(db)

    def _build_runner(self) -> BaseAgentRunner:
        """构造和线上一致的 BaseAgentRunner。"""
        member_repo = SqlAlchemyMemberRepository(self.db)

        def member_provider():
            return [
                type("M", (), {"member_id": m.member_id, "name": m.name, "relation": m.relation})()
                for m in member_repo.list_members()
            ]

        memory_service = MemoryService(member_provider=member_provider)

        return BaseAgentRunner(
            kb_tool=KbSearchTool(
                repository=SqlAlchemyKbRepository(self.db),
                allowed_member_ids=self.member_ids,
            ),
            meal_plan_tool=MealPlanTool(
                service=MealPlanService(self.db, memory_service=memory_service),
                allowed_member_ids=self.member_ids,
            ),
            mall_recommend_tool=MallRecommendTool(
                service=MealProductRecommendationService(
                    self.db,
                    mall_repository=SqlAlchemyMallRepository(self.db),
                ),
                allowed_member_ids=self.member_ids,
            ),
            memory_tool=MemorySearchTool(memory_service),
            member_provider=member_provider,
        )

    def _build_messages(self, case: EvalCase) -> list[dict[str, str]]:
        messages = list(case.history)
        messages.append({"role": "user", "content": case.input})
        return messages

    def run_case(self, case: EvalCase) -> CaseResult:
        """执行一个 eval case，返回完整结果。"""
        result = CaseResult(case=case)
        start = datetime.now()

        try:
            if self.use_real_llm:
                result = self._run_real(case, result)
            else:
                result = self._run_mock(case, result)
        except Exception as exc:
            logger.exception("harness case failed case_id=%s", case.case_id)
            result.error = f"{type(exc).__name__}: {exc}"

        result.latency_ms = int((datetime.now() - start).total_seconds() * 1000)
        result.checks = self._run_checks(case, result)
        return result

    def _run_real(self, case: EvalCase, result: CaseResult) -> CaseResult:
        """真实 LLM 模式：用 _RecordingAgent 包装真实 Agent，拦截 messages。"""
        runner = self._build_runner()
        messages = self._build_messages(case)

        # 用 _RecordingAgent 包装，捕获 response messages
        original_agent_fn = runner._agent
        recording = None

        def wrapped_agent():
            nonlocal recording
            real = original_agent_fn()
            recording = _RecordingAgent(real)
            return recording

        runner._agent = wrapped_agent

        try:
            run_result = runner.run(messages)
            result.card = run_result.get("card")
            result.token_prompt = run_result.get("token_prompt")
            result.token_completion = run_result.get("token_completion")
            if recording:
                result.tool_calls = _extract_tool_calls_from_messages(recording.captured_messages)
        finally:
            runner._agent = original_agent_fn

        return result

    def _run_mock(self, case: EvalCase, result: CaseResult) -> CaseResult:
        """Mock 模式：用 FakeAgent 模拟预期的工具调用链路，验证 harness 框架本身。"""
        runner = self._build_runner()
        fake = _build_fake_agent(case)

        original_agent_fn = runner._agent
        runner._agent = lambda: fake

        try:
            run_result = runner.run(self._build_messages(case))
            result.card = run_result.get("card")
            result.tool_calls = _extract_tool_calls_from_messages(fake._messages)
        finally:
            runner._agent = original_agent_fn

        return result

    def _run_checks(self, case: EvalCase, result: CaseResult) -> list[CheckResult]:
        """对 case 执行所有检查。"""
        # 构建上下文快照
        snapshot = self._build_context_snapshot(case, result)
        result.context_snapshot = snapshot

        checks: list[CheckResult] = []

        checks.append(check_respond_called(result.actual_tools))

        checks.extend(check_tool_calls(
            result.actual_tools,
            case.expected_tools,
            case.forbidden_tools,
        ))

        checks.extend(check_response_schema(result.card, case.expected_response_kind))

        target_member_id = _resolve_member_id(case.target_member) if case.target_member else None
        tool_call_args = [{"tool": tc.tool, "args": tc.args} for tc in result.tool_calls]
        checks.extend(check_member_isolation(tool_call_args, target_member_id))

        content = result.card.get("summary_text", "") if result.card else ""
        checks.extend(check_must_not_show(content, case.must_not_show))

        # ── 新增 checks ──
        checks.extend(check_intent(case.input, case.expected_intent))

        checks.extend(check_evidence_hit(case.required_evidence, snapshot.actual_evidence))

        checks.extend(check_safety_rule(
            snapshot.member_health_tags,
            snapshot.member_allergies,
            snapshot.recommended_products,
        ))

        checks.extend(check_forbidden_product_tags(
            snapshot.recommended_products,
            case.forbidden_product_tags,
        ))

        return checks

    def _build_context_snapshot(self, case: EvalCase, result: CaseResult) -> ContextSnapshot:
        """从 card 和 tool_calls 中提取上下文快照。"""
        target_member_id = _resolve_member_id(case.target_member) if case.target_member else None

        # 提取 evidence
        actual_evidence = _extract_actual_evidence(result.card)

        # 提取 recommended product IDs
        product_ids: list[str] = []
        for tc in result.tool_calls:
            if tc.tool == "mall_recommend":
                product_ids.extend(tc.args.get("product_ids", []))
        if result.card:
            payload = result.card.get("payload", {})
            for item in payload.get("products", []):
                pid = item.get("product_id", "")
                if pid:
                    product_ids.append(pid)

        # 查询商品标签
        recommended_products = self._query_product_tags(product_ids)

        # 查询成员健康画像
        health_tags: list[str] = []
        allergies = ""
        if target_member_id:
            member = self.db.query(Member).filter(Member.member_id == target_member_id).first()
            if member:
                try:
                    health_tags = json.loads(member.health_tags) if member.health_tags else []
                except (json.JSONDecodeError, TypeError):
                    health_tags = []
                allergies = member.allergies or ""

        return ContextSnapshot(
            target_member=case.target_member,
            target_member_id=target_member_id,
            tool_names=result.actual_tools,
            actual_evidence=actual_evidence,
            recommended_products=recommended_products,
            member_health_tags=health_tags,
            member_allergies=allergies,
        )

    def _query_product_tags(self, product_ids: list[str]) -> list[dict]:
        """根据 product_id 列表查询商品标签。"""
        if not product_ids:
            return []
        results = []
        for pid in product_ids:
            p = self.db.query(MallProduct).filter(MallProduct.product_id == pid).first()
            if p:
                try:
                    tags = json.loads(p.recommend_tags) if p.recommend_tags else []
                except (json.JSONDecodeError, TypeError):
                    tags = []
                results.append({"product_id": pid, "name": p.name, "tags": tags})
        return results


class _FakeAgent:
    """Mock Agent：根据 case 定义生成固定工具调用链路。"""

    def __init__(self, case: EvalCase):
        self.case = case
        self._messages = []

    def invoke(self, payload):
        case = self.case
        kind = case.expected_response_kind or "qa"
        target_id = _resolve_member_id(case.target_member) if case.target_member else None
        messages = []

        for tool_name in case.expected_tools:
            from langchain_core.messages import AIMessage, ToolMessage

            args = self._mock_args(tool_name, target_id, kind)
            ai = AIMessage(content="", tool_calls=[{
                "name": tool_name,
                "id": f"call_{tool_name}",
                "args": args,
            }])
            messages.append(ai)

            if tool_name == "respond":
                content = json.dumps({
                    "kind": kind,
                    "summary_text": f"Mock: {case.title}",
                    "payload": self._mock_payload(kind),
                }, ensure_ascii=False)
            elif tool_name == "mall_recommend":
                content = json.dumps({
                    "items": [{"product_id": "p_quinoa", "name": "藜麦杂粮包",
                               "reason": "高纤维", "score": 80}],
                    "product_ids": ["p_quinoa"],
                    "is_error": False, "error": None,
                }, ensure_ascii=False)
            else:
                content = "ok" if tool_name == "respond" else "mock tool result"

            messages.append(ToolMessage(
                content=content,
                tool_call_id=f"call_{tool_name}",
                name=tool_name,
            ))

        self._messages = messages
        return {"messages": messages}

    def _mock_args(self, tool_name: str, target_id: str | None, kind: str) -> dict:
        case = self.case
        if tool_name == "meal_plan":
            return {"scope": case.target_scope, "member_id": target_id, "meal_type": "day"}
        if tool_name == "mall_recommend":
            return {"scope": case.target_scope, "member_id": target_id,
                    "meal_plan_text": "", "query_text": case.input, "limit": 5}
        if tool_name == "kb_search":
            return {"query": case.input, "member_id": target_id, "top_k": 5}
        if tool_name == "memory_search":
            return {"query": case.input, "member_id": target_id, "limit": 5}
        if tool_name == "respond":
            return {"kind": kind, "summary_text": f"Mock: {case.title}",
                    "payload": self._mock_payload(kind)}
        return {}

    def _mock_payload(self, kind: str) -> dict:
        case = self.case
        if kind == "meal_plan":
            return {"scope": case.target_scope, "target_member_name": case.target_member,
                    "meal_items": [{"slot": "dinner", "title": "清蒸鸡胸", "summary": "低脂高蛋白"}],
                    "member_adjustments": [], "avoid_tags": [], "extra_note": None}
        if kind == "kb_interpretation":
            return {
                "topic": case.required_evidence[0] if case.required_evidence else "健康指标",
                "evidence": [{"type": "report_fact", "title": "体检报告",
                              "excerpt": case.required_evidence[0] if case.required_evidence else "指标偏高",
                              "source_id": "fact_1", "source_label": "体检报告 p3"}],
                "suggestions": ["调整饮食结构，减少高油高盐食物"],
                "red_flags": [],
            }
        if kind == "greeting":
            return {"message": "你好，今天可以问我一日三餐", "suggested_topics": ["三餐"]}
        return {"question_topic": case.title, "answer": f"关于{case.title}的建议", "tips": []}


def _extract_actual_evidence(card: dict | None) -> list[str]:
    """从 card 的 payload 中提取 evidence 文本列表。"""
    if not card:
        return []
    evidence = []
    payload = card.get("payload", {})
    for ev in payload.get("evidence", []):
        if isinstance(ev, dict):
            text = ev.get("excerpt", "") or ev.get("text", "")
            if text:
                evidence.append(text)
        elif isinstance(ev, str):
            evidence.append(ev)
    summary = card.get("summary_text", "")
    if summary:
        evidence.append(summary)
    return evidence


def _build_fake_agent(case: EvalCase) -> _FakeAgent:
    return _FakeAgent(case)


def _resolve_member_id(target_member: str | None) -> str | None:
    """把家庭成员称呼映射到 member_id。"""
    if not target_member:
        return None
    mapping = {"爸爸": "mem_dad", "妈妈": "mem_mom", "本人": "mem_son",
               "父亲": "mem_dad", "母亲": "mem_mom", "儿子": "mem_son"}
    return mapping.get(target_member, target_member)
