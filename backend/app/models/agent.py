from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.session import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="done")
    # 结构化商品推荐：mall_recommend 工具产出的 items，JSON 字符串。
    # 与 content 解耦，前端按结构直接渲染卡片，不再依赖"可选商品："字面量匹配。
    product_recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 结构化卡片：respond 工具的 StructuredResponse，JSON 字符串。
    # 与 content / product_recommendations 解耦，前端按结构直接渲染对应卡片。
    card: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
