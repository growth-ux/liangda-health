from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.session import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, default="in_app")
    enabled: Mapped[str] = mapped_column(String(5), nullable=False, default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class SmsConfig(Base):
    __tablename__ = "sms_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    api_key: Mapped[str] = mapped_column(String(200), nullable=False)
    api_secret: Mapped[str] = mapped_column(String(200), nullable=False)
    signature: Mapped[str] = mapped_column(String(100), nullable=False)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[str] = mapped_column(String(5), nullable=False, default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class SmsLog(Base):
    __tablename__ = "sms_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
