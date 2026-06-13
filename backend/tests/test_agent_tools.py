from datetime import datetime

from app.models.kb import KbChunk, KbDocument
from app.services.agent_tools import KbSearchTool


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0]


class FakeVectorStore:
    def search(self, query_embedding, top_k):
        return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]


class FakeKbRepository:
    def __init__(self):
        self.requested_ids = []

    def get_chunks_by_ids(self, chunk_ids):
        self.requested_ids = chunk_ids
        return [
            KbChunk(
                chunk_id="chunk_1",
                document_id="doc_1",
                page_no=2,
                content="血压 152，偏高",
                created_at=datetime(2026, 6, 13, 10, 0, 0),
            )
        ]

    def get_document(self, document_id):
        return KbDocument(
            document_id=document_id,
            file_name="report.pdf",
            file_path="/tmp/report.pdf",
            file_size=128,
            page_count=2,
            title="妈妈体检报告",
            status="ready",
            created_at=datetime(2026, 6, 13, 10, 0, 0),
            updated_at=datetime(2026, 6, 13, 10, 0, 0),
        )


def test_kb_search_tool_searches_report_keywords():
    repository = FakeKbRepository()
    tool = KbSearchTool(repository, FakeEmbeddingService(), FakeVectorStore())

    result = tool.search("这份报告有什么异常？")

    assert repository.requested_ids == ["chunk_1"]
    assert "文档：妈妈体检报告" in result
    assert "页码：2" in result
    assert "血压 152，偏高" in result


def test_kb_search_tool_skips_unrelated_questions():
    repository = FakeKbRepository()
    tool = KbSearchTool(repository, FakeEmbeddingService(), FakeVectorStore())

    result = tool.search("今天吃什么？")

    assert result == ""
    assert repository.requested_ids == []
