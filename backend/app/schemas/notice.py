from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


NoticeCategory = Literal["health_alert", "system", "recommendation", "reminder"]
NoticeLevel = Literal["danger", "warning", "info", "success"]
NoticeStatus = Literal["unread", "read", "snoozed", "done"]


class NoticeItem(BaseModel):
    notice_id: str
    category: NoticeCategory
    level: NoticeLevel
    title: str
    description: str
    source: str
    source_text: str
    status: NoticeStatus
    created_at: datetime
    meta_text: str
    target_url: str | None = None
    action_text: str | None = None
    secondary_action: str | None = None


class NoticeGroup(BaseModel):
    label: str
    items: list[NoticeItem] = Field(default_factory=list)


class NoticeCounts(BaseModel):
    all: int = 0
    health_alert: int = 0
    system: int = 0
    recommendation: int = 0
    unread: int = 0


class NoticeListResponse(BaseModel):
    counts: NoticeCounts
    groups: list[NoticeGroup] = Field(default_factory=list)


class NoticeSummaryResponse(BaseModel):
    unread: int


class NoticeReadAllResponse(BaseModel):
    updated: int
