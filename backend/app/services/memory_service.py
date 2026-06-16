from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from collections.abc import Callable, Iterable

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryItem:
    content: str
    memory_type: str | None = None
    member_id: str | None = None


@dataclass(frozen=True)
class MemoryOwner:
    user_id: str
    member_id: str | None = None
    scope: str = "member"


class MemoryService:
    def __init__(
        self,
        client=None,
        family_user_id: str | None = None,
        member_provider: Callable[[], Iterable[object]] | None = None,
        enabled: bool | None = None,
    ):
        self._client = client
        self.family_user_id = family_user_id or settings.memory_family_user_id
        self.member_provider = member_provider or (lambda: [])
        self.enabled = settings.memory_enabled if enabled is None else enabled

    def add_from_user_message(self, content: str, *, member_id: str | None = None) -> None:
        if not self.enabled or not content.strip():
            return
        owner = self._resolve_owner(content, member_id=member_id)
        if owner is None:
            return
        prompt = (
            "只沉淀 preference、avoidance、goal、marketing_feedback。\n"
            "不要记录健康禁忌、诊断结论、报告事实或手环数据。\n"
            "记忆内容必须使用简体中文，不要翻译成英文。\n"
            f"记忆归属：{owner.user_id}\n"
            f"用户原话：{content.strip()}"
        )
        metadata = {"source": "agent_user_message", "scope": owner.scope}
        if owner.member_id:
            metadata["member_id"] = owner.member_id
        try:
            logger.info(
                "memory_add request start user_id=%s member_id=%s scope=%s content_chars=%s",
                owner.user_id,
                owner.member_id,
                owner.scope,
                len(content),
            )
            self._get_client().add(
                [{"role": "user", "content": prompt}],
                user_id=owner.user_id,
                metadata=metadata,
                prompt=_memory_extraction_prompt(),
            )
            logger.info(
                "memory_add request done user_id=%s member_id=%s scope=%s",
                owner.user_id,
                owner.member_id,
                owner.scope,
            )
        except Exception:
            logger.exception("memory add failed")

    def search(self, query: str, *, member_id: str | None = None, limit: int = 5) -> list[MemoryItem]:
        if not self.enabled or not query.strip():
            return []
        filters = {"user_id": member_id or self.family_user_id}
        try:
            logger.info(
                "memory_search request start user_id=%s member_id=%s limit=%s query_chars=%s",
                filters["user_id"],
                member_id,
                limit,
                len(query),
            )
            raw_items = self._get_client().search(
                query.strip(),
                top_k=limit,
                filters=filters,
            )
        except Exception:
            logger.exception("memory search failed")
            return []
        items = [_to_memory_item(item) for item in _normalize_results(raw_items)]
        logger.info(
            "memory_search request done user_id=%s member_id=%s result_count=%s",
            filters["user_id"],
            member_id,
            len(items),
        )
        return items

    def search_text(self, query: str, *, member_id: str | None = None, limit: int = 5) -> str:
        items = self.search(query, member_id=member_id, limit=limit)
        if not items:
            return "未检索到相关记忆。"
        lines = []
        for item in items:
            label = item.memory_type or "memory"
            lines.append(f"[{label}] {item.content}")
        return "\n".join(lines)

    def list_profile_memories(self, *, member_id: str | None = None, limit: int = 50) -> list[MemoryItem]:
        if not self.enabled:
            return []
        filters = {"user_id": member_id or self.family_user_id}
        try:
            logger.info(
                "memory_list request start user_id=%s member_id=%s limit=%s",
                filters["user_id"],
                member_id,
                limit,
            )
            raw_items = self._get_client().get_all(filters=filters, top_k=limit)
        except Exception:
            logger.exception("memory list_profile_memories failed")
            return []
        items = [_to_memory_item(item) for item in _normalize_results(raw_items)]
        logger.info(
            "memory_list request done user_id=%s member_id=%s result_count=%s",
            filters["user_id"],
            member_id,
            len(items),
        )
        return items

    def _get_client(self):
        settings.memory_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MEM0_DIR", str(settings.memory_dir))
        os.environ.setdefault("MEM0_TELEMETRY", "false")
        if self._client is None:
            if settings.memory_provider != "mem0":
                raise RuntimeError(f"unsupported memory provider: {settings.memory_provider}")
            from mem0 import Memory

            self._client = Memory.from_config(_mem0_config())
        return self._client

    def _resolve_owner(self, content: str, *, member_id: str | None = None) -> MemoryOwner | None:
        if member_id:
            return MemoryOwner(user_id=member_id, member_id=member_id)
        normalized = content.strip()
        if _is_family_scope(normalized):
            return MemoryOwner(user_id=self.family_user_id, scope="family")
        for member in self.member_provider():
            candidate_id = getattr(member, "member_id", None)
            if not candidate_id:
                continue
            names = (
                getattr(member, "relation", None),
                getattr(member, "name", None),
                candidate_id,
            )
            if any(name and str(name) in normalized for name in names):
                return MemoryOwner(user_id=str(candidate_id), member_id=str(candidate_id))
        return None


def _mem0_config() -> dict:
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": settings.llm_model,
                "api_key": settings.llm_api_key,
                "openai_base_url": settings.llm_base_url,
                "temperature": settings.llm_temperature,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": settings.embedding_model,
                "api_key": settings.embedding_api_key,
                "openai_base_url": settings.llm_base_url,
                "embedding_dims": settings.embedding_dimension,
            },
        },
        "vector_store": {
            "provider": "milvus",
            "config": {
                "url": settings.milvus_uri,
                "token": settings.milvus_token or "",
                "collection_name": settings.memory_milvus_collection,
                "embedding_model_dims": settings.embedding_dimension,
                "metric_type": "COSINE",
            },
        },
        "history_db_path": str(settings.memory_history_db_path),
        "custom_instructions": (
            "只沉淀以下四类长期记忆：preference、avoidance、goal、marketing_feedback。\n"
            "preference 表示饮食、口味、商品或生活方式偏好。\n"
            "avoidance 表示不喜欢、排斥、不吃、不愿购买或负反馈。\n"
            "goal 表示阶段性健康、饮食、运动或控糖控脂目标。\n"
            "marketing_feedback 表示对推荐、商品、价格、品牌、购买意愿的反馈。\n"
            "不要记录健康禁忌、诊断结论、体检报告事实、手环数据、一次性闲聊或临时问题。\n"
            "如果用户消息没有上述四类长期记忆价值，返回空记忆。\n"
            "memory 字段必须使用简体中文，不要输出英文改写。"
        ),
    }


def _normalize_results(raw_items) -> list:
    if isinstance(raw_items, dict) and isinstance(raw_items.get("results"), list):
        return raw_items["results"]
    if isinstance(raw_items, list):
        return raw_items
    return []


def _is_family_scope(content: str) -> bool:
    family_words = ("全家", "我们家", "家里人", "一家人")
    return any(word in content for word in family_words)


def _memory_extraction_prompt() -> str:
    return (
        "从用户消息中抽取长期记忆，只保留 preference、avoidance、goal、marketing_feedback 四类。\n"
        "memory 字段必须使用简体中文，不要翻译成英文，不要使用 User/father/mother 等英文表达。\n"
        "如果没有长期记忆价值，返回空 memory 列表。"
    )


def _to_memory_item(item) -> MemoryItem:
    if isinstance(item, str):
        return MemoryItem(content=item)
    if not isinstance(item, dict):
        return MemoryItem(content=str(item))
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    content = item.get("memory") or item.get("text") or item.get("content") or ""
    return MemoryItem(
        content=str(content),
        memory_type=metadata.get("memory_type") or item.get("memory_type"),
        member_id=metadata.get("member_id") or item.get("member_id"),
    )
