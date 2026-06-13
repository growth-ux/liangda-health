from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentMessagesResponse(BaseModel):
    items: list[AgentMessageItem]


class AgentSendResponse(BaseModel):
    user_message: AgentMessageItem
    assistant_message: AgentMessageItem


class QuickActionItem(BaseModel):
    label: str
    action: str
