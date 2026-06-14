from sqlalchemy import inspect

from app.db.session import Base
from app.models.kb import KbChunk, KbDocument


def test_kb_document_member_id_is_not_nullable():
    column = inspect(KbDocument).columns["member_id"]
    assert column.nullable is False


def test_kb_chunk_has_member_id_column():
    columns = {col.name for col in inspect(KbChunk).columns}
    assert "member_id" in columns
    column = inspect(KbChunk).columns["member_id"]
    assert column.nullable is False
    assert column.index is True