from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MetricType = Literal[
    "systolic_bp", "diastolic_bp", "heart_rate", "steps", "sleep_hours", "blood_oxygen",
    "health_fact", "health_trend", "recheck",
]
Operator = Literal[">", "<", ">=", "<="]
Channel = Literal["in_app", "sms", "both"]


class AlertRuleItem(BaseModel):
    rule_id: str
    member_id: str
    member_name: str | None = None
    member_relation: str | None = None
    metric_type: MetricType
    metric_type_text: str = ""
    operator: Operator
    threshold: int
    channel: Channel
    enabled: bool
    created_at: datetime


class AlertRuleCreateRequest(BaseModel):
    member_id: str
    metric_type: MetricType
    operator: Operator
    threshold: int
    channel: Channel = "in_app"


class AlertRuleUpdateRequest(BaseModel):
    metric_type: MetricType | None = None
    operator: Operator | None = None
    threshold: int | None = None
    channel: Channel | None = None
    enabled: bool | None = None


class AlertRuleListResponse(BaseModel):
    rules: list[AlertRuleItem] = Field(default_factory=list)
    member_coverage: dict[str, bool] = Field(default_factory=dict)


class SmsConfigItem(BaseModel):
    id: int
    provider: str
    api_key: str
    api_secret: str
    signature: str
    template_id: str
    enabled: bool
    created_at: datetime


class SmsConfigSaveRequest(BaseModel):
    provider: str
    api_key: str
    api_secret: str
    signature: str
    template_id: str
    enabled: bool = True


class SmsConfigResponse(BaseModel):
    config: SmsConfigItem | None = None


class SmsTestRequest(BaseModel):
    phone: str


class SmsTestResponse(BaseModel):
    status: str
    message: str


class SmsLogItem(BaseModel):
    id: int
    rule_id: str
    member_id: str
    phone: str
    content: str
    status: str
    created_at: datetime


class SmsLogListResponse(BaseModel):
    logs: list[SmsLogItem] = Field(default_factory=list)
