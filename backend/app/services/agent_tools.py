from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.services.meal_plan_service import MealPlanService


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
            return "Error: 必须传入 member_id"
        if member_id not in self.allowed_member_ids:
            return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        try:
            embedding_service = self._embedding_service()
            vector_store = self._vector_store()
            embedding = embedding_service.embed(query)
            hits = vector_store.search(embedding, top_k, member_id=member_id)
            chunks = self.repository.get_chunks_by_ids([hit.chunk_id for hit in hits])
        except Exception as exc:
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
            return "Error: scope 只能是 member 或 family"
        if scope == "member":
            if not member_id:
                return "Error: 单人餐单必须传入 member_id"
            if member_id not in self.allowed_member_ids:
                return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        return self.service.build(scope=scope, member_id=member_id, goal=goal, meal_type=meal_type)


class MemorySearchTool:
    def __init__(self, service):
        self.service = service

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        if not query.strip():
            return "Error: query 不能为空"
        return self.service.search_text(query=query, member_id=member_id, limit=limit)
