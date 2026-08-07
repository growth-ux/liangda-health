"""context_pipeline 三件套单测：Ranking / Budgeting / Pruning。"""
import pytest

from app.services.context_pipeline import (
    ContextBudget,
    ContextItem,
    ContextPipeline,
    DroppedItem,
    PRIORITY_CHAT_HISTORY,
    PRIORITY_DEVICE_ANOMALY,
    PRIORITY_MEMBER_CONSTRAINT,
    PRIORITY_MEMBER_PROFILE,
    PRIORITY_MEMORY,
    PRIORITY_REPORT_FACT,
    PRIORITY_SAFETY,
)


# ── ContextItem ──────────────────────────────────────────


def test_context_item_auto_token_estimate():
    item = ContextItem(source="memory", priority=PRIORITY_MEMORY, content="这是一个测试内容")
    assert item.token_estimate > 0
    assert item.token_estimate == max(1, int(len("这是一个测试内容") * 0.6))


def test_context_item_explicit_token_estimate():
    item = ContextItem(source="memory", priority=PRIORITY_MEMORY, content="test", token_estimate=42)
    assert item.token_estimate == 42


def test_context_item_empty_content():
    item = ContextItem(source="memory", priority=PRIORITY_MEMORY, content="")
    assert item.token_estimate == 0


# ── Ranking ──────────────────────────────────────────────


def test_ranking_sorts_by_priority_descending():
    items = [
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="记忆"),
        ContextItem(source="safety", priority=PRIORITY_SAFETY, content="过敏原"),
        ContextItem(source="report_fact", priority=PRIORITY_REPORT_FACT, content="报告事实"),
    ]
    pipeline = ContextPipeline(budget=ContextBudget(total_limit=99999))
    result = pipeline.process(items)

    assert result.kept_count == 3
    assert result.kept[0].source == "safety"
    assert result.kept[1].source == "report_fact"
    assert result.kept[2].source == "memory"


def test_ranking_same_priority_stable():
    items = [
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="记忆1"),
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="记忆2"),
    ]
    pipeline = ContextPipeline(budget=ContextBudget(total_limit=99999))
    result = pipeline.process(items)
    assert result.kept_count == 2
    assert result.kept[0].content == "记忆1"
    assert result.kept[1].content == "记忆2"


# ── Budgeting ────────────────────────────────────────────


def test_budgeting_drops_items_exceeding_source_limit():
    budget = ContextBudget(limits={"memory": 10}, total_limit=99999)
    items = [
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="短"),  # ~1 token
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="这是一段比较长的记忆内容需要较多token"),
    ]
    pipeline = ContextPipeline(budget=budget)
    result = pipeline.process(items)

    # 第一条应该能放进去，第二条因为超出 memory budget 被丢弃
    assert result.kept_count >= 1
    assert any(d.reason.startswith("source_budget_exceeded") for d in result.dropped)


def test_budgeting_allows_different_sources_independently():
    budget = ContextBudget(limits={"memory": 5, "safety": 100}, total_limit=99999)
    items = [
        ContextItem(source="safety", priority=PRIORITY_SAFETY, content="过敏原花生"),
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="这是一段长记忆"),
    ]
    pipeline = ContextPipeline(budget=budget)
    result = pipeline.process(items)

    # safety 应该保留，memory 可能因为 budget 被丢
    safety_kept = result.kept_by_source("safety")
    assert len(safety_kept) == 1


# ── Pruning ──────────────────────────────────────────────


def test_pruning_drops_lowest_priority_when_over_total():
    budget = ContextBudget(
        limits={"safety": 999, "memory": 999, "product": 999},
        total_limit=15,
    )
    items = [
        ContextItem(source="safety", priority=PRIORITY_SAFETY, content="过敏原花生"),
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="偏好清淡饮食不吃辣不吃油腻的食物"),
        ContextItem(source="product", priority=PRIORITY_MEMORY - 100, content="推荐商品橄榄油低钠适合高血压家庭日常使用"),
    ]
    pipeline = ContextPipeline(budget=budget)
    result = pipeline.process(items)

    # safety 一定保留（最高优先级）
    assert any(i.source == "safety" for i in result.kept)
    # 低优先级的 product 最可能被裁剪
    assert any(d.item.source == "product" for d in result.dropped)
    assert any(d.reason.startswith("total_budget_exceeded") for d in result.dropped)


def test_pruning_keeps_all_when_under_budget():
    items = [
        ContextItem(source="safety", priority=PRIORITY_SAFETY, content="过敏"),
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content="清淡"),
    ]
    pipeline = ContextPipeline()  # 默认 budget 很大
    result = pipeline.process(items)

    assert result.kept_count == 2
    assert result.dropped_count == 0


# ── PruningLog ───────────────────────────────────────────


def test_pruning_log_kept_text():
    from app.services.context_pipeline import PruningLog

    log = PruningLog(
        kept=[
            ContextItem(source="safety", priority=1000, content="过敏原：花生"),
            ContextItem(source="memory", priority=300, content="偏好清淡"),
        ]
    )
    text = log.kept_text()
    assert "过敏原：花生" in text
    assert "偏好清淡" in text


def test_pruning_log_summary():
    from app.services.context_pipeline import PruningLog

    log = PruningLog(
        kept=[
            ContextItem(source="safety", priority=1000, content="a"),
            ContextItem(source="memory", priority=300, content="b"),
        ],
        dropped=[DroppedItem(item=ContextItem(source="product", priority=200, content="c"), reason="test")],
    )
    s = log.summary()
    assert "kept=2" in s
    assert "dropped=1" in s


def test_pruning_log_empty():
    from app.services.context_pipeline import PruningLog

    log = PruningLog()
    assert log.kept_count == 0
    assert log.dropped_count == 0
    assert log.kept_tokens == 0
    assert log.kept_text() == ""


# ── Pipeline edge cases ──────────────────────────────────


def test_pipeline_empty_input():
    pipeline = ContextPipeline()
    result = pipeline.process([])
    assert result.kept_count == 0
    assert result.dropped_count == 0


def test_pipeline_single_item():
    pipeline = ContextPipeline()
    result = pipeline.process([ContextItem(source="safety", priority=PRIORITY_SAFETY, content="过敏")])
    assert result.kept_count == 1
    assert result.dropped_count == 0


def test_pipeline_all_same_source():
    budget = ContextBudget(limits={"memory": 10}, total_limit=99999)
    items = [
        ContextItem(source="memory", priority=PRIORITY_MEMORY, content=f"这是一段比较长的记忆内容编号{i}包含饮食偏好") for i in range(20)
    ]
    pipeline = ContextPipeline(budget=budget)
    result = pipeline.process(items)

    # 应该有一些被 source budget 截掉
    assert result.dropped_count > 0
    assert all(d.reason.startswith("source_budget_exceeded") for d in result.dropped)
