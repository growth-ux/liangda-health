"""Eval Case 定义：结构化描述每个测试用例。"""

from pydantic import BaseModel


class EvalCase(BaseModel):
    case_id: str
    title: str
    input: str
    history: list[dict[str, str]] = []
    target_scope: str = "member"
    target_member: str | None = None
    expected_intent: str | None = None
    expected_tools: list[str] = []
    forbidden_tools: list[str] = []
    required_evidence: list[str] = []
    forbidden_product_tags: list[str] = []
    expected_product_tags: list[str] = []
    must_not_show: list[str] = []
    expected_response_kind: str | None = None
    forbidden_member_sources: list[str] = []
