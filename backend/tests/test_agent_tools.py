from datetime import datetime

from app.models.kb import KbChunk, KbDocument
from app.services.agent_tools import KbSearchTool


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0]


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k, member_id=None):
        self.calls.append(member_id)
        if member_id == "mem_1":
            return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]
        return []


class FakeKbRepository:
    def __init__(self):
        self.requested_ids = []

    def get_chunks_by_ids(self, chunk_ids):
        self.requested_ids = chunk_ids
        return [
            KbChunk(
                chunk_id="chunk_1",
                document_id="doc_1",
                member_id="mem_1",
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


def test_kb_search_tool_searches_with_member_id():
    repository = FakeKbRepository()
    tool = KbSearchTool(repository, FakeEmbeddingService(), FakeVectorStore(), allowed_member_ids=["mem_1"])

    result = tool.search(query="爸爸血糖", member_id="mem_1")

    assert repository.requested_ids == ["chunk_1"]
    assert "文档：妈妈体检报告" in result
    assert "页码：2" in result
    assert "血压 152，偏高" in result


def test_kb_search_tool_rejects_unknown_member_id():
    vector_store = FakeVectorStore()
    tool = KbSearchTool(FakeKbRepository(), FakeEmbeddingService(), vector_store, allowed_member_ids=["mem_1"])

    result = tool.search(query="爸爸血糖", member_id="mem_unknown")

    assert "Error" in result
    assert "不在可用家人列表中" in result
    assert vector_store.calls == []  # 没调用 vector store


def test_kb_search_tool_filters_by_member_id_in_vector_store():
    vector_store = FakeVectorStore()
    tool = KbSearchTool(FakeKbRepository(), FakeEmbeddingService(), vector_store, allowed_member_ids=["mem_1", "mem_2"])

    tool.search(query="爸爸血糖", member_id="mem_2")

    assert vector_store.calls == ["mem_2"]


class FakeMemoryService:
    def __init__(self):
        self.calls = []

    def search_text(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return "[avoidance] 爸爸不喜欢鱼"


def test_memory_search_tool_returns_memory_text():
    from app.services.agent_tools import MemorySearchTool

    service = FakeMemoryService()
    tool = MemorySearchTool(service)

    result = tool.search(query="爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert service.calls == [("爸爸 饮食 排斥", "mem_dad", 3)]
    assert "爸爸不喜欢鱼" in result


def test_memory_search_tool_rejects_empty_query():
    from app.services.agent_tools import MemorySearchTool

    service = FakeMemoryService()
    tool = MemorySearchTool(service)

    result = tool.search(query="   ")

    assert result == "Error: query 不能为空"
    assert service.calls == []
