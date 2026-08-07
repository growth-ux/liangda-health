"""Evaluation Checks：判断 Agent 输出是否符合预期。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    check_type: str
    passed: bool
    details: str = ""


def check_tool_calls(actual_tools: list[str], expected: list[str], forbidden: list[str]) -> list[CheckResult]:
    """Tool Call Check：检查 expected_tools 是否被调用、forbidden_tools 是否未被调用。"""
    results = []
    actual_set = set(actual_tools)

    if expected:
        missing = [t for t in expected if t not in actual_set]
        results.append(CheckResult(
            check_type="tool_call",
            passed=len(missing) == 0,
            details=f"expected={expected} actual={actual_tools} missing={missing}" if missing else f"all expected tools called: {expected}",
        ))

    if forbidden:
        violated = [t for t in forbidden if t in actual_set]
        results.append(CheckResult(
            check_type="forbidden_tool",
            passed=len(violated) == 0,
            details=f"forbidden tools violated: {violated}" if violated else f"no forbidden tools called: {forbidden}",
        ))

    return results


def check_response_schema(card: dict | None, expected_kind: str | None) -> list[CheckResult]:
    """Response Schema Check：检查 card 是否存在、kind 是否匹配、summary_text 是否合规。"""
    results = []

    if card is None:
        results.append(CheckResult(check_type="response_schema", passed=False, details="no respond card found"))
        return results

    results.append(CheckResult(check_type="response_schema", passed=True, details="respond card present"))

    if expected_kind:
        actual_kind = card.get("kind")
        results.append(CheckResult(
            check_type="response_kind",
            passed=actual_kind == expected_kind,
            details=f"expected={expected_kind} actual={actual_kind}",
        ))

    summary = card.get("summary_text", "")
    if summary and len(summary) > 400:
        results.append(CheckResult(
            check_type="summary_length",
            passed=False,
            details=f"summary_text too long: {len(summary)} chars (max 400)",
        ))

    return results


def check_must_not_show(content: str, must_not_show: list[str]) -> list[CheckResult]:
    """Forbidden Rules：检查用户可见文本中是否泄漏内部 ID 或禁忌内容。"""
    if not must_not_show:
        return []

    violations = [item for item in must_not_show if item in content]
    return [CheckResult(
        check_type="must_not_show",
        passed=len(violations) == 0,
        details=f"leaked: {violations}" if violations else f"no forbidden content leaked: {must_not_show}",
    )]


def check_member_isolation(tool_call_args: list[dict], target_member_id: str | None) -> list[CheckResult]:
    """Member Isolation Check：检查工具参数是否使用了正确的 member_id。"""
    if not target_member_id:
        return []

    results = []
    for call in tool_call_args:
        tool_name = call.get("tool", "")
        args = call.get("args", {})
        if "member_id" in args and args["member_id"] and args["member_id"] != target_member_id:
            results.append(CheckResult(
                check_type="member_isolation",
                passed=False,
                details=f"{tool_name} used wrong member_id: expected={target_member_id} actual={args['member_id']}",
            ))
            return results

    results.append(CheckResult(
        check_type="member_isolation",
        passed=True,
        details=f"all tool calls used correct member_id: {target_member_id}",
    ))
    return results


def check_respond_called(actual_tools: list[str]) -> CheckResult:
    """基础检查：Agent 是否调用了 respond 工具完成回复。"""
    return CheckResult(
        check_type="respond_called",
        passed="respond" in actual_tools,
        details="respond was called" if "respond" in actual_tools else "respond was NOT called",
    )


# ── Intent Check ──

_INTENT_KEYWORD_RULES: dict[str, list[str]] = {
    "meal_plan": ["吃什么", "早餐", "午餐", "晚餐", "三餐", "吃啥", "早饭", "晚饭", "午饭"],
    "product_recommendation": ["推荐", "买", "购买", "商品", "选购"],
    "report_qa": ["报告", "体检", "指标", "页码", "检查结果"],
    "evidence_explanation": ["为什么推荐", "依据", "原因"],
    "memory_query": ["不喜欢", "记得", "是不是不", "偏好"],
}


def check_intent(input_text: str, expected_intent: str | None) -> list[CheckResult]:
    """Intent Check：检查用户问题是否路由到预期意图。"""
    if not expected_intent:
        return []

    predicted = None
    for intent, keywords in _INTENT_KEYWORD_RULES.items():
        if any(kw in input_text for kw in keywords):
            predicted = intent
            break

    if predicted is None:
        return [CheckResult(
            check_type="intent",
            passed=True,
            details="no keyword-based intent detected (general conversation)",
        )]

    return [CheckResult(
        check_type="intent",
        passed=predicted == expected_intent,
        details=f"expected={expected_intent} detected={predicted}"
        if predicted != expected_intent
        else f"intent matched: {expected_intent}",
    )]


# ── Evidence Hit Check ──


def check_evidence_hit(required_evidence: list[str], actual_evidence: list[str]) -> list[CheckResult]:
    """Evidence Hit Check：检查必需证据是否被引用。"""
    if not required_evidence:
        return []

    hit, missed = [], []
    for req in required_evidence:
        if any(req in ev for ev in actual_evidence):
            hit.append(req)
        else:
            missed.append(req)

    return [CheckResult(
        check_type="evidence_hit",
        passed=len(missed) == 0,
        details=f"hit={hit} missed={missed}" if missed else f"all evidence hit: {hit}",
    )]


# ── Safety Rule Check ──

_CONDITION_DANGEROUS_TAGS: dict[str, list[str]] = {
    "高血压": ["high_sodium"],
    "血脂偏高": ["high_fat", "high_oil"],
    "控糖": ["high_sugar", "high_gi"],
    "血糖偏高": ["high_sugar", "high_gi"],
}


def check_safety_rule(
    member_health_tags: list[str],
    member_allergies: str,
    recommended_products: list[dict],
) -> list[CheckResult]:
    """Safety Rule Check：检查推荐商品是否违反健康约束（过敏/慢病/禁忌）。"""
    dangerous: set[str] = set()
    reasons: dict[str, str] = {}

    for tag in member_health_tags:
        for cond, tags in _CONDITION_DANGEROUS_TAGS.items():
            if cond in tag:
                for t in tags:
                    dangerous.add(t)
                    reasons.setdefault(t, cond)

    if member_allergies:
        for tag in ["high_allergen"]:
            dangerous.add(tag)
            reasons.setdefault(tag, f"allergy:{member_allergies}")

    if not dangerous or not recommended_products:
        return []

    violations = []
    for p in recommended_products:
        p_tags = set(p.get("tags", []))
        hit = p_tags & dangerous
        if hit:
            conds = [reasons.get(t, t) for t in hit]
            violations.append((p.get("name", "unknown"), list(hit), conds))

    return [CheckResult(
        check_type="safety_rule",
        passed=len(violations) == 0,
        details="; ".join(
            f"{n} has tags={t} (conditions={c})" for n, t, c in violations
        ) if violations else "all products passed safety check",
    )]


# ── Forbidden Product Tags Check ──


def check_forbidden_product_tags(
    recommended_products: list[dict],
    forbidden_tags: list[str],
) -> list[CheckResult]:
    """Forbidden Product Tags：检查推荐商品是否包含禁止标签。"""
    if not forbidden_tags:
        return []

    forbidden_set = set(forbidden_tags)
    violations = []
    for p in recommended_products:
        p_tags = set(p.get("tags", []))
        hit = p_tags & forbidden_set
        if hit:
            violations.append((p.get("name", "unknown"), list(hit)))

    return [CheckResult(
        check_type="forbidden_product_tags",
        passed=len(violations) == 0,
        details="; ".join(f"{n} has forbidden tags={t}" for n, t in violations)
        if violations else f"no forbidden tags found in {len(recommended_products)} products",
    )]
