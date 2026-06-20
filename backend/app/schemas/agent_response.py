"""Agent 用户可见回复的结构化 schema。

LLM 必须调用 respond 工具并填入本 schema；前端按 kind 路由卡片。
所有 Pydantic 模型严格校验——失败即抛 ValidationError，不做兜底降级。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ===== 餐单 payload =====

class MealItem(BaseModel):
    slot: Literal["breakfast", "lunch", "dinner"] | None = None
    title: str = Field(..., min_length=1, max_length=80)
    summary: str = Field(..., max_length=120)


class MemberAdjustment(BaseModel):
    member_name: str = Field(..., min_length=1, max_length=40)
    note: str = Field(..., max_length=200)
    tags: list[str] = Field(default_factory=list)


class MealPlanPayload(BaseModel):
    scope: Literal["family", "member"]
    target_member_name: str | None = None
    meal_items: list[MealItem] = Field(..., min_length=1)
    member_adjustments: list[MemberAdjustment] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    extra_note: str | None = Field(default=None, max_length=200)


# ===== 一般问答 payload =====

class QaPayload(BaseModel):
    question_topic: str = Field(..., min_length=1, max_length=80)
    answer: str = Field(..., min_length=1, max_length=400)
    tips: list[str] = Field(default_factory=list)


# ===== 寒暄 payload =====

class GreetingPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=200)
    suggested_topics: list[str] = Field(default_factory=list)


# ===== 健康解读 payload =====

EvidenceType = Literal["report_fact", "device", "memory", "product"]


class EvidenceItem(BaseModel):
    type: EvidenceType
    title: str = Field(..., min_length=1, max_length=80)
    excerpt: str = Field(..., min_length=1, max_length=200)
    source_id: str = Field(..., min_length=1, max_length=80)
    source_label: str = Field(..., min_length=1, max_length=120)


class MessageEvidence(BaseModel):
    content_items: list[EvidenceItem] = Field(default_factory=list)
    product_items: list[EvidenceItem] = Field(default_factory=list)


class SuggestionItem(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    priority: Literal["primary", "secondary"] = "primary"


class KbInterpretationPayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    evidence: list[EvidenceItem] = Field(..., min_length=1)
    suggestions: list[SuggestionItem] = Field(..., min_length=1)
    red_flags: list[str] = Field(default_factory=list)

    @field_validator("suggestions", mode="before")
    @classmethod
    def normalize_suggestions(cls, value):
        if not isinstance(value, list):
            return value
        return [
            {"text": item, "priority": "primary"} if isinstance(item, str) else item
            for item in value
        ]


# ===== 一般建议 payload =====

class GeneralAdvicePayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    advice: str = Field(..., min_length=1, max_length=400)
    cautions: list[str] = Field(default_factory=list)


# ===== 顶层 Envelope（respond 工具的参数） =====

ResponseKind = Literal["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]


_PAYLOAD_MODELS = {
    "meal_plan": MealPlanPayload,
    "qa": QaPayload,
    "greeting": GreetingPayload,
    "kb_interpretation": KbInterpretationPayload,
    "general_advice": GeneralAdvicePayload,
}


class StructuredResponse(BaseModel):
    kind: ResponseKind
    summary_text: str = Field(..., min_length=1, max_length=400)
    payload: (
        MealPlanPayload
        | QaPayload
        | GreetingPayload
        | KbInterpretationPayload
        | GeneralAdvicePayload
    )
    evidence: MessageEvidence | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_payload_by_kind(cls, data):
        if not isinstance(data, dict):
            return data
        kind = data.get("kind")
        payload_model = _PAYLOAD_MODELS.get(kind)
        if payload_model is None or "payload" not in data:
            return data
        return {**data, "payload": payload_model.model_validate(data["payload"])}
