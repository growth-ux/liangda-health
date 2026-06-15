import json

from app.models.member import Member
from app.services.meal_plan_service import MealPlanService


def _add_member(
    db_session,
    *,
    member_id: str,
    name: str,
    relation: str,
    gender: str = "女",
    birth_year: int = 1960,
    health_tags: list[str],
) -> None:
    db_session.add(
        Member(
            member_id=member_id,
            name=name,
            relation=relation,
            gender=gender,
            birth_year=birth_year,
            health_tags=json.dumps(health_tags, ensure_ascii=False),
        )
    )
    db_session.commit()


def test_meal_plan_member_outputs_day_meals_and_avoid_items(db_session):
    _add_member(
        db_session,
        member_id="mem_mom",
        name="张桂兰",
        relation="妈妈",
        health_tags=["高血压", "骨质疏松"],
    )

    result = MealPlanService(db_session).build_member_plan("mem_mom")

    assert "家人：张桂兰（妈妈）" in result
    assert "早餐：" in result
    assert "午餐：" in result
    assert "晚餐：" in result
    assert "低钠" in result
    assert "避免：" in result
    assert "咸菜" in result


def test_meal_plan_family_outputs_shared_menu_and_adjustments(db_session):
    _add_member(
        db_session,
        member_id="mem_mom",
        name="张桂兰",
        relation="妈妈",
        health_tags=["高血压"],
    )
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=["糖尿病"],
    )

    result = MealPlanService(db_session).build_family_plan()

    assert "全家共餐原则" in result
    assert "早餐：" in result
    assert "午餐：" in result
    assert "晚餐：" in result
    assert "成员调整：" in result
    assert "妈妈" in result
    assert "爸爸" in result
    assert "低钠" in result
    assert "控糖" in result
