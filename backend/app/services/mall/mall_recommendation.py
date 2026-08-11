import json
import random
from datetime import datetime

from app.models.mall import MallProduct
from app.models.member import Member
from app.schemas.mall import MallFamilyRecommendation, MallProductSummary


def _safe_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return value


def _parse_csv_field(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_member_age(member: Member) -> int:
    return max(0, datetime.now().year - member.birth_year)


def _get_member_bmi(member: Member) -> float | None:
    if not member.height_cm or not member.weight_kg or member.height_cm <= 0:
        return None
    return member.weight_kg / ((member.height_cm / 100) ** 2)


def _get_member_health_tags(member: Member) -> list[str]:
    return _safe_json_list(member.health_tags)


def _has_health_condition(health_tags: list[str], keywords: list[str]) -> bool:
    for tag in health_tags:
        for keyword in keywords:
            if keyword in tag:
                return True
    return False


def _check_allergy_conflict(member: Member, product: MallProduct) -> bool:
    allergies = _parse_csv_field(member.allergies)
    if not allergies:
        return False
    warning_tags = _safe_json_list(product.warning_tags)
    if not warning_tags:
        return False
    allergy_lower = [a.lower() for a in allergies]
    warning_lower = [w.lower() for w in warning_tags]
    for allergy in allergy_lower:
        for warning in warning_lower:
            if allergy in warning or warning in allergy:
                return True
    return False


# ── 会员健康匹配规则表（score_product_for_member 与 build_recommend_reason 共用）──
_MEMBER_HEALTH_RULES = [
    {
        "condition": lambda ht: _has_health_condition(ht, ["高血压", "血压偏高", "血压高"]),
        "tag_match": {"low_sodium", "hypertension"},
        "score": 50,
        "reason_tpl": "{name}（{relation}）血压偏高，建议优先选择低钠调味品。",
    },
    {
        "condition": lambda ht: _has_health_condition(ht, ["糖尿病", "血糖偏高", "控糖", "血糖高"]),
        "tag_match": {"sugar_control", "low_gi", "no_sugar", "diabetes"},
        "score": 50,
        "reason_tpl": "{name}（{relation}）有控糖需求，低GI主食更适合日常食用。",
    },
    {
        "condition": lambda ht, bmi=None, age=None: bmi is not None and bmi >= 24,
        "tag_match": {"low_fat", "high_protein", "low_gi", "high_fiber"},
        "score": 30,
        "reason_tpl": "{name}（{relation}）建议控制脂肪摄入，该商品更适合健康饮食。",
    },
    {
        "condition": lambda ht, bmi=None, age=None: age is not None and age < 18,
        "tag_match": {"high_calcium", "children"},
        "score": 30,
        "reason_tpl": "{name}（{relation}）正处于生长发育期，高钙食品有助于骨骼健康。",
    },
    {
        "condition": lambda ht, bmi=None, age=None: age is not None and age >= 60,
        "tag_match": {"high_calcium", "elderly"},
        "score": 30,
        "reason_tpl": "{name}（{relation}）需要关注骨骼健康，高钙食品是不错的选择。",
    },
]


def score_product_for_member(member: Member, product: MallProduct) -> int:
    if _check_allergy_conflict(member, product):
        return -1

    score = 0
    health_tags = _get_member_health_tags(member)
    recommend_set = set(_safe_json_list(product.recommend_tags))

    bmi = _get_member_bmi(member)
    age = _get_member_age(member)

    for rule in _MEMBER_HEALTH_RULES:
        cond = rule["condition"]
        try:
            matched = cond(health_tags, bmi=bmi, age=age)
        except TypeError:
            matched = cond(health_tags)
        if matched and rule["tag_match"] & recommend_set:
            score += rule["score"]

    taste_preferences = _parse_csv_field(member.taste_preferences)
    product_health_tags = _safe_json_list(product.health_tags)
    for taste in taste_preferences:
        for tag in product_health_tags:
            if taste in tag or tag in taste:
                score += 10
                break
        if product.category_name and taste in product.category_name:
            score += 10

    return score


def build_recommend_reason(member: Member, product: MallProduct) -> str:
    health_tags = _get_member_health_tags(member)
    relation = member.relation or "家人"
    recommend_set = set(_safe_json_list(product.recommend_tags))

    bmi = _get_member_bmi(member)
    age = _get_member_age(member)

    for rule in _MEMBER_HEALTH_RULES:
        cond = rule["condition"]
        try:
            matched = cond(health_tags, bmi=bmi, age=age)
        except TypeError:
            matched = cond(health_tags)
        if matched and rule["tag_match"] & recommend_set:
            return rule["reason_tpl"].format(name=member.name, relation=relation)

    return "该商品适合全家日常健康饮食，本推荐不构成医疗建议。"


def filter_allergy_products(member: Member, products: list[MallProduct]) -> list[MallProduct]:
    return [p for p in products if not _check_allergy_conflict(member, p)]


def _summarize_for_member(member: Member, top_product: MallProduct) -> str:
    """根据打分规则生成"为什么这位家人需要这些商品"的简短文案。

    优先级与 score_product_for_member 对齐：先看会员的真实健康诉求，
    再看 Top 商品是否真的命中对应推荐标签，给出有差异、可解释的 summary。
    """
    health_tags = _get_member_health_tags(member)
    recommend_tags = set(_safe_json_list(top_product.recommend_tags))

    hypertension_keywords = ["高血压", "血压偏高", "血压高"]
    if (
        _has_health_condition(health_tags, hypertension_keywords)
        and {"low_sodium", "hypertension"} & recommend_tags
    ):
        return "低钠 · 控血压"

    diabetes_keywords = ["糖尿病", "血糖偏高", "控糖", "血糖高"]
    if (
        _has_health_condition(health_tags, diabetes_keywords)
        and {"sugar_control", "low_gi", "no_sugar", "diabetes"} & recommend_tags
    ):
        return "控糖 · 低 GI"

    bmi = _get_member_bmi(member)
    if bmi is not None and bmi >= 24:
        weight_tags = {"low_fat", "high_protein", "low_gi", "high_fiber"}
        if weight_tags & recommend_tags:
            return "轻负担 · 控体重"

    age = _get_member_age(member)
    if age < 18 and {"high_calcium", "children"} & recommend_tags:
        return "助生长 · 高钙"
    if age >= 60 and {"high_calcium", "elderly"} & recommend_tags:
        return "护骨骼 · 高钙"

    # 兜底：取商品自身的前两个标签，比 dump 三个标签更紧凑
    product_tags = _safe_json_list(top_product.health_tags)
    fallback = " · ".join(product_tags[:2])
    return fallback or "健康推荐"


def build_member_recommendations(
    members: list[Member],
    products: list[MallProduct],
    max_products_per_member: int = 3,
) -> list[MallFamilyRecommendation]:
    recommendations: list[MallFamilyRecommendation] = []

    for member in members:
        safe_products = filter_allergy_products(member, products)
        scored: list[tuple[int, MallProduct]] = []
        for product in safe_products:
            s = score_product_for_member(member, product)
            if s > 0:
                scored.append((s, product))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_products = scored[:max_products_per_member]

        if not top_products:
            continue

        summaries: list[MallProductSummary] = []
        for score_val, product in top_products:
            reason = build_recommend_reason(member, product)
            summaries.append(
                MallProductSummary(
                    product_id=product.product_id,
                    name=product.name,
                    brand=product.brand,
                    category_code=product.category_code,
                    category_name=product.category_name,
                    price_cents=product.price_cents,
                    original_price_cents=product.original_price_cents,
                    spec=product.spec,
                    sales_text=product.sales_text,
                    image_emoji=product.image_emoji,
                    image_url=product.image_url,
                    health_tags_raw=product.health_tags,
                    recommend_reason=reason,
                )
            )

        summary_text = _summarize_for_member(member, top_products[0][1])
        zone_name = f"为{member.relation}推荐"

        recommendations.append(
            MallFamilyRecommendation(
                member_id=member.member_id,
                member_name=member.name,
                relation=member.relation,
                zone_name=zone_name,
                summary=summary_text,
                products=summaries,
            )
        )

    return recommendations


def get_best_recommend_reason(member: Member, product: MallProduct) -> str | None:
    s = score_product_for_member(member, product)
    if s <= 0:
        return None
    return build_recommend_reason(member, product)


def find_best_member_for_product(
    members: list[Member],
    product: MallProduct,
) -> tuple[Member | None, str | None]:
    best_member: Member | None = None
    best_score = 0
    best_reason: str | None = None

    for member in members:
        s = score_product_for_member(member, product)
        if s > best_score:
            best_score = s
            best_member = member
            best_reason = build_recommend_reason(member, product)

    return best_member, best_reason


def _summarize_for_family(members: list[Member], top_products: list[MallProduct]) -> str:
    """按家人们的真实健康诉求 + Top 商品实际标签，拼出"全家通用"的简短说明。"""
    member_count = len(members)
    if member_count == 0 or not top_products:
        return "适合全家日常饮食"

    recommend_union: set[str] = set()
    for product in top_products:
        recommend_union.update(_safe_json_list(product.recommend_tags))

    hypertension_keywords = ["高血压", "血压偏高", "血压高"]
    diabetes_keywords = ["糖尿病", "血糖偏高", "控糖", "血糖高"]

    has_hypertension = any(
        _has_health_condition(_get_member_health_tags(m), hypertension_keywords) for m in members
    )
    has_diabetes = any(
        _has_health_condition(_get_member_health_tags(m), diabetes_keywords) for m in members
    )
    has_overweight = any(
        (bmi := _get_member_bmi(m)) is not None and bmi >= 24 for m in members
    )
    has_elderly = any(_get_member_age(m) >= 60 for m in members)
    has_child = any(_get_member_age(m) < 18 for m in members)

    themes: list[str] = []
    if has_hypertension and {"low_sodium", "hypertension"} & recommend_union:
        themes.append("低钠")
    if has_diabetes and {"sugar_control", "low_gi", "no_sugar", "diabetes"} & recommend_union:
        themes.append("控糖")
    if has_overweight and {"low_fat", "high_protein", "low_gi", "high_fiber"} & recommend_union:
        themes.append("轻负担")
    if (has_elderly or has_child) and {"high_calcium", "elderly", "children"} & recommend_union:
        themes.append("护骨骼")

    if themes:
        return f"覆盖 {member_count} 位家人 · 兼顾{'·'.join(themes)}"
    return f"适合 {member_count} 位家人的日常饮食"


def build_family_recommendation(
    members: list[Member],
    products: list[MallProduct],
    max_products: int = 6,
) -> MallFamilyRecommendation | None:
    """聚合全家推荐：
    1) 硬过滤：与任何一位成员过敏原冲突的商品直接出局
    2) 聚合打分：把每位成员的 score 求和，挑总分 > 0 的 Top N
    3) summary：按家人真实诉求 + 实际命中标签生成
    """
    if not members:
        return None

    safe_products = [
        product
        for product in products
        if not any(_check_allergy_conflict(m, product) for m in members)
    ]

    scored: list[tuple[int, MallProduct]] = []
    for product in safe_products:
        aggregate = sum(score_product_for_member(m, product) for m in members)
        if aggregate > 0:
            scored.append((aggregate, product))
    scored.sort(key=lambda item: item[0], reverse=True)
    top_products = scored[:max_products]
    if not top_products:
        return None

    summaries: list[MallProductSummary] = []
    for _, product in top_products:
        summaries.append(
            MallProductSummary(
                product_id=product.product_id,
                name=product.name,
                brand=product.brand,
                category_code=product.category_code,
                category_name=product.category_name,
                price_cents=product.price_cents,
                original_price_cents=product.original_price_cents,
                spec=product.spec,
                sales_text=product.sales_text,
                image_emoji=product.image_emoji,
                image_url=product.image_url,
                health_tags_raw=product.health_tags,
                recommend_reason=None,
            )
        )

    return MallFamilyRecommendation(
        member_id="family",
        member_name="全家",
        relation="家庭",
        zone_name="全家通用",
        summary=_summarize_for_family(members, [p for _, p in top_products]),
        products=summaries,
    )


def build_daily_recommendations(
    members: list[Member],
    products: list[MallProduct],
) -> list[MallProductSummary]:
    """全量"今日猜你想买"列表：
    1) 硬过滤：与任何一位成员过敏原冲突的商品直接出局
    2) 同一类目内，按"家人聚合分 + 随机扰动"降序
    3) **类目间按 round-robin 轮询输出**——避免排序被一两个高分类目锁死，
       让"换一批"时每个类目都有机会出现在前几个槽位
    4) 仍然全量返回，让前端分页/换一批
    """
    safe_products = [
        product
        for product in products
        if not any(_check_allergy_conflict(m, product) for m in members)
    ]

    # 按类目分组并打分排序
    by_category: dict[str, list[tuple[float, MallProduct]]] = {}
    for product in safe_products:
        family_score = (
            sum(score_product_for_member(m, product) for m in members) if members else 0
        )
        jitter = random.random() * (max(30.0, family_score * 0.3) if family_score > 0 else 10.0)
        by_category.setdefault(product.category_code, []).append((family_score + jitter, product))
    for items in by_category.values():
        items.sort(key=lambda item: item[0], reverse=True)

    # 类目间按 sort_order 稳定轮询；空位跳过
    category_codes = sorted(by_category.keys())
    interleaved: list[MallProduct] = []
    max_len = max((len(items) for items in by_category.values()), default=0)
    for index in range(max_len):
        for code in category_codes:
            items = by_category[code]
            if index < len(items):
                interleaved.append(items[index][1])

    return [
        MallProductSummary(
            product_id=product.product_id,
            name=product.name,
            brand=product.brand,
            category_code=product.category_code,
            category_name=product.category_name,
            price_cents=product.price_cents,
            original_price_cents=product.original_price_cents,
            spec=product.spec,
            sales_text=product.sales_text,
            image_emoji=product.image_emoji,
            image_url=product.image_url,
            health_tags_raw=product.health_tags,
            recommend_reason=None,
        )
        for product in interleaved
    ]
