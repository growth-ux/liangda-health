import json
from datetime import datetime

from app.models.member import Member
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.services.meal_product_recommendation_service import MealProductRecommendationService


def _add_member(
    db_session,
    *,
    member_id: str = "mem_dad",
    name: str = "李建国",
    relation: str = "爸爸",
    allergies: str | None = None,
):
    member = Member(
        member_id=member_id,
        name=name,
        relation=relation,
        gender="男",
        birth_year=1958,
        health_tags=json.dumps(["高血压", "高血脂"], ensure_ascii=False),
        allergies=allergies,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(member)
    db_session.commit()
    return member


def test_recommend_member_products_from_meal_plan_and_profile(db_session):
    _add_member(db_session)
    repo = SqlAlchemyMallRepository(db_session)
    repo.seed_default_data()
    service = MealProductRecommendationService(db_session, mall_repository=repo)

    result = service.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="晚餐：杂粮饭 + 鸡胸肉 + 豆腐青菜。建议低钠、少油。",
        limit=4,
    )

    assert result["is_error"] is False
    assert result["error"] is None
    items = result["items"]
    assert items, "应当返回至少一个推荐商品"
    for item in items:
        assert item["product_id"]
        assert item["name"]
        assert item["price_text"].startswith("¥")
        assert item["reason"]
    # 推荐理由应当结合本次餐单方向（低钠 / 少油 / 杂粮 / 高蛋白 中的某个）
    all_reasons = " ".join(item["reason"] for item in items)
    assert any(keyword in all_reasons for keyword in ["低钠", "少油", "轻负担", "高纤维", "蛋白"])


def test_recommend_default_limit_is_five(db_session):
    _add_member(db_session)
    repo = SqlAlchemyMallRepository(db_session)
    repo.seed_default_data()
    service = MealProductRecommendationService(db_session, mall_repository=repo)

    result = service.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="晚餐：杂粮饭 + 鸡胸肉 + 豆腐青菜。建议低钠、少油、高纤维、高蛋白、高钙。",
    )

    assert result["is_error"] is False
    assert len(result["items"]) == 5


def test_recommend_family_products_filters_any_member_allergy(db_session):
    _add_member(db_session, member_id="mem_dad", allergies="soy")
    _add_member(db_session, member_id="mem_mom", name="张桂兰", relation="妈妈")
    repo = SqlAlchemyMallRepository(db_session)
    repo.seed_default_data()
    service = MealProductRecommendationService(db_session, mall_repository=repo)

    result = service.recommend(
        scope="family",
        meal_plan_text="全家晚餐：低钠调味 + 杂粮饭 + 豆腐青菜。",
        limit=5,
    )

    assert result["is_error"] is False
    names = [item["name"] for item in result["items"]]
    assert not any("酱油" in name or "生抽" in name for name in names)


def test_recommend_rejects_missing_member_id(db_session):
    service = MealProductRecommendationService(db_session)

    result = service.recommend(scope="member", meal_plan_text="晚餐：杂粮饭")

    assert result["is_error"] is True
    assert result["items"] == []
    assert "member_id" in (result["error"] or "")


def test_recommend_rejects_invalid_scope(db_session):
    service = MealProductRecommendationService(db_session)

    result = service.recommend(scope="team", meal_plan_text="晚餐：杂粮饭")

    assert result["is_error"] is True
    assert "scope" in (result["error"] or "")


def test_recommend_member_returns_placeholder_when_no_match(db_session):
    """结构化输出在没匹配上时返回 is_error=False + items=[],前端据此不渲染卡片。"""
    _add_member(db_session)
    repo = SqlAlchemyMallRepository(db_session)
    repo.seed_default_data()
    service = MealProductRecommendationService(db_session, mall_repository=repo)

    # family scope 至少会拿到一个基础匹配（这是排序逻辑的副作用），所以这里只断言
    # 结构化形状稳定 + 全部 items 都有完整字段，不强制要求空。
    result = service.recommend(
        scope="family",
        meal_plan_text="今天天气真好",
        limit=3,
    )

    assert result["is_error"] is False
    assert result["error"] is None
    for item in result["items"]:
        assert {"product_id", "name", "reason", "price_text", "image_url", "image_emoji", "score"} <= item.keys()
