from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.mall import MallProduct
from app.models.member import Member
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.services.health_profile_service import FamilyHealthProfile, HealthProfile, HealthProfileService
from app.services.mall_recommendation import score_product_for_member


@dataclass(frozen=True)
class MealProductRecommendation:
    product: MallProduct
    score: int
    reason: str


TAG_RULES: list[tuple[tuple[str, ...], tuple[str, ...], str]] = [
    (("低钠", "清淡", "血压"), ("low_sodium", "hypertension"), "契合本次低钠清淡方向"),
    (("控糖", "低GI", "血糖", "主食定量", "杂粮", "燕麦", "糙米"), ("sugar_control", "low_gi"), "适合作为控糖或低 GI 主食选择"),
    (("少油", "低脂", "轻负担", "晚餐减轻"), ("low_fat",), "更适合少油轻负担饮食"),
    (("高纤维", "高纤", "杂粮", "蔬菜", "黑米", "藜麦"), ("high_fiber",), "补充膳食纤维，适合餐单中的杂粮方向"),
    (("优质蛋白", "高蛋白", "鸡胸肉", "豆腐", "豆浆", "牛奶", "蛋"), ("high_protein",), "补充优质蛋白，适合餐单搭配"),
    (("高钙", "骨密度", "骨质", "牛奶", "芝麻"), ("high_calcium", "nutrients"), "匹配高钙和营养补充方向"),
    (("低嘌呤", "尿酸", "痛风"), ("low_purine",), "更适合关注尿酸和嘌呤摄入的人群"),
]


class MealProductRecommendationService:
    def __init__(
        self,
        db: Session,
        *,
        mall_repository: SqlAlchemyMallRepository | None = None,
        profile_service: HealthProfileService | None = None,
    ):
        self.db = db
        self.mall_repository = mall_repository or SqlAlchemyMallRepository(db)
        self.profile_service = profile_service or HealthProfileService(db)

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 5,
    ) -> dict:
        """返回结构化推荐结果。

        结构：
          {
            "items": [
              {
                "product_id": str,
                "name": str,
                "reason": str,
                "price_text": str,
                "image_url": str | None,
                "image_emoji": str | None,
                "score": int,
              },
              ...
            ],
            "is_error": bool,
            "error": str | None,
          }

        错误情况（缺少 member_id / scope 非法等）也会通过 is_error + error 字段表达，
        调用方（agent runner / agent tool wrapper）按需要决定是当作文本错误继续走，
        还是当作结构化空结果直接交前端。
        """
        if scope == "member":
            if not member_id:
                return {"items": [], "is_error": True, "error": "单人商品推荐必须传入 member_id"}
            profile = self.profile_service.get_member_profile(member_id)
            member = self.db.query(Member).filter(Member.member_id == member_id).one_or_none()
            if member is None:
                return {"items": [], "is_error": True, "error": "家人不存在"}
            recs = self._recommend_for_member(profile, member, meal_plan_text, limit)
        elif scope == "family":
            profile = self.profile_service.get_family_profile()
            members = self.db.query(Member).all()
            recs = self._recommend_for_family(profile, members, meal_plan_text, limit)
        else:
            return {"items": [], "is_error": True, "error": "scope 只能是 member 或 family"}
        return {
            "items": [self._serialize(rec) for rec in recs],
            "is_error": False,
            "error": None,
        }

    def _recommend_for_member(
        self,
        profile: HealthProfile,
        member: Member,
        meal_plan_text: str,
        limit: int,
    ) -> list[MealProductRecommendation]:
        products = self._products()
        context = " ".join(
            [
                meal_plan_text,
                " ".join(profile.diet_principles),
                " ".join(profile.recent_states),
                " ".join(profile.goals),
            ]
        )
        return self._rank(products, context, [member], limit)

    def _recommend_for_family(
        self,
        profile: FamilyHealthProfile,
        members: list[Member],
        meal_plan_text: str,
        limit: int,
    ) -> list[MealProductRecommendation]:
        products = self._products()
        context = " ".join(
            [
                meal_plan_text,
                " ".join(profile.shared_principles),
                " ".join(profile.family_modifiers),
                " ".join(profile.family_goals),
            ]
        )
        return self._rank(products, context, members, limit)

    def _products(self) -> list[MallProduct]:
        self.mall_repository.seed_default_data()
        return self.mall_repository.list_all_products()

    def _rank(
        self,
        products: list[MallProduct],
        context: str,
        members: list[Member],
        limit: int,
    ) -> list[MealProductRecommendation]:
        scored: list[MealProductRecommendation] = []
        for product in products:
            if any(_has_allergy_conflict(member, product) for member in members):
                continue
            tags = set(_json_list(product.recommend_tags))
            tag_score, reason = _score_tags(context, tags)
            member_score = sum(max(0, score_product_for_member(member, product)) for member in members)
            score = tag_score + member_score
            if score > 0:
                scored.append(MealProductRecommendation(product=product, score=score, reason=reason))
        scored.sort(key=lambda item: (-item.score, item.product.product_id))
        return _pick_diverse_reasons(scored, max(1, limit))

    @staticmethod
    def _serialize(rec: MealProductRecommendation) -> dict:
        product = rec.product
        return {
            "product_id": product.product_id,
            "name": product.name,
            "reason": rec.reason,
            "price_text": MealProductRecommendationService._format_price(product.price_cents),
            "image_url": product.image_url,
            "image_emoji": product.image_emoji,
            "score": rec.score,
        }

    @staticmethod
    def _format_price(cents: int) -> str:
        yuan = cents / 100
        if yuan == int(yuan):
            return f"¥{int(yuan)}"
        return f"¥{yuan:.1f}"


def _score_tags(context: str, tags: set[str]) -> tuple[int, str]:
    for keywords, recommend_tags, reason in TAG_RULES:
        if any(keyword in context for keyword in keywords) and tags & set(recommend_tags):
            return 80, reason
    return 0, "适合本次健康餐单搭配"


def _pick_diverse_reasons(
    items: list[MealProductRecommendation],
    limit: int,
) -> list[MealProductRecommendation]:
    selected: list[MealProductRecommendation] = []
    used_reasons: set[str] = set()
    for item in items:
        if item.reason in used_reasons:
            continue
        selected.append(item)
        used_reasons.add(item.reason)
        if len(selected) >= limit:
            return selected
    for item in items:
        if item in selected:
            continue
        selected.append(item)
        if len(selected) >= limit:
            return selected
    return selected


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _has_allergy_conflict(member: Member, product: MallProduct) -> bool:
    allergies = _csv(member.allergies)
    warning_tags = [item.lower() for item in _json_list(product.warning_tags)]
    return any(allergy in warning or warning in allergy for allergy in allergies for warning in warning_tags)
