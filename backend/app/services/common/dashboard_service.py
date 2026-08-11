from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.agent import AgentMessage, AgentSession
from app.models.health_fact import HealthFact
from app.models.kb import KbDocument
from app.models.mall import MallCartItem, MallProduct
from app.models.member import Member
from app.models.notice import Notice
from app.schemas.dashboard import (
    BrandRankItem,
    CardUsageItem,
    CategoryPenetrationItem,
    DashboardAiUsage,
    DashboardDailyPoint,
    DashboardFactStatus,
    DashboardNoticeDoneRate,
    DashboardOverview,
    DashboardResponse,
    FactRiskItem,
    FunnelStep,
    HeatmapPoint,
    HotProductItem,
    LiveEvent,
    MemberProfile,
    NameCountItem,
    RiskMemberItem,
    SessionDepth,
)

# qwen-plus 百炼计费（元/token）估算值，仅用于看板展示量级，非精确账单。
_INPUT_PRICE_PER_TOKEN = 0.8 / 1_000_000
_OUTPUT_PRICE_PER_TOKEN = 2.0 / 1_000_000

BRAND_RANK_LIMIT = 8
CATEGORY_PENETRATION_LIMIT = 10
DAILY_TREND_DAYS = 14
FACT_RISK_TOP_LIMIT = 8
RISK_MEMBER_LIMIT = 5
HOT_PRODUCT_LIMIT = 8
HEALTH_TAG_CLOUD_LIMIT = 12
LIVE_EVENT_LIMIT = 12
LIVE_EVENT_SOURCE_LIMIT = 10

# 年龄段分桶顺序固定，便于前端直接渲染。
_AGE_BANDS = [
    ("18岁以下", None, 18),
    ("18-35岁", 18, 36),
    ("36-55岁", 36, 56),
    ("56-70岁", 56, 71),
    ("70岁以上", 71, None),
]

_FACT_STATUS_TEXT = {"danger": "需重点干预", "warning": "建议关注", "normal": "指标正常"}


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self) -> DashboardResponse:
        recommendation_message_count = self._count_recommendation_messages()
        recommended_items = self._collect_recommended_items()
        cart_quantity, cart_amount_cents = self._cart_totals()
        product_map = self._product_map(list(recommended_items.keys()))
        cart_by_product = self._cart_by_product()
        user_message_count = self._count_user_messages()
        # 下单/支付：当前无订单模型，以加购量的 50% 估算已完成支付数（演示口径）。
        paid_quantity = int(cart_quantity * 0.5) if cart_quantity > 0 else 0

        return DashboardResponse(
            overview=DashboardOverview(
                member_count=self._count(Member),
                report_count=self._count(KbDocument),
                health_fact_count=self._count(HealthFact),
                session_count=self._count(AgentSession),
                message_count=self._count(AgentMessage),
                recommendation_count=recommendation_message_count,
                cart_item_count=cart_quantity,
                cart_amount_yuan=round(cart_amount_cents / 100, 2),
            ),
            ai_usage=self._ai_usage(),
            funnel=[
                FunnelStep(name="用户主动咨询", value=user_message_count),
                FunnelStep(name="AI 推荐消息", value=recommendation_message_count),
                FunnelStep(name="推荐商品曝光", value=sum(recommended_items.values())),
                FunnelStep(name="加入购物车", value=cart_quantity),
                FunnelStep(name="下单/支付", value=paid_quantity),
            ],
            brand_ranks=self._brand_ranks(recommended_items, product_map, cart_by_product),
            category_penetration=self._category_penetration(recommended_items, product_map),
            daily_trend=self._daily_trend(),
            fact_status=self._fact_status(),
            notice_done=self._notice_done_rate(),
            member_profile=self._member_profile(),
            fact_risk_top=self._fact_risk_top(),
            risk_members=self._risk_members(),
            interaction_heatmap=self._interaction_heatmap(),
            card_usage=self._card_usage(),
            session_depth=self._session_depth(),
            hot_products=self._hot_products(recommended_items, product_map, cart_by_product),
            live_events=self._live_events(),
        )

    def _count(self, model) -> int:
        return self.db.query(func.count(model.id)).scalar() or 0

    def _count_user_messages(self) -> int:
        """统计用户主动发起的对话消息数（role=user）。"""
        return (
            self.db.query(func.count(AgentMessage.id))
            .filter(AgentMessage.role == "user")
            .scalar()
            or 0
        )

    def _count_recommendation_messages(self) -> int:
        return (
            self.db.query(func.count(AgentMessage.id))
            .filter(AgentMessage.product_recommendations.is_not(None))
            .scalar()
            or 0
        )

    def _collect_recommended_items(self) -> Counter:
        """统计每个商品被推荐的次数（跨会话消息里的 product_recommendations）。"""
        counter: Counter = Counter()
        rows = (
            self.db.query(AgentMessage.product_recommendations)
            .filter(AgentMessage.product_recommendations.is_not(None))
            .all()
        )
        for (raw,) in rows:
            for item in _parse_recommendation_items(raw):
                product_id = item.get("product_id")
                if product_id:
                    counter[str(product_id)] += 1
        return counter

    def _ai_usage(self) -> DashboardAiUsage:
        token_prompt, token_completion = (
            self.db.query(
                func.coalesce(func.sum(AgentMessage.token_prompt), 0),
                func.coalesce(func.sum(AgentMessage.token_completion), 0),
            ).one()
        )
        model_row = (
            self.db.query(AgentMessage.model_name)
            .filter(AgentMessage.model_name.is_not(None))
            .order_by(AgentMessage.id.desc())
            .first()
        )
        token_prompt = int(token_prompt or 0)
        token_completion = int(token_completion or 0)
        estimated_cost = token_prompt * _INPUT_PRICE_PER_TOKEN + token_completion * _OUTPUT_PRICE_PER_TOKEN
        return DashboardAiUsage(
            model_name=model_row[0] if model_row else None,
            token_prompt_total=token_prompt,
            token_completion_total=token_completion,
            # 保留 4 位小数：单测等小数据量下不至于被四舍五入到 0
            estimated_cost_yuan=round(estimated_cost, 4),
        )

    def _cart_totals(self) -> tuple[int, int]:
        """购物车总量与预估转化额（分）。"""
        row = (
            self.db.query(
                func.coalesce(func.sum(MallCartItem.quantity), 0),
                func.coalesce(func.sum(MallCartItem.quantity * MallProduct.price_cents), 0),
            )
            .join(MallProduct, MallCartItem.product_id == MallProduct.product_id)
            .one()
        )
        return int(row[0] or 0), int(row[1] or 0)

    def _product_map(self, product_ids: list[str]) -> dict[str, MallProduct]:
        if not product_ids:
            return {}
        products = self.db.query(MallProduct).filter(MallProduct.product_id.in_(product_ids)).all()
        return {product.product_id: product for product in products}

    def _cart_by_product(self) -> dict[str, int]:
        rows = (
            self.db.query(MallCartItem.product_id, func.sum(MallCartItem.quantity))
            .group_by(MallCartItem.product_id)
            .all()
        )
        return {product_id: int(quantity) for product_id, quantity in rows}

    def _brand_ranks(
        self,
        recommended_items: Counter,
        product_map: dict[str, MallProduct],
        cart_by_product: dict[str, int],
    ) -> list[BrandRankItem]:
        price_by_product = {
            product_id: product.price_cents for product_id, product in product_map.items()
        }

        brand_stats: dict[str, dict] = {}
        for product_id, recommend_count in recommended_items.items():
            product = product_map.get(product_id)
            brand = product.brand if product and product.brand else "其他品牌"
            category_name = product.category_name if product else None
            cart_quantity = cart_by_product.get(product_id, 0)
            entry = brand_stats.setdefault(
                brand,
                {
                    "recommend_count": 0,
                    "cart_count": 0,
                    "amount_cents": 0,
                    "category_name": category_name,
                },
            )
            entry["recommend_count"] += recommend_count
            entry["cart_count"] += cart_quantity
            entry["amount_cents"] += cart_quantity * price_by_product.get(product_id, 0)
            if entry["category_name"] is None:
                entry["category_name"] = category_name

        ranks = [
            BrandRankItem(
                brand=brand,
                category_name=stats["category_name"],
                recommend_count=stats["recommend_count"],
                cart_count=stats["cart_count"],
                amount_yuan=round(stats["amount_cents"] / 100, 2),
            )
            for brand, stats in brand_stats.items()
        ]
        ranks.sort(key=lambda item: (item.recommend_count, item.cart_count), reverse=True)
        return ranks[:BRAND_RANK_LIMIT]

    def _category_penetration(
        self, recommended_items: Counter, product_map: dict[str, MallProduct]
    ) -> list[CategoryPenetrationItem]:
        category_counter: Counter = Counter()
        for product_id, recommend_count in recommended_items.items():
            product = product_map.get(product_id)
            category = product.category_name if product and product.category_name else "其他品类"
            category_counter[category] += recommend_count
        items = [
            CategoryPenetrationItem(category_name=category, recommend_count=count)
            for category, count in category_counter.items()
        ]
        items.sort(key=lambda item: item.recommend_count, reverse=True)
        return items[:CATEGORY_PENETRATION_LIMIT]

    def _daily_trend(self) -> list[DashboardDailyPoint]:
        today = utc_now().date()
        start_day = today - timedelta(days=DAILY_TREND_DAYS - 1)
        start_at = datetime.combine(start_day, datetime.min.time())

        rows = (
            self.db.query(
                func.date(AgentMessage.created_at).label("day"),
                func.count(AgentMessage.id),
                func.sum(case((AgentMessage.product_recommendations.is_not(None), 1), else_=0)),
            )
            .filter(AgentMessage.created_at >= start_at)
            .group_by("day")
            .all()
        )
        stats_by_day = {
            str(day): (int(count or 0), int(recommendation_count or 0))
            for day, count, recommendation_count in rows
        }

        trend: list[DashboardDailyPoint] = []
        for offset in range(DAILY_TREND_DAYS):
            day = start_day + timedelta(days=offset)
            message_count, recommendation_count = stats_by_day.get(day.isoformat(), (0, 0))
            trend.append(
                DashboardDailyPoint(
                    date=day.isoformat(),
                    message_count=message_count,
                    recommendation_count=recommendation_count,
                )
            )
        return trend

    def _fact_status(self) -> DashboardFactStatus:
        rows = self.db.query(HealthFact.status, func.count(HealthFact.id)).group_by(HealthFact.status).all()
        status_map = {status: int(count) for status, count in rows}
        return DashboardFactStatus(
            normal=status_map.get("normal", 0),
            warning=status_map.get("warning", 0),
            danger=status_map.get("danger", 0),
        )

    def _notice_done_rate(self) -> DashboardNoticeDoneRate:
        total = self._count(Notice)
        done = (
            self.db.query(func.count(Notice.id)).filter(Notice.status == "done").scalar() or 0
        )
        rate = round(done / total, 3) if total else 0.0
        return DashboardNoticeDoneRate(total=total, done=done, rate=rate)

    def _member_profile(self) -> MemberProfile:
        members = self.db.query(Member).all()
        gender_counter: Counter = Counter(member.gender for member in members if member.gender)
        relation_counter: Counter = Counter(member.relation for member in members if member.relation)

        current_year = utc_now().year
        band_counter = {band_name: 0 for band_name, _, _ in _AGE_BANDS}
        tag_counter: Counter = Counter()
        for member in members:
            age = current_year - member.birth_year
            for band_name, low, high in _AGE_BANDS:
                if (low is None or age >= low) and (high is None or age < high):
                    band_counter[band_name] += 1
                    break
            tag_counter.update(_split_tags(member.health_tags))
            tag_counter.update(_split_tags(member.allergies))

        return MemberProfile(
            gender_distribution=[
                NameCountItem(name=name, count=count) for name, count in gender_counter.most_common()
            ],
            relation_distribution=[
                NameCountItem(name=name, count=count) for name, count in relation_counter.most_common()
            ],
            age_bands=[
                NameCountItem(name=band_name, count=band_counter[band_name])
                for band_name, _, _ in _AGE_BANDS
            ],
            health_tag_cloud=[
                NameCountItem(name=name, count=count)
                for name, count in tag_counter.most_common(HEALTH_TAG_CLOUD_LIMIT)
            ],
        )

    def _fact_risk_top(self) -> list[FactRiskItem]:
        rows = (
            self.db.query(
                HealthFact.name,
                func.sum(case((HealthFact.status == "warning", 1), else_=0)),
                func.sum(case((HealthFact.status == "danger", 1), else_=0)),
            )
            .filter(HealthFact.status.in_(["warning", "danger"]))
            .group_by(HealthFact.name)
            .order_by((func.count(HealthFact.id)).desc())
            .limit(FACT_RISK_TOP_LIMIT)
            .all()
        )
        return [
            FactRiskItem(name=name, warning_count=int(warning_count or 0), danger_count=int(danger_count or 0))
            for name, warning_count, danger_count in rows
        ]

    def _risk_members(self) -> list[RiskMemberItem]:
        rows = (
            self.db.query(
                HealthFact.member_id,
                func.sum(case((HealthFact.status == "danger", 1), else_=0)),
                func.sum(case((HealthFact.status == "warning", 1), else_=0)),
            )
            .filter(HealthFact.status.in_(["warning", "danger"]))
            .group_by(HealthFact.member_id)
            .all()
        )
        member_ids = [member_id for member_id, _, _ in rows]
        members = (
            self.db.query(Member).filter(Member.member_id.in_(member_ids)).all() if member_ids else []
        )
        member_map = {member.member_id: member for member in members}

        items: list[RiskMemberItem] = []
        for member_id, danger_count, warning_count in rows:
            member = member_map.get(member_id)
            items.append(
                RiskMemberItem(
                    member_id=member_id,
                    member_name=member.name if member else member_id,
                    relation=member.relation if member else None,
                    danger_count=int(danger_count or 0),
                    warning_count=int(warning_count or 0),
                )
            )
        items.sort(key=lambda item: (item.danger_count, item.warning_count), reverse=True)
        return items[:RISK_MEMBER_LIMIT]

    def _interaction_heatmap(self) -> list[HeatmapPoint]:
        """用户提问的 星期 × 小时 热力分布，仅返回非零点。"""
        timestamps = (
            self.db.query(AgentMessage.created_at)
            .filter(AgentMessage.role == "user")
            .all()
        )
        counter: Counter = Counter()
        for (created_at,) in timestamps:
            if created_at is None:
                continue
            counter[(created_at.weekday(), created_at.hour)] += 1
        return [
            HeatmapPoint(weekday=weekday, hour=hour, count=count)
            for (weekday, hour), count in counter.items()
        ]

    def _card_usage(self) -> list[CardUsageItem]:
        rows = (
            self.db.query(AgentMessage.card)
            .filter(AgentMessage.card.is_not(None))
            .all()
        )
        counter: Counter = Counter()
        for (raw,) in rows:
            try:
                card = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(card, dict) and card.get("kind"):
                counter[str(card["kind"])] += 1
        return [
            CardUsageItem(kind=kind, count=count) for kind, count in counter.most_common()
        ]

    def _session_depth(self) -> SessionDepth:
        session_count = self._count(AgentSession)
        rows = (
            self.db.query(AgentMessage.session_id, func.count(AgentMessage.id))
            .filter(AgentMessage.role == "user")
            .group_by(AgentMessage.session_id)
            .all()
        )
        turns = [int(count) for _, count in rows]
        total_turns = sum(turns)
        max_turns = max(turns) if turns else 0
        avg_turns = round(total_turns / session_count, 1) if session_count else 0.0
        return SessionDepth(
            session_count=session_count, avg_user_turns=avg_turns, max_user_turns=max_turns
        )

    def _hot_products(
        self,
        recommended_items: Counter,
        product_map: dict[str, MallProduct],
        cart_by_product: dict[str, int],
    ) -> list[HotProductItem]:
        items: list[HotProductItem] = []
        for product_id, recommend_count in recommended_items.items():
            product = product_map.get(product_id)
            cart_count = cart_by_product.get(product_id, 0)
            price_cents = product.price_cents if product else 0
            items.append(
                HotProductItem(
                    product_id=product_id,
                    name=product.name if product else product_id,
                    brand=product.brand if product else None,
                    category_name=product.category_name if product else None,
                    image_emoji=product.image_emoji if product else None,
                    price_yuan=round(price_cents / 100, 2),
                    recommend_count=recommend_count,
                    cart_count=cart_count,
                    amount_yuan=round(cart_count * price_cents / 100, 2),
                )
            )
        items.sort(key=lambda item: (item.recommend_count, item.cart_count), reverse=True)
        return items[:HOT_PRODUCT_LIMIT]

    def _live_events(self) -> list[LiveEvent]:
        events: list[LiveEvent] = []

        documents = (
            self.db.query(KbDocument)
            .order_by(KbDocument.created_at.desc())
            .limit(LIVE_EVENT_SOURCE_LIMIT)
            .all()
        )
        for document in documents:
            label = document.title or document.file_name
            events.append(
                LiveEvent(
                    event_type="report_upload",
                    text=f"上传健康报告《{label}》，AI 开始结构化解析",
                    occurred_at=document.created_at,
                )
            )

        facts = (
            self.db.query(HealthFact)
            .order_by(HealthFact.created_at.desc())
            .limit(LIVE_EVENT_SOURCE_LIMIT)
            .all()
        )
        for fact in facts:
            status_text = _FACT_STATUS_TEXT.get(fact.status, fact.status)
            events.append(
                LiveEvent(
                    event_type="fact_extract",
                    text=f"AI 提取健康事实「{fact.name}」（{status_text}）",
                    occurred_at=fact.created_at,
                )
            )

        recommend_messages = (
            self.db.query(AgentMessage)
            .filter(AgentMessage.product_recommendations.is_not(None))
            .order_by(AgentMessage.created_at.desc())
            .limit(LIVE_EVENT_SOURCE_LIMIT)
            .all()
        )
        for message in recommend_messages:
            item_count = len(_parse_recommendation_items(message.product_recommendations))
            events.append(
                LiveEvent(
                    event_type="ai_recommend",
                    text=f"AI 在对话中推荐了 {item_count} 个商品",
                    occurred_at=message.created_at,
                )
            )

        cart_items = (
            self.db.query(MallCartItem, MallProduct.name)
            .join(MallProduct, MallCartItem.product_id == MallProduct.product_id)
            .order_by(MallCartItem.created_at.desc())
            .limit(LIVE_EVENT_SOURCE_LIMIT)
            .all()
        )
        for cart_item, product_name in cart_items:
            events.append(
                LiveEvent(
                    event_type="cart_add",
                    text=f"「{product_name}」×{cart_item.quantity} 加入购物车",
                    occurred_at=cart_item.created_at,
                )
            )

        events.sort(key=lambda event: event.occurred_at, reverse=True)
        return events[:LIVE_EVENT_LIMIT]


def _split_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    # health_tags 以 JSON 数组字符串存储（与 member schema 的 _safe_tags 一致），
    # allergies 等字段为普通文本，两种格式都要兼容。
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [tag.strip() for tag in re.split(r"[,、;；\s]+", raw) if tag.strip()]


def _card_kind(raw: str | None) -> str | None:
    try:
        card = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(card, dict):
        kind = card.get("kind")
        if kind:
            return str(kind)
    return None


_CARD_KIND_TEXT = {
    "meal_plan": "膳食计划",
    "kb_interpretation": "报告解读",
    "qa": "健康问答",
    "greeting": "问候关怀",
    "general_advice": "健康建议",
}


def _parse_recommendation_items(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]
