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

EvidenceType = Literal["report_fact", "device", "memory", "product", "safety_block"]


class EvidenceItem(BaseModel):
    type: EvidenceType = "report_fact"
    title: str = Field(default="", max_length=80)
    excerpt: str = Field(..., min_length=1, max_length=200)
    source_id: str = Field(default="", max_length=80)
    source_label: str = Field(default="", max_length=120)

    @field_validator("excerpt", mode="before")
    @classmethod
    def _coerce_excerpt(cls, v):
        if isinstance(v, str) and len(v) > 200:
            return v[:200]
        return v

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if not isinstance(data, dict):
            return data
        # LLM 经常只输出 source + excerpt，需要映射到完整字段
        if "source" in data and "source_label" not in data:
            data["source_label"] = data["source"]
        if "source_id" not in data:
            data["source_id"] = data.get("source", data.get("source_label", "unknown"))
        if "title" not in data or not data.get("title"):
            data["title"] = data.get("source", data.get("source_label", "健康指标"))
        if "type" not in data:
            data["type"] = "report_fact"
        return data


class MessageEvidence(BaseModel):
    content_items: list[EvidenceItem] = Field(default_factory=list)
    product_items: list[EvidenceItem] = Field(default_factory=list)
    # 安全红线拦截记录：推荐过程中被过敏原/健康禁忌拦下的商品及原因
    safety_items: list[EvidenceItem] = Field(default_factory=list)
    # Context Pipeline 裁剪摘要：保留了多少条、裁剪了多少条、各来源分布
    pruning_summary: str | None = Field(default=None, max_length=200)


_PRIORITY_MAP = {
    "high": "primary",
    "medium": "secondary",
    "low": "secondary",
    "primary": "primary",
    "secondary": "secondary",
}


class SuggestionItem(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    priority: Literal["primary", "secondary"] = "primary"

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v):
        if isinstance(v, str):
            return _PRIORITY_MAP.get(v.lower(), "primary")
        return v


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
    advice: str = Field(..., min_length=1, max_length=1200)
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
    summary_text: str = Field(..., min_length=1, max_length=1200)
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
