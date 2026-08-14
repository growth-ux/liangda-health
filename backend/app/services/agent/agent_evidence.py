from __future__ import annotations

import logging
import re

from app.schemas.agent_response import EvidenceItem, MessageEvidence
from app.services.agent.context_pipeline import DroppedItem, PruningLog

logger = logging.getLogger(__name__)


class AgentEvidenceCollector:
    def __init__(self) -> None:
        self.content_items: list[EvidenceItem] = []
        self.product_items: list[EvidenceItem] = []
        self.safety_items: list[EvidenceItem] = []
        self.pruning_logs: list[PruningLog] = []

    def add_content(self, item: EvidenceItem) -> None:
        self._append_unique(self.content_items, item)

    def add_product(self, item: EvidenceItem) -> None:
        self._append_unique(self.product_items, item)

    def add_safety_block(self, item: EvidenceItem) -> None:
        self._append_unique(self.safety_items, item)

    def add_pruning_log(self, log: PruningLog) -> None:
        """记录一次 Pipeline 的裁剪结果。"""
        self.pruning_logs.append(log)
        logger.info(
            "evidence_collector pruning_log %s",
            log.summary(),
        )

    def dump(self) -> MessageEvidence | None:
        if not self.content_items and not self.product_items and not self.safety_items:
            return None
        return MessageEvidence(
            content_items=self.content_items,
            product_items=self.product_items,
            safety_items=self.safety_items,
            pruning_summary=self._pruning_summary(),
        )

    def _append_unique(self, items: list[EvidenceItem], candidate: EvidenceItem) -> None:
        candidate_excerpt = _normalize_excerpt(candidate.excerpt)
        for item in items:
            if item.type != candidate.type:
                continue
            if item.source_id == candidate.source_id:
                return
            if candidate_excerpt and _normalize_excerpt(item.excerpt) == candidate_excerpt:
                return
        items.append(candidate)

    def _pruning_summary(self) -> str | None:
        if not self.pruning_logs:
            return None
        total_kept = sum(log.kept_count for log in self.pruning_logs)
        total_dropped = sum(log.dropped_count for log in self.pruning_logs)
        total_tokens = sum(log.kept_tokens for log in self.pruning_logs)
        if total_dropped == 0:
            return f"上下文装配 {total_kept} 条，token≈{total_tokens}，未裁剪"
        dropped_sources: dict[str, int] = {}
        for log in self.pruning_logs:
            for d in log.dropped:
                dropped_sources[d.item.source] = dropped_sources.get(d.item.source, 0) + 1
        dropped_desc = "、".join(f"{s}:{c}" for s, c in sorted(dropped_sources.items()))
        return f"上下文装配 {total_kept} 条（token≈{total_tokens}），裁剪 {total_dropped} 条（{dropped_desc}）"


def _normalize_excerpt(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return normalized
