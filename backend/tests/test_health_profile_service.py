import json
from datetime import date, timedelta

from app.models.device import DeviceDailyMetric
from app.models.member import Member
from app.services.health_profile_service import HealthProfileService


def _add_member(
    db_session,
    *,
    member_id: str = "mem_mom",
    name: str = "张桂兰",
    relation: str = "妈妈",
    gender: str = "女",
    birth_year: int = 1960,
    health_tags: list[str] | None = None,
    allergies: str | None = None,
    taste_preferences: str | None = None,
    height_cm: int | None = 160,
    weight_kg: int | None = 62,
) -> Member:
    member = Member(
        member_id=member_id,
        name=name,
        relation=relation,
        gender=gender,
        birth_year=birth_year,
        height_cm=height_cm,
        weight_kg=weight_kg,
        health_tags=json.dumps(health_tags or [], ensure_ascii=False),
        allergies=allergies,
        taste_preferences=taste_preferences,
    )
    db_session.add(member)
    db_session.commit()
    return member


def _add_metric(
    db_session,
    *,
    member_id: str,
    days_ago: int,
    steps: int = 7000,
    avg_heart_rate: int = 72,
    systolic_bp: int = 122,
    diastolic_bp: int = 78,
    sleep_hours: float = 7.2,
    blood_oxygen: int = 98,
) -> None:
    db_session.add(
        DeviceDailyMetric(
            member_id=member_id,
            metric_date=date.today() - timedelta(days=days_ago),
            steps=steps,
            avg_heart_rate=avg_heart_rate,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
            sleep_hours=sleep_hours,
            blood_oxygen=blood_oxygen,
            sync_status="success",
            sync_source="test",
        )
    )
    db_session.commit()


def test_health_profile_maps_hypertension_to_low_sodium(db_session):
    _add_member(db_session, health_tags=["高血压"], allergies="花生", taste_preferences="清淡")

    profile = HealthProfileService(db_session).get_member_profile("mem_mom")

    assert profile.name == "张桂兰"
    assert "低钠" in profile.diet_principles
    assert "腌制品" in profile.avoid_tags
    assert "花生" in profile.allergies
    assert "清淡" in profile.taste_preferences


def test_health_profile_uses_device_bp_as_today_modifier(db_session):
    _add_member(db_session, health_tags=[])
    for days_ago in range(7):
        _add_metric(db_session, member_id="mem_mom", days_ago=days_ago, systolic_bp=136, diastolic_bp=88)

    profile = HealthProfileService(db_session).get_member_profile("mem_mom")

    assert "血压近期偏高，今天低钠策略更严格" in profile.today_modifiers
    assert "低钠" in profile.diet_principles


def test_family_profile_merges_shared_principles_and_member_adjustments(db_session):
    _add_member(db_session, member_id="mem_mom", name="张桂兰", relation="妈妈", health_tags=["高血压"])
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=["糖尿病"],
        birth_year=1958,
    )

    profile = HealthProfileService(db_session).get_family_profile()

    assert "低钠" in profile.shared_principles
    assert "控糖" in profile.shared_principles
    assert any("妈妈" in item and "低钠" in item for item in profile.member_adjustments)
    assert any("爸爸" in item and "控糖" in item for item in profile.member_adjustments)
