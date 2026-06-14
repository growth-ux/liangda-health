from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base
from app.models.kb import KbChunk, KbDocument
from app.models.member import Member


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


def _seed_member(session, member_id, name):
    session.add(Member(
        member_id=member_id, name=name, relation="本人", gender="男", birth_year=1990,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    session.commit()


def _seed_document(session, document_id, member_id, patient_name):
    session.add(KbDocument(
        document_id=document_id, file_name="r.pdf", file_path="/tmp/r.pdf",
        file_size=10, member_id=member_id, status="ready",
        patient_name=patient_name, title="t",
    ))
    session.add(KbChunk(
        chunk_id=f"chunk_{document_id}", document_id=document_id,
        member_id=member_id, page_no=1, content="text",
    ))
    session.commit()


def test_migrate_remaps_default_to_matched_member(db_session):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "张三")

    from app.scripts.migrate_kb_member_binding import migrate
    report = migrate(db_session, dry_run=False)

    assert report["matched"] == 1
    assert report["unmatched"] == 0
    db_session.expire_all()
    doc = db_session.query(KbDocument).filter(KbDocument.document_id == "doc_1").one()
    assert doc.member_id == "mem_zhang"
    chunk = db_session.query(KbChunk).filter(KbChunk.chunk_id == "chunk_doc_1").one()
    assert chunk.member_id == "mem_zhang"


def test_migrate_reports_unmatched(db_session):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "钱七")

    from app.scripts.migrate_kb_member_binding import migrate
    report = migrate(db_session, dry_run=False)

    assert report["matched"] == 0
    assert report["unmatched"] == 1


def test_migrate_is_idempotent(db_session):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "张三")

    from app.scripts.migrate_kb_member_binding import migrate
    migrate(db_session, dry_run=False)
    report = migrate(db_session, dry_run=False)

    assert report["matched"] == 0
    assert report["unmatched"] == 0


def test_migrate_dry_run_does_not_modify(db_session):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "张三")

    from app.scripts.migrate_kb_member_binding import migrate
    report = migrate(db_session, dry_run=True)

    assert report["matched"] == 1
    db_session.expire_all()
    doc = db_session.query(KbDocument).filter(KbDocument.document_id == "doc_1").one()
    assert doc.member_id == "default"