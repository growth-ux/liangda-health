"""Context Engineering Pipeline：Ranking + Budgeting + Pruning。

把来自不同数据源的上下文统一为 ContextItem，按优先级排序、
按类型分配 token 预算、超预算时裁剪低优先级项，并记录裁剪日志。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── 优先级常量 ──────────────────────────────────────────────
PRIORITY_SAFETY = 1000
PRIORITY_REPORT_FACT = 900
PRIORITY_DEVICE_ANOMALY = 700
PRIORITY_MEMBER_CONSTRAINT = 500
PRIORITY_MEMBER_PROFILE = 400
PRIORITY_MEMORY = 300
PRIORITY_PRODUCT = 200
PRIORITY_CHAT_HISTORY = 100


# ── 默认预算（token 数）────────────────────────────────────
DEFAULT_BUDGET_BY_SOURCE: dict[str, int] = {
    "safety": 600,
    "report_fact": 800,
    "device_anomaly": 400,
    "member_constraint": 500,
    "member_profile": 400,
    "memory": 400,
    "product": 600,
    "chat_history": 300,
}

DEFAULT_TOTAL_BUDGET = 3500


# ── 数据结构 ────────────────────────────────────────────────
@dataclass(frozen=True)
class ContextItem:
    """一条上下文条目。

    source: 数据来源类型（对应 DEFAULT_BUDGET_BY_SOURCE 的 key）
    priority: 优先级分数，越高越重要
    content: 给 LLM 看的文本
    token_estimate: 预估 token 数
    evidence_id: 溯源标识（可选）
    metadata: 附加元数据（可选）
    """

    source: str
    priority: int
    content: str
    token_estimate: int = 0
    evidence_id: str | None = None
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if self.token_estimate == 0 and self.content:
            # 简易估算：中文约 1.5 token/字，英文约 0.25 token/word
            # 取字符数 * 0.6 作为折中估算
            object.__setattr__(self, "token_estimate", max(1, int(len(self.content) * 0.6)))


@dataclass(frozen=True)
class DroppedItem:
    """被裁剪的上下文条目及原因。"""

    item: ContextItem
    reason: str


@dataclass
class PruningLog:
    """Pipeline 处理结果：保留的 + 被裁剪的。"""

    kept: list[ContextItem] = field(default_factory=list)
    dropped: list[DroppedItem] = field(default_factory=list)

    @property
    def kept_tokens(self) -> int:
        return sum(item.token_estimate for item in self.kept)

    @property
    def kept_count(self) -> int:
        return len(self.kept)

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)

    def kept_by_source(self, source: str) -> list[ContextItem]:
        return [item for item in self.kept if item.source == source]

    def kept_text(self, *, separator: str = "\n") -> str:
        """把所有保留的上下文拼成一段文本。"""
        return separator.join(item.content for item in self.kept if item.content.strip())

    def summary(self) -> str:
        """返回一行摘要，方便日志打印。"""
        source_counts: dict[str, int] = {}
        for item in self.kept:
            source_counts[item.source] = source_counts.get(item.source, 0) + 1
        kept_desc = ", ".join(f"{s}:{c}" for s, c in sorted(source_counts.items()))
        return f"kept={self.kept_count}({kept_desc}) dropped={self.dropped_count} tokens={self.kept_tokens}"


@dataclass(frozen=True)
class ContextBudget:
    """上下文预算配置。"""

    limits: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_BUDGET_BY_SOURCE))
    total_limit: int = DEFAULT_TOTAL_BUDGET

    def limit_for(self, source: str) -> int:
        return self.limits.get(source, 300)


# ── Pipeline 核心 ──────────────────────────────────────────
class ContextPipeline:
    """Ranking + Budgeting + Pruning 三件套。

    用法：
        pipeline = ContextPipeline()
        result = pipeline.process(items)
        prompt = result.kept_text()
    """

    def __init__(self, budget: ContextBudget | None = None) -> None:
        self.budget = budget or ContextBudget()

    def process(self, items: list[ContextItem]) -> PruningLog:
        if not items:
            return PruningLog()

        # Step 4: Ranking — 按优先级降序排序
        ranked = sorted(items, key=lambda x: x.priority, reverse=True)

        # Step 5: Budgeting — 按类型分配 token 窗口
        budget_kept: list[ContextItem] = []
        budget_dropped: list[DroppedItem] = []
        used_by_source: dict[str, int] = {}

        for item in ranked:
            source_used = used_by_source.get(item.source, 0)
            source_limit = self.budget.limit_for(item.source)

            if source_used + item.token_estimate > source_limit:
                budget_dropped.append(DroppedItem(item=item, reason=f"source_budget_exceeded({item.source}:{source_used}/{source_limit})"))
                continue

            budget_kept.append(item)
            used_by_source[item.source] = source_used + item.token_estimate

        # Step 6: Pruning — 超总量时从最低优先级开始裁剪
        total_tokens = sum(item.token_estimate for item in budget_kept)

        if total_tokens <= self.budget.total_limit:
            logger.info(
                "context_pipeline done %s",
                PruningLog(kept=budget_kept, dropped=budget_dropped).summary(),
            )
            return PruningLog(kept=budget_kept, dropped=budget_dropped)

        # budget_kept 已经按优先级降序，从末尾（最低优先级）开始裁剪
        pruned_dropped: list[DroppedItem] = list(budget_dropped)
        pruned_kept: list[ContextItem] = []

        for item in budget_kept:
            current_total = sum(i.token_estimate for i in pruned_kept)
            if current_total + item.token_estimate <= self.budget.total_limit:
                pruned_kept.append(item)
            else:
                pruned_dropped.append(DroppedItem(item=item, reason=f"total_budget_exceeded({current_total}/{self.budget.total_limit})"))

        result = PruningLog(kept=pruned_kept, dropped=pruned_dropped)
        logger.info("context_pipeline pruned %s", result.summary())
        return result
