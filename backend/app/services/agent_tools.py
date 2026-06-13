from app.repositories.kb_repository import SqlAlchemyKbRepository


REPORT_KEYWORDS = ("报告", "体检", "指标", "血压", "血糖", "骨密度", "检验", "异常")


class KbSearchTool:
    def __init__(self, repository: SqlAlchemyKbRepository, embedding_service, vector_store):
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def should_search(self, query: str) -> bool:
        return any(keyword in query for keyword in REPORT_KEYWORDS)

    def search(self, query: str, top_k: int = 5) -> str:
        if not self.should_search(query):
            return ""
        try:
            embedding = self.embedding_service.embed(query)
            hits = self.vector_store.search(embedding, top_k)
            chunks = self.repository.get_chunks_by_ids([hit.chunk_id for hit in hits])
        except Exception:
            return ""

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
