from datetime import datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.session import Base


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exam_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # NOTE: member_id 改为 NOT NULL。已有脏数据（NULL/'default'）由 Plan Task 10
    # （backend/scripts/migrate_kb_member_binding.py）回填后再施加约束。
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fact_extract_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    fact_extract_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class KbPage(Base):
    __tablename__ = "kb_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # NOTE: kb_chunks 新增 member_id。冗余存储以避免每次召回都 join kb_documents。
    # 已有 chunk 由 Plan Task 10 迁移脚本回填。
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
