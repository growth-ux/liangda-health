"""Harness 框架自身的单元测试（Mock 模式，不调用 LLM）。"""

import json
from dataclasses import dataclass

import pytest

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
from harness.diagnosis import FailureDiagnosis, classify_failures
from harness.runner import CaseResult, ContextSnapshot, ToolCallTrace, _extract_tool_calls_from_messages, _extract_actual_evidence, _resolve_member_id


# ── EvalCase ──

def test_eval_case_parses_minimal_fields():
    case = EvalCase(case_id="test_001", title="测试", input="你好")
    assert case.case_id == "test_001"
    assert case.expected_tools == []
    assert case.forbidden_tools == []
    assert case.target_scope == "member"


def test_eval_case_parses_full_fields():
    data = {
        "case_id": "dad_dinner_001",
        "title": "爸爸晚餐",
        "input": "爸爸今晚吃什么",
        "history": [{"role": "user", "content": "爸爸不喜欢鱼"}],
        "target_member": "爸爸",
        "expected_intent": "meal_plan",
        "expected_tools": ["meal_plan", "respond"],
        "forbidden_tools": ["kb_search"],
        "required_evidence": ["血脂偏高"],
        "forbidden_member_sources": ["妈妈"],
        "expected_response_kind": "meal_plan",
    }
    case = EvalCase.model_validate(data)
    assert case.expected_tools == ["meal_plan", "respond"]
    assert case.forbidden_tools == ["kb_search"]
    assert case.expected_intent == "meal_plan"
    assert case.forbidden_member_sources == ["妈妈"]
    assert len(case.history) == 1


# ── Existing Checks ──

def test_check_tool_calls_all_expected_present():
    results = check_tool_calls(["meal_plan", "respond"], ["meal_plan", "respond"], [])
    assert all(r.passed for r in results)


def test_check_tool_calls_missing_expected():
    results = check_tool_calls(["respond"], ["meal_plan", "respond"], [])
    assert not results[0].passed
    assert "meal_plan" in results[0].details


def test_check_tool_calls_forbidden_violated():
    results = check_tool_calls(["meal_plan", "kb_search", "respond"], ["meal_plan", "respond"], ["kb_search"])
    forbidden_check = [r for r in results if r.check_type == "forbidden_tool"]
    assert len(forbidden_check) == 1
    assert not forbidden_check[0].passed


def test_check_tool_calls_no_forbidden_no_violation():
    results = check_tool_calls(["meal_plan", "respond"], ["meal_plan", "respond"], ["kb_search"])
    forbidden_check = [r for r in results if r.check_type == "forbidden_tool"]
    assert forbidden_check[0].passed


def test_check_response_schema_card_present():
    results = check_response_schema({"kind": "qa", "summary_text": "ok"}, "qa")
    assert all(r.passed for r in results)


def test_check_response_schema_no_card():
    results = check_response_schema(None, "qa")
    assert not results[0].passed


def test_check_response_schema_kind_mismatch():
    results = check_response_schema({"kind": "qa", "summary_text": "ok"}, "meal_plan")
    kind_check = [r for r in results if r.check_type == "response_kind"]
    assert not kind_check[0].passed


def test_check_must_not_show_no_leak():
    results = check_must_not_show("今天晚餐建议清淡", ["member_id", "诊断性结论"])
    assert results[0].passed


def test_check_must_not_show_leaked():
    results = check_must_not_show("mem_dad 的报告建议", ["mem_dad"])
    assert not results[0].passed


def test_check_member_isolation_correct():
    args = [{"tool": "meal_plan", "args": {"member_id": "mem_dad"}}]
    results = check_member_isolation(args, "mem_dad")
    assert results[0].passed


def test_check_member_isolation_wrong():
    args = [{"tool": "kb_search", "args": {"member_id": "mem_mom"}}]
    results = check_member_isolation(args, "mem_dad")
    assert not results[0].passed


def test_check_member_isolation_no_target():
    results = check_member_isolation([], None)
    assert results == []


def test_check_respond_called():
    assert check_respond_called(["meal_plan", "respond"]).passed
    assert not check_respond_called(["meal_plan"]).passed


# ── Intent Check ──

def test_check_intent_correct_meal_plan():
    results = check_intent("爸爸今晚吃什么？", "meal_plan")
    assert results[0].passed
    assert results[0].check_type == "intent"


def test_check_intent_correct_product_recommendation():
    results = check_intent("推荐一款适合全家的油", "product_recommendation")
    assert results[0].passed


def test_check_intent_correct_report_qa():
    results = check_intent("爸爸报告里血脂怎么样？", "report_qa")
    assert results[0].passed


def test_check_intent_correct_memory_query():
    results = check_intent("爸爸是不是不喜欢鱼？", "memory_query")
    assert results[0].passed


def test_check_intent_mismatch():
    results = check_intent("推荐一款适合全家的油", "meal_plan")
    assert not results[0].passed
    assert "product_recommendation" in results[0].details


def test_check_intent_no_expected():
    results = check_intent("你好", None)
    assert results == []


def test_check_intent_general_conversation():
    results = check_intent("你好", "greeting")
    assert results[0].passed  # 无关键词命中 → 视为通用对话 → 通过


# ── Evidence Hit Check ──

def test_check_evidence_hit_all_hit():
    results = check_evidence_hit(["血脂偏高"], ["总胆固醇高于参考范围，血脂偏高"])
    assert results[0].passed
    assert results[0].check_type == "evidence_hit"


def test_check_evidence_hit_missed():
    results = check_evidence_hit(["血脂偏高"], ["血糖正常"])
    assert not results[0].passed
    assert "missed" in results[0].details


def test_check_evidence_hit_empty_required():
    results = check_evidence_hit([], ["任何证据"])
    assert results == []


def test_check_evidence_hit_multiple():
    results = check_evidence_hit(["血脂偏高", "血压偏高"], ["血压 152/96，血压偏高"])
    assert not results[0].passed  # 血压偏高命中，血脂偏高未命中


# ── Safety Rule Check ──

def test_check_safety_rule_pass():
    products = [{"name": "低钠酱油", "tags": ["low_sodium"]}]
    results = check_safety_rule(["高血压"], "海鲜", products)
    assert results[0].passed


def test_check_safety_rule_violate_hypertension():
    products = [{"name": "腌渍咸菜", "tags": ["high_sodium"]}]
    results = check_safety_rule(["高血压"], "", products)
    assert not results[0].passed
    assert "high_sodium" in results[0].details


def test_check_safety_rule_violate_blood_lipid():
    products = [{"name": "猪油", "tags": ["high_fat"]}]
    results = check_safety_rule(["血脂偏高"], "", products)
    assert not results[0].passed


def test_check_safety_rule_violate_sugar_control():
    products = [{"name": "蜜饯", "tags": ["high_sugar"]}]
    results = check_safety_rule(["控糖"], "", products)
    assert not results[0].passed


def test_check_safety_rule_no_dangerous_conditions():
    products = [{"name": "薯片", "tags": ["high_sodium"]}]
    results = check_safety_rule([], "", products)
    assert results == []  # 无健康约束 → 不检查


def test_check_safety_rule_no_products():
    results = check_safety_rule(["高血压"], "", [])
    assert results == []


# ── Forbidden Product Tags Check ──

def test_check_forbidden_product_tags_clean():
    products = [{"name": "藜麦", "tags": ["high_fiber", "low_gi"]}]
    results = check_forbidden_product_tags(products, ["high_sodium"])
    assert results[0].passed
    assert results[0].check_type == "forbidden_product_tags"


def test_check_forbidden_product_tags_violated():
    products = [{"name": "腌菜", "tags": ["high_sodium"]}]
    results = check_forbidden_product_tags(products, ["high_sodium"])
    assert not results[0].passed
    assert "high_sodium" in results[0].details


def test_check_forbidden_product_tags_empty_forbidden():
    products = [{"name": "腌菜", "tags": ["high_sodium"]}]
    results = check_forbidden_product_tags(products, [])
    assert results == []


def test_check_forbidden_product_tags_multiple_products():
    products = [
        {"name": "藜麦", "tags": ["high_fiber"]},
        {"name": "腌菜", "tags": ["high_sodium"]},
    ]
    results = check_forbidden_product_tags(products, ["high_sodium"])
    assert not results[0].passed


# ── Diagnosis Layer ──

def test_classify_failures_no_failures():
    checks = [CheckResult(check_type="tool_call", passed=True, details="ok")]
    diag = classify_failures("test_001", checks)
    assert diag.failure_types == []
    assert diag.root_causes == []


def test_classify_failures_tool_error():
    checks = [CheckResult(check_type="tool_call", passed=False, details="missing meal_plan")]
    diag = classify_failures("test_001", checks)
    assert "tool_error" in diag.failure_types
    assert any("prompt" in rc or "工具" in rc for rc in diag.root_causes)
    assert any("prompt" in fs or "工具" in fs for fs in diag.fix_suggestions)


def test_classify_failures_safety_error():
    checks = [CheckResult(check_type="safety_rule", passed=False, details="high_sodium violated")]
    diag = classify_failures("test_001", checks)
    assert "safety_error" in diag.failure_types
    assert any("禁忌" in rc or "画像" in rc for rc in diag.root_causes)


def test_classify_failures_with_runtime_error():
    diag = classify_failures("test_001", [], error="ConnectionError: timeout")
    assert "runtime_error" in diag.failure_types
    assert any("异常" in rc for rc in diag.root_causes)


def test_classify_failures_multiple_types():
    checks = [
        CheckResult(check_type="tool_call", passed=False, details="missing"),
        CheckResult(check_type="safety_rule", passed=False, details="violated"),
    ]
    diag = classify_failures("test_001", checks)
    assert "tool_error" in diag.failure_types
    assert "safety_error" in diag.failure_types


def test_classify_failures_dedup():
    checks = [
        CheckResult(check_type="tool_call", passed=False, details="m1"),
        CheckResult(check_type="forbidden_tool", passed=False, details="m2"),
    ]
    diag = classify_failures("test_001", checks)
    assert diag.failure_types.count("tool_error") == 1


# ── Extract Actual Evidence ──

def test_extract_actual_evidence_from_card():
    card = {
        "summary_text": "爸爸血脂偏高需要注意",
        "payload": {
            "evidence": [
                {"excerpt": "总胆固醇高于参考范围"},
                {"text": "甘油三酯偏高"},
            ]
        }
    }
    ev = _extract_actual_evidence(card)
    assert "总胆固醇高于参考范围" in ev
    assert "甘油三酯偏高" in ev
    assert "爸爸血脂偏高需要注意" in ev  # summary_text also included


def test_extract_actual_evidence_none_card():
    assert _extract_actual_evidence(None) == []


def test_extract_actual_evidence_empty_card():
    assert _extract_actual_evidence({}) == []


# ── ContextSnapshot ──

def test_context_snapshot_defaults():
    snap = ContextSnapshot()
    assert snap.target_member is None
    assert snap.actual_evidence == []
    assert snap.recommended_products == []


# ── CaseResult ──

def test_case_result_passed_when_no_errors_and_all_checks_pass():
    case = EvalCase(case_id="t1", title="t", input="x")
    result = CaseResult(
        case=case,
        tool_calls=[ToolCallTrace(step=1, tool="respond", args={})],
        checks=[CheckResult(check_type="respond_called", passed=True, details="ok")],
    )
    assert result.passed


def test_case_result_failed_when_error():
    case = EvalCase(case_id="t1", title="t", input="x")
    result = CaseResult(case=case, error="boom")
    assert not result.passed


def test_case_result_actual_tools():
    case = EvalCase(case_id="t1", title="t", input="x")
    result = CaseResult(
        case=case,
        tool_calls=[
            ToolCallTrace(step=1, tool="meal_plan", args={}),
            ToolCallTrace(step=2, tool="respond", args={}),
        ],
    )
    assert result.actual_tools == ["meal_plan", "respond"]


# ── Resolve Member ID ──

def test_resolve_member_id_known():
    assert _resolve_member_id("爸爸") == "mem_dad"
    assert _resolve_member_id("妈妈") == "mem_mom"


def test_resolve_member_id_unknown():
    assert _resolve_member_id("陌生人") == "陌生人"


def test_resolve_member_id_none():
    assert _resolve_member_id(None) is None


# ── Extract Tool Calls from Messages ──

def test_extract_tool_calls_from_messages():
    from langchain_core.messages import AIMessage

    messages = [
        AIMessage(content="", tool_calls=[
            {"name": "meal_plan", "id": "c1", "args": {"scope": "family"}},
        ]),
        AIMessage(content="", tool_calls=[
            {"name": "respond", "id": "c2", "args": {"kind": "meal_plan"}},
        ]),
    ]
    traces = _extract_tool_calls_from_messages(messages)
    assert len(traces) == 2
    assert traces[0].tool == "meal_plan"
    assert traces[0].step == 1
    assert traces[1].tool == "respond"
    assert traces[1].step == 2


# ── Load Cases ──

def test_load_cases_from_json(tmp_path):
    cases_data = [
        {"case_id": "test_001", "title": "测试用例", "input": "你好",
         "expected_tools": ["respond"], "expected_response_kind": "greeting"},
    ]
    cases_file = tmp_path / "test_cases.json"
    cases_file.write_text(json.dumps(cases_data, ensure_ascii=False))

    from harness.runner import EvalCase
    loaded = [EvalCase.model_validate(item) for item in json.loads(cases_file.read_text())]
    assert len(loaded) == 1
    assert loaded[0].case_id == "test_001"


# ── Report ──

def test_report_prints_without_error(capsys):
    from harness.report import print_report

    case = EvalCase(case_id="t1", title="测试", input="你好",
                    expected_tools=["respond"], expected_response_kind="greeting")
    results = [
        CaseResult(
            case=case,
            tool_calls=[ToolCallTrace(step=1, tool="respond", args={})],
            card={"kind": "greeting", "summary_text": "你好"},
            checks=[
                CheckResult(check_type="respond_called", passed=True, details="ok"),
                CheckResult(check_type="tool_call", passed=True, details="all expected"),
            ],
            latency_ms=42,
        )
    ]
    passed, failed, total = print_report(results, show_diff=False)
    captured = capsys.readouterr()
    assert "t1" in captured.out
    assert "Passed: 1" in captured.out
    assert "42ms" in captured.out
    assert passed == 1
    assert failed == 0
    assert total == 1


def test_report_shows_quality_metrics(capsys):
    from harness.report import print_report

    case = EvalCase(case_id="t1", title="测试", input="你好",
                    expected_intent="greeting", expected_tools=["respond"],
                    expected_response_kind="greeting")
    results = [
        CaseResult(
            case=case,
            tool_calls=[ToolCallTrace(step=1, tool="respond", args={})],
            card={"kind": "greeting", "summary_text": "你好"},
            checks=[
                CheckResult(check_type="respond_called", passed=True, details="ok"),
                CheckResult(check_type="intent", passed=True, details="matched"),
                CheckResult(check_type="safety_rule", passed=True, details="clean"),
            ],
            latency_ms=100,
        )
    ]
    print_report(results, show_diff=False)
    captured = capsys.readouterr()
    assert "Quality Metrics" in captured.out
    assert "意图路由正确率" in captured.out
    assert "安全规则通过率" in captured.out


def test_report_shows_diagnosis_for_failed(capsys):
    from harness.report import print_report

    case = EvalCase(case_id="t1", title="测试", input="推荐油",
                    expected_tools=["mall_recommend", "respond"],
                    expected_response_kind="qa")
    results = [
        CaseResult(
            case=case,
            tool_calls=[ToolCallTrace(step=1, tool="respond", args={})],
            card={"kind": "qa", "summary_text": "ok"},
            checks=[
                CheckResult(check_type="tool_call", passed=False, details="missing mall_recommend"),
            ],
            latency_ms=50,
        )
    ]
    print_report(results, show_diff=False)
    captured = capsys.readouterr()
    assert "failure_types" in captured.out
    assert "tool_error" in captured.out
    assert "root_cause" in captured.out
    assert "fix" in captured.out
