"""端到端验证：上传 → 检索 → 跨家人隔离正确性。"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.kb import get_embedding_service, get_vector_store
from app.core.config import settings
from app.db.session import Base, get_db
from app.main import create_app
from app.models.kb import KbChunk, KbDocument
from app.models.member import Member
from app.services.embedding import DashScopeEmbeddingService


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k, member_id=None):
        self.calls.append(member_id)
        if member_id is None:
            raise ValueError("member_id required")
        if member_id == "mem_1":
            return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]
        return []


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0, 0.0]


@pytest.fixture
def db_session():
    engine = create_engine(settings.test_database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed(session):
    session.add_all([
        Member(
            member_id="mem_1", name="张三", relation="本人", gender="男", birth_year=1990,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        ),
        Member(
            member_id="mem_2", name="李四", relation="父亲", gender="男", birth_year=1965,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        ),
        KbDocument(
            document_id="doc_1", file_name="zhang.pdf", file_path="/tmp/zhang.pdf",
            file_size=10, member_id="mem_1", status="ready",
            patient_name="张三", title="张三体检",
        ),
        KbDocument(
            document_id="doc_2", file_name="li.pdf", file_path="/tmp/li.pdf",
            file_size=10, member_id="mem_2", status="ready",
            patient_name="李四", title="李四体检",
        ),
        KbChunk(
            chunk_id="chunk_1", document_id="doc_1", member_id="mem_1",
            page_no=1, content="张三血糖偏高",
        ),
        KbChunk(
            chunk_id="chunk_2", document_id="doc_2", member_id="mem_2",
            page_no=1, content="李四血压偏高",
        ),
    ])
    session.commit()


def test_search_only_returns_target_member_chunks(db_session):
    """跨家人检索：A 上传的内容不会被 B 的检索召回。"""
    _seed(db_session)
    vector_store = FakeVectorStore()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post(
        "/api/kb/search",
        json={"query": "血糖", "member_id": "mem_2", "top_k": 5},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert vector_store.calls == ["mem_2"]


def test_search_returns_target_member_chunks(db_session):
    _seed(db_session)
    vector_store = FakeVectorStore()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post(
        "/api/kb/search",
        json={"query": "血糖", "member_id": "mem_1", "top_k": 5},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["chunk_id"] == "chunk_1"
    assert items[0]["content"] == "张三血糖偏高"


def test_search_requires_member_id(db_session):
    _seed(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post("/api/kb/search", json={"query": "血糖", "top_k": 5})

    assert response.status_code == 422
