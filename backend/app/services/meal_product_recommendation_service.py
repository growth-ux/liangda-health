from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.mall import MallProduct
from app.models.member import Member
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.services.health_profile_service import FamilyHealthProfile, HealthProfile, HealthProfileService
from app.services.mall_recommendation import build_recommend_reason, score_product_for_member


@dataclass(frozen=True)
class MealProductRecommendation:
    product: MallProduct
    score: int
    reason: str
    evidence_source: str


TAG_RULES: list[tuple[tuple[str, ...], tuple[str, ...], str]] = [
    (("低钠", "清淡", "血压"), ("low_sodium", "hypertension"), "契合本次低钠清淡方向"),
    (("控糖", "低GI", "血糖", "主食定量", "杂粮", "燕麦", "糙米"), ("sugar_control", "low_gi"), "适合作为控糖或低 GI 主食选择"),
    (("少油", "低脂", "轻负担", "晚餐减轻"), ("low_fat",), "更适合少油轻负担饮食"),
    (("高纤维", "高纤", "杂粮", "蔬菜", "黑米", "藜麦"), ("high_fiber",), "补充膳食纤维，适合餐单中的杂粮方向"),
    (("优质蛋白", "高蛋白", "鸡胸肉", "豆腐", "豆浆", "牛奶", "蛋", "植物蛋白"), ("high_protein",), "补充优质蛋白，适合餐单搭配"),
    (("高钙", "骨密度", "骨质", "牛奶", "芝麻"), ("high_calcium", "nutrients"), "匹配高钙和营养补充方向"),
    (("低嘌呤", "尿酸", "痛风"), ("low_purine",), "更适合关注尿酸和嘌呤摄入的人群"),
]

CATEGORY_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("蔬菜", "配菜", "清炒", "凉拌", "菌菇", "生菜", "西兰花", "菠菜", "番茄", "黄瓜"), "vegetables", "适合清淡配菜和高纤维搭配"),
    (("鸡蛋", "鸡胸肉", "虾仁", "鱼", "鳕鱼", "牛里脊", "优质蛋白", "高蛋白"), "meat_eggs", "补充优质蛋白，适合作为正餐食材"),
    (("豆腐", "豆浆", "豆干", "纳豆", "腐竹", "植物蛋白"), "soy_products", "适合清淡烹调和植物蛋白补充"),
    (("水果", "加餐", "餐后", "维C", "苹果", "蓝莓", "橙子", "猕猴桃", "牛油果", "圣女果"), "fruits", "适合作为加餐或餐后水果补充"),
]

QUERY_CATEGORY_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("油", "食用油", "橄榄油", "菜籽油", "亚麻籽油", "玉米油", "花生油"), "oil", "匹配你正在找的油品类目"),
    (("米", "面", "挂面", "面条", "大米"), "rice_flour", "匹配你正在找的米面类目"),
    (("杂粮", "燕麦", "藜麦", "黑米", "糙米"), "grains", "匹配你正在找的杂粮类目"),
    (("调料", "调味", "酱油", "生抽", "醋", "蚝油"), "seasoning", "匹配你正在找的调味品类目"),
    (("牛奶", "酸奶", "奶"), "dairy", "匹配你正在找的乳制品类目"),
    (("饮料", "饮品", "豆奶", "果汁"), "beverages", "匹配你正在找的饮品类目"),
    (("零食", "饼干"), "snacks", "匹配你正在找的零食类目"),
    (("蔬菜", "菌菇"), "vegetables", "匹配你正在找的蔬菜菌菇类目"),
    (("水果",), "fruits", "匹配你正在找的水果类目"),
    (("豆腐", "豆浆", "豆干", "豆制品"), "soy_products", "匹配你正在找的豆制品类目"),
    (("鸡蛋", "鸡胸肉", "牛肉", "猪肉", "虾", "鱼", "肉"), "meat_eggs", "匹配你正在找的肉禽蛋类目"),
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
        query_text: str = "",
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
            recs = self._recommend_for_member(profile, member, meal_plan_text, query_text, limit)
        elif scope == "family":
            profile = self.profile_service.get_family_profile()
            members = self.db.query(Member).all()
            recs = self._recommend_for_family(profile, members, meal_plan_text, query_text, limit)
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
        query_text: str,
        limit: int,
    ) -> list[MealProductRecommendation]:
        products = self._products()
        context = " ".join(
            [
                meal_plan_text,
                query_text,
                " ".join(profile.diet_principles),
                " ".join(profile.recent_states),
                " ".join(profile.goals),
            ]
        )
        return self._rank(products, context, [member], query_text, limit, profile=profile)

    def _recommend_for_family(
        self,
        profile: FamilyHealthProfile,
        members: list[Member],
        meal_plan_text: str,
        query_text: str,
        limit: int,
    ) -> list[MealProductRecommendation]:
        products = self._products()
        context = " ".join(
            [
                meal_plan_text,
                query_text,
                " ".join(profile.shared_principles),
                " ".join(profile.family_modifiers),
                " ".join(profile.family_goals),
            ]
        )
        return self._rank(products, context, members, query_text, limit, family_profile=profile)

    def _products(self) -> list[MallProduct]:
        self.mall_repository.seed_default_data()
        return self.mall_repository.list_all_products()

    def _rank(
        self,
        products: list[MallProduct],
        context: str,
        members: list[Member],
        query_text: str,
        limit: int,
        *,
        profile: HealthProfile | None = None,
        family_profile: FamilyHealthProfile | None = None,
    ) -> list[MealProductRecommendation]:
        requested_category, requested_reason = _match_requested_category(query_text)
        if requested_category:
            products = [product for product in products if product.category_code == requested_category]

        scored: list[MealProductRecommendation] = []
        for product in products:
            if any(_has_allergy_conflict(member, product) for member in members):
                continue
            tags = set(_json_list(product.recommend_tags))
            category_score, category_reason = _score_category(context, product.category_code)
            tag_score, tag_reason = _score_tags(context, tags)
            member_score = sum(max(0, score_product_for_member(member, product)) for member in members)
            requested_score = 200 if requested_category and product.category_code == requested_category else 0
            score = requested_score + category_score + tag_score + member_score
            reason, evidence_source = _build_evidence_reason(
                product=product,
                members=members,
                profile=profile,
                family_profile=family_profile,
                requested_reason=requested_reason,
                category_reason=category_reason,
                tag_reason=tag_reason,
            )
            if score > 0:
                scored.append(
                    MealProductRecommendation(
                        product=product,
                        score=score,
                        reason=reason,
                        evidence_source=evidence_source,
                    )
                )
        scored.sort(key=lambda item: (-item.score, item.product.product_id))
        return _pick_diverse_reasons(scored, max(1, limit))

    @staticmethod
    def _serialize(rec: MealProductRecommendation) -> dict:
        product = rec.product
        return {
            "product_id": product.product_id,
            "name": product.name,
            "reason": rec.reason,
            "evidence_source": rec.evidence_source,
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


def _score_category(context: str, category_code: str) -> tuple[int, str]:
    for keywords, target_category, reason in CATEGORY_RULES:
        if category_code == target_category and any(keyword in context for keyword in keywords):
            return 120, reason
    return 0, ""


def _match_requested_category(query_text: str) -> tuple[str | None, str]:
    for keywords, category_code, reason in QUERY_CATEGORY_RULES:
        if any(keyword in query_text for keyword in keywords):
            return category_code, reason
    return None, ""


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


def _build_evidence_reason(
    *,
    product: MallProduct,
    members: list[Member],
    profile: HealthProfile | None,
    family_profile: FamilyHealthProfile | None,
    requested_reason: str,
    category_reason: str,
    tag_reason: str,
) -> tuple[str, str]:
    tags = set(_json_list(product.recommend_tags))
    generic_reason = requested_reason or category_reason or tag_reason or "匹配本次商品标签"

    if profile is not None:
        device_reason = _member_device_reason(profile, tags)
        if device_reason:
            return _merge_reasons(device_reason, generic_reason), "最近7天手环 + 商品标签"
        report_reason = _member_report_reason(profile, tags)
        if report_reason:
            return _merge_reasons(report_reason, generic_reason), "报告健康事实 + 商品标签"
        member_reason = build_recommend_reason(members[0], product)
        if not member_reason.startswith("该商品适合全家"):
            return _merge_reasons(member_reason, generic_reason), "健康档案 + 商品标签"

    if family_profile is not None:
        family_device_reason = _family_device_reason(family_profile, tags)
        if family_device_reason:
            return _merge_reasons(family_device_reason, generic_reason), "最近7天手环 + 商品标签"
        family_report_reason = _family_report_reason(family_profile, tags)
        if family_report_reason:
            return _merge_reasons(family_report_reason, generic_reason), "报告健康事实 + 商品标签"

    if requested_reason:
        return generic_reason, "当前问题 + 商品标签"
    return generic_reason, "商品标签匹配"


def _merge_reasons(primary: str, secondary: str) -> str:
    if not secondary or secondary in primary:
        return primary
    return f"{primary}；{secondary}"


def _member_report_reason(profile: HealthProfile, tags: set[str]) -> str:
    if not profile.evidence_notes:
        return ""
    return _risk_reason(profile.long_term_risks, tags)


def _family_report_reason(profile: FamilyHealthProfile, tags: set[str]) -> str:
    if not profile.evidence_notes:
        return ""
    return _risk_reason(profile.shared_risks, tags)


def _member_device_reason(profile: HealthProfile, tags: set[str]) -> str:
    return _device_reason(profile.recent_states, tags)


def _family_device_reason(profile: FamilyHealthProfile, tags: set[str]) -> str:
    return _device_reason(profile.family_modifiers, tags)


def _risk_reason(risks: list[str], tags: set[str]) -> str:
    if "血脂偏高" in risks and {"low_fat", "high_fiber", "high_protein"} & tags:
        return "报告提示血脂偏高，这次推荐优先少油和高纤维方向"
    if "血压偏高" in risks and {"low_sodium", "hypertension"} & tags:
        return "报告提示血压偏高，这次推荐优先低钠方向"
    if "血糖风险" in risks and {"sugar_control", "low_gi"} & tags:
        return "报告提示控糖风险，这次推荐优先低 GI 方向"
    if "骨密度风险" in risks and {"high_calcium", "nutrients"} & tags:
        return "报告提示骨密度风险，这次推荐优先高钙营养方向"
    if "尿酸风险" in risks and {"low_purine"} & tags:
        return "报告提示尿酸风险，这次推荐优先低嘌呤方向"
    return ""


def _device_reason(states: list[str], tags: set[str]) -> str:
    state_text = " ".join(states)
    if "血压近期偏高" in state_text and {"low_sodium", "hypertension"} & tags:
        return "手环显示近期血压偏高，这次推荐继续收紧低钠方向"
    if "步数偏低" in state_text and {"low_fat", "high_fiber", "low_gi"} & tags:
        return "手环显示近期步数偏低，这次推荐更偏向轻负担商品"
    if "睡眠不足" in state_text and {"low_fat", "high_fiber"} & tags:
        return "手环显示近期睡眠不足，这次推荐更偏向清淡轻负担商品"
    return ""


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
