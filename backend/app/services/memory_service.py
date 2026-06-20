from __future__ import annotations

import logging
import os
import re
from difflib import SequenceMatcher
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
        if _should_skip_memory_write(content):
            logger.info("memory_add skipped reason=filtered_by_rule content_chars=%s", len(content))
            return
        owner = self._resolve_owner(content, member_id=member_id)
        if owner is None:
            return
        prompt = (
            "只沉淀 preference、avoidance、marketing_feedback。\n"
            "不要记录健康禁忌、诊断结论、报告事实或手环数据。\n"
            "不要记录一次性推荐请求、当前问答意图、临时购买需求。\n"
            "不要记录围绕体检报告、异常指标、是否干预、健康风险解释的提问。\n"
            "不要记录长期目标、阶段目标、照护意图或对当前对话的总结性改写。\n"
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
        items = _dedupe_memory_items([_to_memory_item(item) for item in _normalize_results(raw_items)])
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
            "只沉淀以下三类长期记忆：preference、avoidance、marketing_feedback。\n"
            "preference 表示饮食、口味、商品或生活方式偏好。\n"
            "avoidance 表示不喜欢、排斥、不吃、不愿购买或负反馈。\n"
            "marketing_feedback 表示对推荐、商品、价格、品牌、购买意愿的反馈。\n"
            "不要记录健康禁忌、诊断结论、体检报告事实、手环数据、一次性闲聊或临时问题。\n"
            "不要记录一次性推荐请求、当前问答意图、临时购买需求。\n"
            "不要记录围绕体检报告、异常指标、是否干预、健康风险解释的提问。\n"
            "不要记录长期目标、阶段目标、照护意图或对当前对话的总结性改写。\n"
            "如果用户消息没有上述三类长期记忆价值，返回空记忆。\n"
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
        "从用户消息中抽取长期记忆，只保留 preference、avoidance、marketing_feedback 三类。\n"
        "memory 字段必须使用简体中文，不要翻译成英文，不要使用 User/father/mother 等英文表达。\n"
        "不要输出 goal，不要输出长期目标、阶段目标、照护意图或对当前对话的总结性改写。\n"
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


def _dedupe_memory_items(items: list[MemoryItem]) -> list[MemoryItem]:
    deduped: list[MemoryItem] = []
    for item in items:
        if not item.content.strip():
            continue
        if any(_is_similar_memory(item, existing) for existing in deduped):
            continue
        deduped.append(item)
    return deduped


def _is_similar_memory(left: MemoryItem, right: MemoryItem) -> bool:
    if left.member_id != right.member_id or left.memory_type != right.memory_type:
        return False
    left_text = _normalize_memory_text(left.content)
    right_text = _normalize_memory_text(right.content)
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    shorter_length = min(len(left_text), len(right_text))
    longer_length = max(len(left_text), len(right_text))
    if shorter_length >= 12 and (left_text in right_text or right_text in left_text):
        return shorter_length / longer_length >= 0.7
    if shorter_length < 20:
        return False
    return SequenceMatcher(None, left_text, right_text).ratio() >= 0.72


def _normalize_memory_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"[，。！？；：、“”‘’（）()\[\]【】,.!?;:]", "", normalized)
    return normalized


def _should_skip_memory_write(content: str) -> bool:
    normalized = content.strip()
    if not normalized:
        return True
    if _is_one_off_recommendation_request(normalized):
        return True
    if _is_health_fact_question(normalized):
        return True
    if _is_goal_like_message(normalized):
        return True
    if _is_preference_query(normalized):
        return True
    return False


def _is_preference_query(content: str) -> bool:
    """Detect preference/avoidance questions that should not be written to memory.

    用户问 "爸爸不喜欢吃什么" 这种偏好/排斥问句，本身不带新事实；
    让它走到 mem0.add 后 LLM 容易把检索结果二次写回向量库造成重复。
    命中条件：问句标记 + 偏好/排斥关键词。
    """
    question_markers = ("什么", "哪些", "啥", "吗", "呢", "?", "？")
    preference_words = (
        "喜欢", "爱", "想", "能", "可以", "适合", "愿意", "想要",
    )
    avoidance_words = (
        "不喜欢", "不爱", "不想", "不愿", "不能", "不应", "不可",
        "不要", "别", "忌", "过敏", "敏感", "不耐", "讨厌", "排斥", "抗拒",
    )
    if not any(marker in content for marker in question_markers):
        return False
    return any(word in content for word in preference_words + avoidance_words)


def _is_one_off_recommendation_request(content: str) -> bool:
    one_off_patterns = (
        r"推荐一款",
        r"推荐[一1]个",
        r"推荐.*食用油",
        r"适合.*食用油",
        r"适合.*吗",
        r"帮.*选.*(油|商品|产品)",
        r"想买.*(油|商品|产品)",
    )
    return any(re.search(pattern, content) for pattern in one_off_patterns)


def _is_health_fact_question(content: str) -> bool:
    health_fact_patterns = (
        r"血脂.*是否需要干预",
        r"血脂.*要不要干预",
        r"血脂偏高.*(怎么办|怎么处理|要不要管)",
        r"健康风险",
        r"报告.*(怎么看|解读|说明)",
        r"(指标|体检).*(异常|偏高|偏低)",
    )
    return any(re.search(pattern, content) for pattern in health_fact_patterns)


def _is_goal_like_message(content: str) -> bool:
    goal_like_patterns = (
        r"最近想",
        r"想控(糖|脂)",
        r"要控(糖|脂)",
        r"长期关注",
        r"阶段目标",
        r"长期目标",
        r"照护意图",
        r"关怀意图",
        r"体现出.*意图",
        r"安排今晚.*(晚餐|饮食)",
        r"晚餐安排",
    )
    return any(re.search(pattern, content) for pattern in goal_like_patterns)
