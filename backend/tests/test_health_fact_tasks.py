from datetime import datetime

from app.models.health_fact import HealthFact
from app.models.kb import KbChunk, KbDocument, KbPage
from app.repositories.health_fact_repository import HealthFactCreate
from app.services.health_fact_tasks import extract_health_facts_for_document


def _seed_document(db_session, document_id: str = "doc_1") -> None:
    db_session.add(
        KbDocument(
            document_id=document_id,
            file_name="report.pdf",
            file_path="/tmp/report.pdf",
            file_size=128,
            page_count=1,
            title="体检报告",
            patient_name="王秀英",
            institution="市立医院",
            member_id="mem_1",
            status="ready",
            fact_extract_status="pending",
            fact_extract_error=None,
            created_at=datetime(2026, 6, 12, 10, 0, 0),
            updated_at=datetime(2026, 6, 12, 10, 0, 0),
        )
    )
    db_session.add(
        KbPage(
            document_id=document_id,
            page_no=1,
            text_content="骨密度 T 值 -2.1",
        )
    )
    db_session.add(
        KbChunk(
            chunk_id="chunk_1",
            document_id=document_id,
            page_no=1,
            member_id="mem_1",
            content="骨密度 T 值 -2.1",
        )
    )
    db_session.commit()


def test_extract_health_facts_task_saves_facts_and_marks_ready(db_session, monkeypatch):
    _seed_document(db_session)

    class FakeExtractor:
        def extract(self, *, document_id, member_id, pages, chunks):
            assert document_id == "doc_1"
            assert member_id == "mem_1"
            assert [page.page_no for page in pages] == [1]
            assert [chunk.chunk_id for chunk in chunks] == ["chunk_1"]
            return [
                HealthFactCreate(
                    fact_id="fact_1",
                    member_id=member_id,
                    fact_type="risk",
                    name="骨密度低",
                    value=None,
                    unit=None,
                    reference_range=None,
                    status="warning",
                    source_document_id=document_id,
                    source_page_no=1,
                    source_chunk_id="chunk_1",
                    evidence_text="骨密度 T 值 -2.1",
                )
            ]

    monkeypatch.setattr("app.services.health_fact_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.services.health_fact_tasks.HealthFactExtractor", FakeExtractor)

    extract_health_facts_for_document("doc_1")

    db_session.expire_all()
    document = db_session.query(KbDocument).filter(KbDocument.document_id == "doc_1").one()
    facts = db_session.query(HealthFact).filter(HealthFact.source_document_id == "doc_1").all()
    assert document.fact_extract_status == "ready"
    assert document.fact_extract_error is None
    assert len(facts) == 1
    assert facts[0].name == "骨密度低"


def test_extract_health_facts_task_marks_failed_when_extractor_raises(db_session, monkeypatch):
    _seed_document(db_session)

    class BrokenExtractor:
        def extract(self, *, document_id, member_id, pages, chunks):
            raise RuntimeError("LLM 调用失败")

    monkeypatch.setattr("app.services.health_fact_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.services.health_fact_tasks.HealthFactExtractor", BrokenExtractor)

    extract_health_facts_for_document("doc_1")

    db_session.expire_all()
    document = db_session.query(KbDocument).filter(KbDocument.document_id == "doc_1").one()
    facts = db_session.query(HealthFact).filter(HealthFact.source_document_id == "doc_1").all()
    assert document.fact_extract_status == "failed"
    assert document.fact_extract_error == "LLM 调用失败"
    assert facts == []
