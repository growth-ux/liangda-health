import json
from datetime import date, timedelta

from app.models.device import DeviceDailyMetric
from app.models.health_fact import HealthFact
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


def _add_fact(
    db_session,
    *,
    member_id: str = "mem_mom",
    fact_id: str = "fact_1",
    fact_type: str = "metric",
    name: str = "总胆固醇偏高",
    value: str | None = "6.1",
    unit: str | None = "mmol/L",
    reference_range: str | None = "<5.2",
    status: str = "warning",
    source_document_id: str = "doc_checkup",
    source_page_no: int = 3,
    source_chunk_id: str | None = "chunk_1",
    evidence_text: str = "总胆固醇高于参考范围",
) -> None:
    db_session.add(
        HealthFact(
            fact_id=fact_id,
            member_id=member_id,
            fact_type=fact_type,
            name=name,
            value=value,
            unit=unit,
            reference_range=reference_range,
            status=status,
            source_document_id=source_document_id,
            source_page_no=source_page_no,
            source_chunk_id=source_chunk_id,
            evidence_text=evidence_text,
        )
    )
    db_session.commit()


class FakeMemoryService:
    def __init__(self, items=None):
        self.items = items or []
        self.calls = []
        self.list_calls = []

    def search(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return self.items

    def list_profile_memories(self, member_id=None, limit=50):
        self.list_calls.append((member_id, limit))
        return self.items


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


def test_health_profile_maps_health_fact_to_risk_and_principles(db_session):
    _add_member(db_session, health_tags=[])
    _add_fact(db_session, name="总胆固醇偏高")

    profile = HealthProfileService(db_session).get_member_profile("mem_mom")

    assert "血脂偏高" in profile.long_term_risks
    assert "少油" in profile.diet_principles
    assert "高纤维" in profile.diet_principles
    assert "油炸" in profile.avoid_tags
    assert "报告健康事实" in profile.source_notes
    assert any("总胆固醇偏高" in note and "doc_checkup 第 3 页" in note for note in profile.evidence_notes)


def test_health_profile_keeps_low_sodium_above_salty_memory(db_session):
    from app.services.memory_service import MemoryItem

    _add_member(db_session, health_tags=[])
    _add_fact(db_session, name="血压偏高", evidence_text="收缩压偏高")
    memory = FakeMemoryService([MemoryItem(content="爸爸喜欢咸口", memory_type="preference", member_id="mem_mom")])

    profile = HealthProfileService(db_session, memory_service=memory).get_member_profile("mem_mom")

    assert "低钠" in profile.diet_principles
    assert "重盐调味" in profile.avoid_tags
    assert "爸爸喜欢咸口" in profile.preferences
    assert "爸爸喜欢咸口" not in profile.avoid_tags


def test_health_profile_memory_avoidance_stays_out_of_health_avoid_tags(db_session):
    from app.services.memory_service import MemoryItem

    _add_member(db_session, member_id="mem_dad", name="李建国", relation="爸爸", gender="男", health_tags=["高血压"])
    memory = FakeMemoryService([MemoryItem(content="爸爸不喜欢鱼", memory_type="avoidance", member_id="mem_dad")])

    profile = HealthProfileService(db_session, memory_service=memory).get_member_profile("mem_dad")

    assert memory.list_calls == [("mem_dad", 50)]
    assert memory.calls == []
    assert "爸爸不喜欢鱼" in profile.preferences
    assert "爸爸不喜欢鱼" not in profile.avoid_tags
    assert "互动记忆" in profile.source_notes


def test_health_profile_uses_member_memory_full_recall_for_preferences(db_session):
    from app.services.memory_service import MemoryItem

    _add_member(db_session, member_id="mem_dad", name="李建国", relation="爸爸", gender="男", health_tags=[])
    memory = FakeMemoryService([MemoryItem(content="爸爸不喜欢鱼", memory_type="avoidance", member_id="mem_dad")])

    profile = HealthProfileService(db_session, memory_service=memory).get_member_profile("mem_dad")

    assert memory.list_calls == [("mem_dad", 50)]
    assert memory.calls == []
    assert "爸爸不喜欢鱼" in profile.preferences


def test_family_profile_merges_health_facts_and_family_memory(db_session):
    from app.services.memory_service import MemoryItem

    _add_member(db_session, member_id="mem_mom", name="张桂兰", relation="妈妈", health_tags=[])
    _add_member(db_session, member_id="mem_dad", name="李建国", relation="爸爸", gender="男", health_tags=[])
    _add_fact(db_session, member_id="mem_mom", fact_id="fact_bp", name="血压偏高")
    _add_fact(db_session, member_id="mem_dad", fact_id="fact_sugar", name="血糖偏高")
    memory = FakeMemoryService([MemoryItem(content="全家周末在家做饭", memory_type="preference")])

    profile = HealthProfileService(db_session, memory_service=memory).get_family_profile()

    assert set(memory.list_calls[:2]) == {("mem_mom", 50), ("mem_dad", 50)}
    assert memory.list_calls[-1] == (None, 50)
    assert "血压偏高" in profile.shared_risks
    assert "血糖风险" in profile.shared_risks
    assert "低钠" in profile.shared_principles
    assert "控糖" in profile.shared_principles
    assert "重盐调味" in profile.shared_avoid_tags
    assert "甜饮" in profile.shared_avoid_tags
    assert "全家周末在家做饭" in profile.family_preferences
