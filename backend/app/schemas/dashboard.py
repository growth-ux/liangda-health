from datetime import datetime

from pydantic import BaseModel, Field


class DashboardOverview(BaseModel):
    member_count: int = 0
    report_count: int = 0
    health_fact_count: int = 0
    session_count: int = 0
    message_count: int = 0
    recommendation_count: int = 0
    cart_item_count: int = 0
    cart_amount_yuan: float = 0.0


class DashboardAiUsage(BaseModel):
    model_name: str | None = None
    token_prompt_total: int = 0
    token_completion_total: int = 0
    estimated_cost_yuan: float = 0.0


class FunnelStep(BaseModel):
    name: str
    value: int


class BrandRankItem(BaseModel):
    brand: str
    category_name: str | None = None
    recommend_count: int = 0
    cart_count: int = 0
    amount_yuan: float = 0.0


class CategoryPenetrationItem(BaseModel):
    category_name: str
    recommend_count: int = 0


class DashboardDailyPoint(BaseModel):
    date: str
    message_count: int = 0
    recommendation_count: int = 0


class DashboardFactStatus(BaseModel):
    normal: int = 0
    warning: int = 0
    danger: int = 0


class DashboardNoticeDoneRate(BaseModel):
    total: int = 0
    done: int = 0
    rate: float = 0.0


class NameCountItem(BaseModel):
    name: str
    count: int = 0


class MemberProfile(BaseModel):
    gender_distribution: list[NameCountItem] = Field(default_factory=list)
    relation_distribution: list[NameCountItem] = Field(default_factory=list)
    age_bands: list[NameCountItem] = Field(default_factory=list)
    health_tag_cloud: list[NameCountItem] = Field(default_factory=list)


class FactRiskItem(BaseModel):
    name: str
    warning_count: int = 0
    danger_count: int = 0


class RiskMemberItem(BaseModel):
    member_id: str
    member_name: str
    relation: str | None = None
    danger_count: int = 0
    warning_count: int = 0


class HeatmapPoint(BaseModel):
    weekday: int = 0
    hour: int = 0
    count: int = 0


class CardUsageItem(BaseModel):
    kind: str
    count: int = 0


class SessionDepth(BaseModel):
    session_count: int = 0
    avg_user_turns: float = 0.0
    max_user_turns: int = 0


class HotProductItem(BaseModel):
    product_id: str
    name: str
    brand: str | None = None
    category_name: str | None = None
    image_emoji: str | None = None
    price_yuan: float = 0.0
    recommend_count: int = 0
    cart_count: int = 0
    amount_yuan: float = 0.0


class LiveEvent(BaseModel):
    event_type: str
    text: str
    occurred_at: datetime


class DashboardResponse(BaseModel):
    overview: DashboardOverview
    ai_usage: DashboardAiUsage
    funnel: list[FunnelStep] = Field(default_factory=list)
    brand_ranks: list[BrandRankItem] = Field(default_factory=list)
    category_penetration: list[CategoryPenetrationItem] = Field(default_factory=list)
    daily_trend: list[DashboardDailyPoint] = Field(default_factory=list)
    fact_status: DashboardFactStatus = Field(default_factory=DashboardFactStatus)
    notice_done: DashboardNoticeDoneRate = Field(default_factory=DashboardNoticeDoneRate)
    member_profile: MemberProfile = Field(default_factory=MemberProfile)
    fact_risk_top: list[FactRiskItem] = Field(default_factory=list)
    risk_members: list[RiskMemberItem] = Field(default_factory=list)
    interaction_heatmap: list[HeatmapPoint] = Field(default_factory=list)
    card_usage: list[CardUsageItem] = Field(default_factory=list)
    session_depth: SessionDepth = Field(default_factory=SessionDepth)
    hot_products: list[HotProductItem] = Field(default_factory=list)
    live_events: list[LiveEvent] = Field(default_factory=list)
