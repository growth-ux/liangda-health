from pathlib import Path

from fastapi.testclient import TestClient

from app.api.kb import get_embedding_service, get_vector_store
from app.core.config import settings
from app.db.session import Base, get_db
from app.main import create_app
from app.models import kb as _kb_models
from app.services.vector_store import VectorHit


class FakeVectorStore:
    def __init__(self):
        self.records = []

    def upsert(self, records):
        self.records.extend(records)

    def search(self, query_embedding, top_k, member_id=None):
        hits = [
            VectorHit(chunk_id=record.chunk_id, score=sum(a * b for a, b in zip(query_embedding, record.embedding)))
            for record in self.records
            if record.member_id == member_id
        ]
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0, 0.0] if "Bone density" in text else [0.0, 1.0]

    def embed_many(self, texts):
        return [self.embed(text) for text in texts]


def test_upload_text_pdf_then_search_returns_source_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.test_database_url)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    vector_store = FakeVectorStore()
    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    member_response = client.post(
        "/api/members",
        json={
            "name": "WangXiuying",
            "relation": "母亲",
            "gender": "女",
            "birth_year": 1961,
            "health_tags": ["高血压"],
        },
    )
    assert member_response.status_code == 200
    member_id = member_response.json()["member_id"]

    pdf_path = tmp_path / "report.pdf"
    _write_text_pdf(
        pdf_path,
        "General Check Report\n"
        "Name: WangXiuying\n"
        "Exam Date: 2026-05-12\n"
        "Institution: CityHospital\n"
        "Bone density T score -2.1\n"
        + "report body " * 30,
    )

    with pdf_path.open("rb") as file:
        upload_response = client.post(
            "/api/kb/upload",
            data={"member_id": member_id},
            files={"file": ("report.pdf", file, "application/pdf")},
        )

    assert upload_response.status_code == 200
    assert upload_response.json()["status"] == "ready"
    assert upload_response.json()["page_count"] == 1
    assert upload_response.json()["chunk_count"] >= 1

    list_response = client.get("/api/kb/documents")
    assert list_response.status_code == 200
    assert list_response.json()[0]["patient_name"] == "WangXiuying"

    search_response = client.post(
        "/api/kb/search",
        json={"query": "Bone density", "member_id": member_id, "top_k": 3},
    )
    assert search_response.status_code == 200
    assert search_response.json()["items"]
    assert "Bone density" in search_response.json()["items"][0]["content"]

    Base.metadata.drop_all(bind=engine)


def _write_text_pdf(path: Path, text: str) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
