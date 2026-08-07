"""Reporting：终端输出 Harness 回归结果。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from harness.diagnosis import FailureDiagnosis, classify_failures

if TYPE_CHECKING:
    from harness.runner import CaseResult

_LAST_RESULTS_PATH = Path(__file__).resolve().parent.parent / "runtime" / "harness_last_results.json"


def print_report(results: list[CaseResult], *, show_diff: bool = True) -> tuple[int, int, int]:
    """打印终端可读的 Harness 回归报告。"""
    if not results:
        print("\n⚠️  No eval cases to run.\n")
        return 0, 0, 0

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print("\n" + "=" * 70)
    print("  Harness Regression Report")
    print("=" * 70)

    # 每个 case 的结果
    for r in results:
        icon = "✅" if r.passed else "❌"
        print(f"\n{icon}  {r.case.case_id}: {r.case.title}")
        print(f"   input: {r.case.input[:50]}{'...' if len(r.case.input) > 50 else ''}")
        if r.tool_calls:
            tools_str = " → ".join(tc.tool for tc in r.tool_calls)
            print(f"   tools: {tools_str}")
        if r.card:
            print(f"   kind: {r.card.get('kind', '?')}")
        if r.error:
            print(f"   ⚠️  error: {r.error}")
        for c in r.checks:
            check_icon = "  ✓" if c.passed else "  ✗"
            print(f"   {check_icon} [{c.check_type}] {c.details}")

        # 上下文快照摘要
        snap = r.context_snapshot
        if snap.actual_evidence:
            print(f"   📎 evidence: {snap.actual_evidence[:3]}")
        if snap.recommended_products:
            names = [p['name'] for p in snap.recommended_products[:3]]
            print(f"   🛒 products: {names}")
        if snap.member_health_tags:
            print(f"   🏥 health_tags: {snap.member_health_tags}")

        # Diagnosis（只对失败用例）
        if not r.passed:
            diag = classify_failures(r.case.case_id, r.checks, r.error)
            if diag.failure_types:
                print(f"   🔍 failure_types: {diag.failure_types}")
            if diag.root_causes:
                for rc in diag.root_causes:
                    print(f"   💡 root_cause: {rc}")
            if diag.fix_suggestions:
                for fs in diag.fix_suggestions:
                    print(f"   🔧 fix: {fs}")

        if r.latency_ms:
            print(f"   ⏱  {r.latency_ms}ms", end="")
            if r.token_prompt:
                print(f"  tokens: {r.token_prompt}+{r.token_completion}", end="")
            print()

    # 汇总
    print("\n" + "-" * 70)
    print(f"  Total: {len(results)}  |  Passed: {passed}  |  Failed: {failed}")

    # 按 check type 统计通过率
    type_stats: dict[str, list[bool]] = {}
    for r in results:
        for c in r.checks:
            type_stats.setdefault(c.check_type, []).append(c.passed)

    if type_stats:
        print("\n  Pass Rate by Check Type:")
        for check_type, outcomes in sorted(type_stats.items()):
            rate = sum(outcomes) / len(outcomes) * 100
            bar = "█" * int(rate // 10) + "░" * (10 - int(rate // 10))
            print(f"    {check_type:<26s} {bar} {rate:.0f}% ({sum(outcomes)}/{len(outcomes)})")

    # ── Quality Metrics ──
    _print_quality_metrics(results, type_stats)

    # 失败用例汇总
    if failed > 0:
        print(f"\n  ❌ Failed Cases ({failed}):")
        for r in results:
            if not r.passed:
                failed_checks = [c for c in r.checks if not c.passed]
                reasons = "; ".join(f"{c.check_type}: {c.details}" for c in failed_checks)
                print(f"    - {r.case.case_id}: {reasons or r.error}")

    # ── Regression Diff ──
    if show_diff:
        _print_regression_diff(results, passed, failed)

    print("\n" + "=" * 70 + "\n")

    # 保存本次结果供下次 diff
    _save_results(results)

    return passed, failed, len(results)


def _print_quality_metrics(results: list[CaseResult], type_stats: dict[str, list[bool]]) -> None:
    """Quality Metrics：工具调用率 / 证据命中率 / 安全通过率 / 推荐质量。"""
    print("\n  Quality Metrics:")

    def _rate(check_type: str) -> str:
        outcomes = type_stats.get(check_type, [])
        if not outcomes:
            return "N/A"
        rate = sum(outcomes) / len(outcomes) * 100
        return f"{rate:.0f}% ({sum(outcomes)}/{len(outcomes)})"

    # 工具调用率
    print(f"    工具调用正确率       : {_rate('tool_call')}")
    print(f"    禁忌工具遵守率       : {_rate('forbidden_tool')}")
    print(f"    意图路由正确率       : {_rate('intent')}")
    print(f"    成员隔离正确率       : {_rate('member_isolation')}")
    print(f"    证据命中率           : {_rate('evidence_hit')}")
    print(f"    安全规则通过率       : {_rate('safety_rule')}")
    print(f"    商品标签合规率       : {_rate('forbidden_product_tags')}")
    print(f"    输出结构合规率       : {_rate('response_schema')}")

    # 平均延迟
    latencies = [r.latency_ms for r in results if r.latency_ms]
    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"    平均延迟             : {avg:.0f}ms")


def _print_regression_diff(results: list[CaseResult], passed: int, failed: int) -> None:
    """Regression Diff：对比上一次运行结果。"""
    if not _LAST_RESULTS_PATH.exists():
        return

    try:
        last_data = json.loads(_LAST_RESULTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    last_total = last_data.get("total", 0)
    last_passed = last_data.get("passed", 0)
    last_failed = last_data.get("failed", 0)
    last_case_ids = set(last_data.get("passed_case_ids", []))
    last_failed_ids = set(last_data.get("failed_case_ids", []))

    current_passed_ids = {r.case.case_id for r in results if r.passed}
    current_failed_ids = {r.case.case_id for r in results if not r.passed}

    newly_failed = current_failed_ids & last_case_ids
    newly_fixed = current_passed_ids & last_failed_ids

    delta = passed - last_passed
    delta_str = f"+{delta}" if delta > 0 else str(delta)

    print("\n  Regression Diff (vs last run):")
    print(f"    上次: {last_passed}/{last_total} passed  |  本次: {passed}/{len(results)} passed  |  Δ: {delta_str}")

    if newly_failed:
        print(f"    🔴 新增失败 ({len(newly_failed)}): {', '.join(sorted(newly_failed))}")
    if newly_fixed:
        print(f"    🟢 新增修复 ({len(newly_fixed)}): {', '.join(sorted(newly_fixed))}")
    if not newly_failed and not newly_fixed:
        print("    ✅ 无变化")


def _save_results(results: list[CaseResult]) -> None:
    """保存本次结果供下次 diff。"""
    _LAST_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "passed_case_ids": [r.case.case_id for r in results if r.passed],
        "failed_case_ids": [r.case.case_id for r in results if not r.passed],
    }
    try:
        _LAST_RESULTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
