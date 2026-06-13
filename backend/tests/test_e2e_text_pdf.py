from pathlib import Path

from fastapi.testclient import TestClient

from app.api.kb import get_vector_store
from app.core.config import settings
from app.db.session import Base, get_db
from app.main import create_app
from app.models import kb as _kb_models
from app.services.vector_store import InMemoryVectorStore


def test_upload_text_pdf_then_search_returns_source_chunk(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(settings, "database_url", database_url)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "milvus_enabled", False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    vector_store = InMemoryVectorStore()
    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    client = TestClient(app)

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
            "/kb/upload",
            files={"file": ("report.pdf", file, "application/pdf")},
        )

    assert upload_response.status_code == 200
    assert upload_response.json()["status"] == "ready"
    assert upload_response.json()["page_count"] == 1
    assert upload_response.json()["chunk_count"] >= 1

    list_response = client.get("/kb/documents")
    assert list_response.status_code == 200
    assert list_response.json()[0]["patient_name"] == "WangXiuying"

    search_response = client.post("/kb/search", json={"query": "Bone density", "top_k": 3})
    assert search_response.status_code == 200
    assert search_response.json()["items"]
    assert "Bone density" in search_response.json()["items"][0]["content"]


def _write_text_pdf(path: Path, text: str) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
