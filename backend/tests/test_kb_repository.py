from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base
from app.models.kb import KbChunk, KbDocument
from app.models.member import Member
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.services.chunker import TextChunk


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


def _seed_members(session):
    session.add_all([
        Member(member_id="mem_1", name="张三", relation="本人", gender="男", birth_year=1990, created_at=datetime.utcnow()),
        Member(member_id="mem_2", name="李四", relation="父亲", gender="男", birth_year=1965, created_at=datetime.utcnow()),
    ])
    session.commit()


def test_save_chunks_writes_member_id(db_session):
    _seed_members(db_session)
    repo = SqlAlchemyKbRepository(db_session)
    repo.create_document(KbDocument(
        document_id="doc_1", file_name="r.pdf", file_path="/tmp/r.pdf",
        file_size=10, member_id="mem_1", status="processing",
    ))
    repo.save_chunks([
        TextChunk(chunk_id="c1", document_id="doc_1", member_id="mem_1", page_no=1, content="text"),
    ])

    db_session.expire_all()
    chunk = db_session.query(KbChunk).filter(KbChunk.chunk_id == "c1").one()
    assert chunk.member_id == "mem_1"


def test_list_documents_by_member_filters_correctly(db_session):
    _seed_members(db_session)
    repo = SqlAlchemyKbRepository(db_session)
    repo.create_document(KbDocument(
        document_id="doc_1", file_name="r1.pdf", file_path="/tmp/r1.pdf",
        file_size=10, member_id="mem_1", status="ready",
    ))
    repo.create_document(KbDocument(
        document_id="doc_2", file_name="r2.pdf", file_path="/tmp/r2.pdf",
        file_size=10, member_id="mem_2", status="ready",
    ))

    docs_mem_1 = repo.list_documents_by_member("mem_1")

    ids = [d.document_id for d in docs_mem_1]
    assert ids == ["doc_1"]


def test_get_chunks_by_member_returns_only_that_member(db_session):
    _seed_members(db_session)
    repo = SqlAlchemyKbRepository(db_session)
    repo.create_document(KbDocument(
        document_id="doc_1", file_name="r1.pdf", file_path="/tmp/r1.pdf",
        file_size=10, member_id="mem_1", status="ready",
    ))
    repo.create_document(KbDocument(
        document_id="doc_2", file_name="r2.pdf", file_path="/tmp/r2.pdf",
        file_size=10, member_id="mem_2", status="ready",
    ))
    repo.save_chunks([
        TextChunk(chunk_id="c1", document_id="doc_1", member_id="mem_1", page_no=1, content="a"),
        TextChunk(chunk_id="c2", document_id="doc_2", member_id="mem_2", page_no=1, content="b"),
    ])

    chunks = repo.get_chunks_by_member("mem_1")

    chunk_ids = [c.chunk_id for c in chunks]
    assert chunk_ids == ["c1"]