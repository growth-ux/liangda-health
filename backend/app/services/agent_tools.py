from app.repositories.kb_repository import SqlAlchemyKbRepository


class KbSearchTool:
    def __init__(
        self,
        repository: SqlAlchemyKbRepository,
        embedding_service,
        vector_store,
        allowed_member_ids: list[str],
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.allowed_member_ids = set(allowed_member_ids)

    def search(self, query: str, member_id: str, top_k: int = 5) -> str:
        if not member_id:
            return "Error: 必须传入 member_id"
        if member_id not in self.allowed_member_ids:
            return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        try:
            embedding = self.embedding_service.embed(query)
            hits = self.vector_store.search(embedding, top_k, member_id=member_id)
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