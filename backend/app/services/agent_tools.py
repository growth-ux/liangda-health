import json
import logging
import re

from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.schemas.agent_response import EvidenceItem
from app.services.meal_plan_service import MealPlanService

logger = logging.getLogger(__name__)

# Context Compression: 报告 chunk 最大字符数，超出后在句边界截断
MAX_CHUNK_CONTENT_CHARS = 200


def _compress_chunk_content(content: str, max_chars: int = MAX_CHUNK_CONTENT_CHARS) -> str:
    """Context Compression：把长 chunk 压缩为结构化摘要，保留关键信息。

    策略：在句子边界截断，避免切断指标数值或证据短句。
    """
    content = content.strip()
    if len(content) <= max_chars:
        return content

    truncated = content[:max_chars]

    # 在句边界截断：优先 。！？；\n，其次 ，、
    best = 0
    for sep in ('。', '！', '？', '；', '\n', '，', '、'):
        pos = truncated.rfind(sep)
        if pos > best:
            best = pos

    if best > max_chars // 3:
        return truncated[:best + 1].strip()

    return truncated.rstrip() + '…'


def _normalize_evidence_excerpt(text: str, *, max_length: int = 160, strip_square_tags: bool = False) -> str:
    normalized = text.replace("\n", " ").strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if strip_square_tags:
        normalized = re.sub(r"\[[^\]]+\]\s*", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:max_length]


class KbSearchTool:
    def __init__(
        self,
        repository: SqlAlchemyKbRepository,
        embedding_service=None,
        vector_store=None,
        allowed_member_ids: list[str] | None = None,
        embedding_service_factory=None,
        vector_store_factory=None,
        evidence_collector=None,
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.allowed_member_ids = set(allowed_member_ids or [])
        self.embedding_service_factory = embedding_service_factory
        self.vector_store_factory = vector_store_factory
        self.evidence_collector = evidence_collector

    def search(self, query: str, member_id: str, top_k: int = 5) -> str:
        if not member_id:
            logger.info("kb_search rejected reason=missing_member_id")
            return "Error: 必须传入 member_id"
        if member_id not in self.allowed_member_ids:
            logger.info("kb_search rejected reason=member_not_allowed member_id=%s", member_id)
            return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        try:
            embedding_service = self._embedding_service()
            vector_store = self._vector_store()
            logger.info(
                "kb_search embedding start member_id=%s top_k=%s query_chars=%s",
                member_id,
                top_k,
                len(query),
            )
            embedding = embedding_service.embed(query)
            logger.info("kb_search embedding done member_id=%s", member_id)
            hits = vector_store.search(embedding, top_k, member_id=member_id)
            chunks = self.repository.get_chunks_by_ids([hit.chunk_id for hit in hits])
        except Exception as exc:
            logger.exception("kb_search failed member_id=%s top_k=%s", member_id, top_k)
            return f"Error: 检索失败 {exc}"

        parts = []
        for index, chunk in enumerate(chunks, start=1):
            document = self.repository.get_document(chunk.document_id)
            title = (document.title or document.file_name) if document is not None else chunk.document_id
            compressed = _compress_chunk_content(chunk.content)
            parts.append(
                f"[报告片段 {index}]\n"
                f"文档：{title}\n"
                f"页码：{chunk.page_no}\n"
                f"内容：{compressed}"
            )
        # 证据只收第一条：一次返回多 chunk 时右栏只展示主依据，避免塞满。
        if self.evidence_collector is not None and chunks:
            first_chunk = chunks[0]
            document = self.repository.get_document(first_chunk.document_id)
            title = (document.title or document.file_name) if document is not None else first_chunk.document_id
            self.evidence_collector.add_content(
                EvidenceItem(
                    type="report_fact",
                    title=title[:80] if title else first_chunk.document_id,
                    excerpt=_normalize_evidence_excerpt(first_chunk.content, max_length=180),
                    source_id=first_chunk.chunk_id,
                    source_label=f"{document.file_name} p{first_chunk.page_no}" if document is not None else first_chunk.document_id,
                )
            )
        logger.info("kb_search done member_id=%s hit_count=%s chunk_count=%s", member_id, len(hits), len(chunks))
        return "\n\n".join(parts)

    def _embedding_service(self):
        if self.embedding_service is None and self.embedding_service_factory is not None:
            self.embedding_service = self.embedding_service_factory()
        return self.embedding_service

    def _vector_store(self):
        if self.vector_store is None and self.vector_store_factory is not None:
            self.vector_store = self.vector_store_factory()
        return self.vector_store


class MealPlanTool:
    def __init__(self, service: MealPlanService, allowed_member_ids: list[str], evidence_collector=None):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)
        self.evidence_collector = evidence_collector

    def build(
        self,
        *,
        scope: str,
        member_id: str | None = None,
        goal: str | None = None,
        meal_type: str = "day",
    ) -> str:
        if scope not in {"member", "family"}:
            logger.info("meal_plan rejected reason=invalid_scope scope=%s", scope)
            return "Error: scope 只能是 member 或 family"
        if scope == "member":
            if not member_id:
                logger.info("meal_plan rejected reason=missing_member_id")
                return "Error: 单人餐单必须传入 member_id"
            if member_id not in self.allowed_member_ids:
                logger.info("meal_plan rejected reason=member_not_allowed member_id=%s", member_id)
                return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        result = self.service.build(scope=scope, member_id=member_id, goal=goal, meal_type=meal_type)
        if self.evidence_collector is not None:
            for item in self.service.get_evidence_items(scope=scope, member_id=member_id):
                self.evidence_collector.add_content(item)
        logger.info(
            "meal_plan done scope=%s member_id=%s meal_type=%s output_chars=%s",
            scope,
            member_id,
            meal_type,
            len(result),
        )
        return result


class MemorySearchTool:
    def __init__(self, service, evidence_collector=None):
        self.service = service
        self.evidence_collector = evidence_collector

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        if not query.strip():
            logger.info("memory_search rejected reason=blank_query")
            return "Error: query 不能为空"
        result = self.service.search_text(query=query, member_id=member_id, limit=limit)
        if self.evidence_collector is not None:
            self.evidence_collector.add_content(
                EvidenceItem(
                    type="memory",
                    title=f"关于「{query}」的互动记忆",
                    excerpt=_normalize_evidence_excerpt(str(result), strip_square_tags=True),
                    source_id=f"memory:{member_id or 'family'}:{query}",
                    source_label="互动记忆",
                )
            )
        logger.info(
            "memory_search done member_id=%s limit=%s output_chars=%s",
            member_id,
            limit,
            len(result),
        )
        return result


class MallRecommendTool:
    def __init__(self, service, allowed_member_ids: list[str], evidence_collector=None):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)
        self.evidence_collector = evidence_collector

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        query_text: str = "",
        limit: int = 5,
    ) -> str:
        # 工具返回值必须是字符串（LangChain tool 协议），但 service 现在返回结构化 dict。
        # 成功路径：dict → JSON 字符串，agent runner 拦截 ToolMessage 后按结构解析。
        # 错误路径：仍然以 "Error: ..." 字符串返回，runner 会因 JSON 解析失败而忽略。
        if scope not in {"member", "family"}:
            logger.info("mall_recommend rejected reason=invalid_scope scope=%s", scope)
            return "Error: scope 只能是 member 或 family"
        if scope == "member":
            if not member_id:
                logger.info("mall_recommend rejected reason=missing_member_id")
                return "Error: 单人商品推荐必须传入 member_id"
            if member_id not in self.allowed_member_ids:
                logger.info("mall_recommend rejected reason=member_not_allowed member_id=%s", member_id)
                return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        result = self.service.recommend(
            scope=scope,
            member_id=member_id,
            meal_plan_text=meal_plan_text,
            query_text=query_text,
            limit=limit,
        )
        if self.evidence_collector is not None:
            for item in result.get("items") or []:
                self.evidence_collector.add_product(
                    EvidenceItem(
                        type="product",
                        title=item["name"],
                        excerpt=_normalize_evidence_excerpt(item.get("reason", "")),
                        source_id=item["product_id"],
                        source_label=item.get("evidence_source") or "商城标签匹配",
                    )
                )
            # 安全红线拦截记录：让评委/用户看见哪些商品被过敏原和健康禁忌挡掉了
            for blocked in result.get("blocked_items") or []:
                title = (blocked.get("name") or "未知商品").strip() or "未知商品"
                excerpt = _normalize_evidence_excerpt(blocked.get("reason") or "安全红线拦截")
                if not excerpt:
                    excerpt = "安全红线拦截"
                self.evidence_collector.add_safety_block(
                    EvidenceItem(
                        type="safety_block",
                        title=title[:80],
                        excerpt=excerpt,
                        source_id=f"blocked:{blocked.get('product_id', 'unknown')}",
                        source_label="安全红线拦截",
                    )
                )
        payload = json.dumps(result, ensure_ascii=False)
        logger.info(
            "mall_recommend done scope=%s member_id=%s item_count=%s blocked_count=%s is_error=%s",
            scope,
            member_id,
            len(result.get("items") or []),
            len(result.get("blocked_items") or []),
            result.get("is_error"),
        )
        return payload
