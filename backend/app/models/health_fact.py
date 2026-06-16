from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.session import Base


class HealthFact(Base):
    __tablename__ = "health_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="warning", index=True)
    source_document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
