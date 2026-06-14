from typing import Literal

from pydantic import BaseModel, Field


HealthLevel = Literal["danger", "warning", "success", "info"]


class HealthAnalysisFamily(BaseModel):
    name: str
    period_label: str


class HealthAnalysisMetrics(BaseModel):
    family_score: int
    family_score_delta: int
    attention_count: int
    report_count: int
    device_count: int


class HealthAnalysisSummaryItem(BaseModel):
    level: HealthLevel
    text: str


class HealthAnalysisAbnormalItem(BaseModel):
    metric: str
    member_id: str
    member_name: str
    member_relation: str
    current_value: str
    status: Literal["danger", "warning"]
    status_text: str
    trend_text: str
    suggestion: str
    score_impact: int = Field(exclude=True)


class HealthAnalysisMemberCard(BaseModel):
    member_id: str
    name: str
    relation: str
    age: int
    health_score: int
    status: Literal["success", "warning", "danger"]
    status_text: str
    avatar_text: str


class HealthAnalysisIndicator(BaseModel):
    key: str
    label: str
    value: str
    unit: str | None = None
    status: HealthLevel
    status_text: str


class HealthAnalysisBloodPressurePoint(BaseModel):
    date: str
    systolic: int
    diastolic: int


class HealthAnalysisAdvice(BaseModel):
    title: str
    lines: list[str]
    prompt: str


class HealthAnalysisOverviewResponse(BaseModel):
    family: HealthAnalysisFamily
    metrics: HealthAnalysisMetrics
    summary: list[HealthAnalysisSummaryItem]
    abnormal_items: list[HealthAnalysisAbnormalItem]
    member_cards: list[HealthAnalysisMemberCard]


class HealthAnalysisMemberResponse(BaseModel):
    member_card: HealthAnalysisMemberCard
    indicators: list[HealthAnalysisIndicator]
    blood_pressure_7d: list[HealthAnalysisBloodPressurePoint]
    abnormalities: list[HealthAnalysisAbnormalItem]
    advice: HealthAnalysisAdvice
