from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentSessionCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=255)


class AgentSessionCreateResponse(BaseModel):
    session_id: str
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentSessionListItem(BaseModel):
    session_id: str
    title: str
    preview: str
    updated_at: datetime


class AgentMessageSendRequest(BaseModel):
    content: str


class AgentMessageItem(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    status: str
    product_recommendations: list[dict] | None = None
    card: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("product_recommendations", mode="before")
    @classmethod
    def _parse_product_recommendations(cls, value):
        # ORM 里存的是 JSON 字符串；None 和已是 list/dict 的直接放过
        if value is None or isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            import json

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, list) else None
        return None

    @field_validator("card", mode="before")
    @classmethod
    def _parse_card(cls, value):
        # ORM 里存的是 JSON 字符串；None / 已是 dict / 解析失败 → None
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            import json

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None


class AgentMessagesResponse(BaseModel):
    items: list[AgentMessageItem]


class AgentSendResponse(BaseModel):
    user_message: AgentMessageItem
    assistant_message: AgentMessageItem


class QuickActionItem(BaseModel):
    label: str
    action: str
