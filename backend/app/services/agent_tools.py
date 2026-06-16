import json
import logging

from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.services.meal_plan_service import MealPlanService

logger = logging.getLogger(__name__)


class KbSearchTool:
    def __init__(
        self,
        repository: SqlAlchemyKbRepository,
        embedding_service=None,
        vector_store=None,
        allowed_member_ids: list[str] | None = None,
        embedding_service_factory=None,
        vector_store_factory=None,
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.allowed_member_ids = set(allowed_member_ids or [])
        self.embedding_service_factory = embedding_service_factory
        self.vector_store_factory = vector_store_factory

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
            title = document.title or document.file_name if document is not None else chunk.document_id
            parts.append(
                f"[报告片段 {index}]\n"
                f"文档：{title}\n"
                f"页码：{chunk.page_no}\n"
                f"内容：{chunk.content}"
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
    def __init__(self, service: MealPlanService, allowed_member_ids: list[str]):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)

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
        logger.info(
            "meal_plan done scope=%s member_id=%s meal_type=%s output_chars=%s",
            scope,
            member_id,
            meal_type,
            len(result),
        )
        return result


class MemorySearchTool:
    def __init__(self, service):
        self.service = service

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        if not query.strip():
            logger.info("memory_search rejected reason=blank_query")
            return "Error: query 不能为空"
        result = self.service.search_text(query=query, member_id=member_id, limit=limit)
        logger.info(
            "memory_search done member_id=%s limit=%s output_chars=%s",
            member_id,
            limit,
            len(result),
        )
        return result


class MallRecommendTool:
    def __init__(self, service, allowed_member_ids: list[str]):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 5,
    ) -> str:
        # 工具返回值必须是字符串（LangChain tool 协议），但 service 现在返回结构化 dict。
        # 成功路径：dict → JSON 字符串，agent runner 拦截 ToolMessage 后按结构解析。
        # 错误路径：仍然以 "Error: ..." 字符串返回，runner 会因 JSON 解析失败而忽略。
        if scope not in {"member", "family"}:
            logger.info("mall_recommend rejected reason=invalid_scope scope=%s", scope)
            return "Error: scope 只能是 member 或 family"
        if not meal_plan_text.strip():
            logger.info("mall_recommend rejected reason=blank_meal_plan")
            return "Error: meal_plan_text 不能为空"
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
            limit=limit,
        )
        payload = json.dumps(result, ensure_ascii=False)
        logger.info(
            "mall_recommend done scope=%s member_id=%s item_count=%s is_error=%s",
            scope,
            member_id,
            len(result.get("items") or []),
            result.get("is_error"),
        )
        return payload
