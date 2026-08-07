"""Diagnosis Layer：解释失败原因，给出修复建议。"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.checks import CheckResult


# ── Failure Classification 映射 ──

_CHECK_TO_FAILURE_TYPE: dict[str, str] = {
    "intent":           "intent_error",
    "member_isolation": "member_error",
    "tool_call":        "tool_error",
    "forbidden_tool":   "tool_error",
    "evidence_hit":     "retrieval_error",
    "safety_rule":      "safety_error",
    "response_schema":  "schema_error",
    "response_kind":    "schema_error",
    "must_not_show":    "schema_error",
    "summary_length":   "schema_error",
    "respond_called":   "schema_error",
    "forbidden_product_tags": "recommendation_error",
}


# ── Root Cause Hint 映射 ──

_ROOT_CAUSE_HINTS: dict[str, tuple[str, str]] = {
    # failure_type → (possible_cause, fix_direction)
    "intent_error": (
        "prompt 路由规则不清或关键词覆盖不足",
        "收紧意图规则，增加 few-shot 示例",
    ),
    "member_error": (
        "成员解析缺少历史指代或上下文继承",
        "增加 reference carry-over，显式传递 target_member",
    ),
    "tool_error": (
        "工具边界描述不清或工具职责重叠",
        "拆分工具职责或增强系统 prompt 中的工具说明",
    ),
    "retrieval_error": (
        "query 表达和报告指标不匹配，或 chunk 切分不合理",
        "增加 query rewrite / keyword search，优化 chunk 粒度",
    ),
    "safety_error": (
        "商品标签缺少禁忌映射，或健康画像未参与推荐过滤",
        "补充安全规则和黑名单标签，在推荐前做健康约束过滤",
    ),
    "schema_error": (
        "模型未调用 respond 或输出结构不稳定",
        "强化 respond 强制规则，增加 output schema 约束",
    ),
    "recommendation_error": (
        "推荐规则未过滤禁忌标签，或健康画像权重不足",
        "在推荐链路中加入标签黑名单过滤和健康画像加权",
    ),
    "memory_error": (
        "记忆检索或写入逻辑异常",
        "检查 MemoryService 调用参数和 mem0 配置",
    ),
}


@dataclass
class FailureDiagnosis:
    """单个用例的失败诊断。"""
    case_id: str
    failure_types: list[str] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)
    fix_suggestions: list[str] = field(default_factory=list)


def classify_failures(case_id: str, checks: list[CheckResult], error: str | None = None) -> FailureDiagnosis:
    """Failure Classification：把失败的 check 映射到失败类型。"""
    diag = FailureDiagnosis(case_id=case_id)

    if error:
        diag.failure_types.append("runtime_error")
        diag.root_causes.append(f"执行异常: {error}")
        diag.fix_suggestions.append("检查 Agent Runner 连接和模型配置")

    for c in checks:
        if c.passed:
            continue
        ftype = _CHECK_TO_FAILURE_TYPE.get(c.check_type, "unknown_error")
        if ftype not in diag.failure_types:
            diag.failure_types.append(ftype)

        hint = _ROOT_CAUSE_HINTS.get(ftype)
        if hint:
            cause, fix = hint
            if cause not in diag.root_causes:
                diag.root_causes.append(cause)
            if fix not in diag.fix_suggestions:
                diag.fix_suggestions.append(fix)

    return diag
