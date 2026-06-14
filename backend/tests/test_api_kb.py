from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.kb import get_embedding_service, get_vector_store
from app.core.config import settings
from app.db.session import get_db
from app.main import create_app
from app.models.kb import KbChunk, KbDocument, KbPage
from app.models.member import Member
from app.services.embedding import DashScopeEmbeddingService


class FakeQuery:
    def __init__(self, data):
        self.data = data

    def order_by(self, *args):
        return self

    def filter(self, *args):
        for condition in args:
            self.data = [item for item in self.data if _matches_filter(item, condition)]
        return self

    def all(self):
        return self.data

    def one_or_none(self):
        return self.data[0] if self.data else None


def _matches_filter(item, condition):
    left = getattr(condition, "left", None)
    right = getattr(condition, "right", None)
    if left is None or right is None:
        return True
    actual = getattr(item, left.key, None)
    expected = getattr(right, "value", right)
    from sqlalchemy.sql import operators
    if getattr(condition, "operator", None) is operators.in_op:
        return actual in expected
    return actual == expected


class FakeDb:
    def __init__(self):
        self.deleted = []
        self.document = KbDocument(
            document_id="doc_1",
            file_name="report.pdf",
            file_path="/tmp/report.pdf",
            file_size=128,
            page_count=1,
            title="体检报告",
            patient_name="王秀英",
            institution="市立医院",
            member_id="mem_1",
            status="ready",
            created_at=datetime(2026, 6, 12, 10, 0, 0),
            updated_at=datetime(2026, 6, 12, 10, 0, 0),
        )
        self.chunk = KbChunk(
            chunk_id="chunk_1",
            document_id="doc_1",
            page_no=1,
            content="骨密度 T 值 -2.1",
            created_at=datetime(2026, 6, 12, 10, 0, 0),
        )
        self.page = KbPage(
            document_id="doc_1",
            page_no=1,
            text_content="骨密度 T 值 -2.1",
            created_at=datetime(2026, 6, 12, 10, 0, 0),
        )

    def query(self, model):
        if model is KbDocument:
            return FakeQuery([self.document])
        if model is KbChunk:
            return FakeQuery([self.chunk])
        if model is KbPage:
            return FakeQuery([self.page])
        if model is Member:
            return FakeQuery([SimpleNamespace(member_id="mem_1", name="王秀英", relation="本人")])
        return FakeQuery([])

    def delete(self, item):
        self.deleted.append(item)

    def commit(self):
        pass

    def close(self):
        pass


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k, member_id=None):
        self.calls.append({"member_id": member_id})
        if member_id != "mem_1":
            return []
        return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0, 0.0]


def test_kb_document_list_and_detail_endpoints():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    list_response = client.get("/api/kb/documents")
    detail_response = client.get("/api/kb/documents/doc_1")

    assert list_response.status_code == 200
    assert list_response.json()[0]["document_id"] == "doc_1"
    assert list_response.json()[0]["member_id"] == "mem_1"
    assert list_response.json()[0]["member_name"] == "王秀英"
    assert list_response.json()[0]["thumbnail_url"] == "/uploads/doc_1/thumbnail.png"
    assert detail_response.status_code == 200
    assert detail_response.json()["file_name"] == "report.pdf"
    assert detail_response.json()["member_relation"] == "本人"
    assert detail_response.json()["thumbnail_url"] == "/uploads/doc_1/thumbnail.png"


def test_kb_document_chunks_endpoint_returns_document_chunks():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get("/api/kb/documents/doc_1/chunks")

    assert response.status_code == 200
    assert response.json()["items"][0]["chunk_id"] == "chunk_1"
    assert response.json()["items"][0]["page_no"] == 1
    assert response.json()["items"][0]["content"] == "骨密度 T 值 -2.1"


def test_kb_delete_document_removes_document_pages_and_chunks():
    db = FakeDb()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.delete("/api/kb/documents/doc_1")

    assert response.status_code == 204
    assert any(isinstance(item, KbDocument) for item in db.deleted)
    assert any(isinstance(item, KbPage) for item in db.deleted)
    assert any(isinstance(item, KbChunk) for item in db.deleted)


def test_kb_search_endpoint_returns_chunk_content():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post("/api/kb/search", json={"query": "骨密度", "member_id": "mem_1", "top_k": 5})

    assert response.status_code == 200
    assert response.json()["items"][0]["chunk_id"] == "chunk_1"
    assert response.json()["items"][0]["content"] == "骨密度 T 值 -2.1"


def test_kb_search_requires_member_id():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post("/api/kb/search", json={"query": "骨密度", "top_k": 5})

    assert response.status_code == 422


def test_kb_search_rejects_unknown_member_id():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post("/api/kb/search", json={"query": "骨密度", "member_id": "mem_unknown", "top_k": 5})

    assert response.status_code == 400
    assert response.json()["detail"] == "家人不存在"


def test_kb_upload_rejects_non_pdf_file():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/api/kb/upload",
        files={"file": ("report.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "只支持 PDF 文件"


def test_kb_upload_requires_member_id():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/api/kb/upload",
        files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请选择家人"


def test_kb_upload_rejects_pdf_content_type_with_non_pdf_extension():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/api/kb/upload",
        files={"file": ("report.txt", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "只支持 PDF 文件"


def test_get_embedding_service_uses_dashscope_with_existing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-v3")
    monkeypatch.setattr(settings, "embedding_api_key", None)
    monkeypatch.setattr(settings, "llm_api_key", "secret")

    service = get_embedding_service()

    assert isinstance(service, DashScopeEmbeddingService)
    assert service.model == "text-embedding-v3"
    assert service.api_key == "secret"
