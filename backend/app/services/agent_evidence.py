from __future__ import annotations

import re

from app.schemas.agent_response import EvidenceItem, MessageEvidence


class AgentEvidenceCollector:
    def __init__(self) -> None:
        self.content_items: list[EvidenceItem] = []
        self.product_items: list[EvidenceItem] = []

    def add_content(self, item: EvidenceItem) -> None:
        self._append_unique(self.content_items, item)

    def add_product(self, item: EvidenceItem) -> None:
        self._append_unique(self.product_items, item)

    def dump(self) -> MessageEvidence | None:
        if not self.content_items and not self.product_items:
            return None
        return MessageEvidence(
            content_items=self.content_items,
            product_items=self.product_items,
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


def _normalize_excerpt(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return normalized
