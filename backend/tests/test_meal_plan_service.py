import json
from datetime import date, timedelta

from app.models.device import DeviceDailyMetric
from app.models.health_fact import HealthFact
from app.models.member import Member
from app.services.meal_plan_service import MealPlanService
from app.services.memory_service import MemoryItem


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


class FakeMealPlanGenerator:
    def __init__(self, response: str):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_meal_plan_member_outputs_day_meals_and_avoid_items(db_session):
    _add_member(
        db_session,
        member_id="mem_mom",
        name="张桂兰",
        relation="妈妈",
        health_tags=["高血压", "骨质疏松"],
    )

    generator = FakeMealPlanGenerator(
        "家人：张桂兰（妈妈）\n早餐：燕麦豆浆\n午餐：低钠菜饭\n晚餐：豆腐青菜\n避免：咸菜"
    )

    result = MealPlanService(db_session, generator=generator).build_member_plan("mem_mom")

    assert "家人：张桂兰（妈妈）" in result
    assert "早餐：" in result
    assert "午餐：" in result
    assert "晚餐：" in result
    assert "低钠" in generator.prompts[0]
    assert "避免：" in result
    assert "咸菜" in generator.prompts[0]
    assert "不要先写一大段健康画像" in generator.prompts[0]
    assert "健康背景最多一句话" in generator.prompts[0]
    assert "原因解释最多 2-3 条短句" in generator.prompts[0]
    assert "一小碗、一碗、一盘、一杯、一掌心、一个" in generator.prompts[0]
    assert "不要展开每个食材的克数、毫升数或配方级用量" in generator.prompts[0]


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

    generator = FakeMealPlanGenerator(
        "全家共餐原则：低钠、控糖\n早餐：无糖豆浆\n午餐：杂粮饭\n晚餐：豆腐青菜\n成员调整：妈妈低钠，爸爸控糖"
    )

    result = MealPlanService(db_session, generator=generator).build_family_plan()

    assert "全家共餐原则" in result
    assert "早餐：" in result
    assert "午餐：" in result
    assert "晚餐：" in result
    assert "成员调整：" in result
    assert "妈妈" in generator.prompts[0]
    assert "爸爸" in generator.prompts[0]
    assert "低钠" in generator.prompts[0]
    assert "控糖" in generator.prompts[0]
    assert "不要先写一大段家庭健康画像" in generator.prompts[0]
    assert "健康背景最多一句话" in generator.prompts[0]
    assert "原因解释最多 2-3 条短句" in generator.prompts[0]
    assert "一小碗、一碗、一盘、一杯、一掌心、一个" in generator.prompts[0]
    assert "只有用户明确要求精确克数、营养计算、热量估算或详细食谱时，才给克数" in generator.prompts[0]


class FakeMemoryService:
    def __init__(self, items):
        self.items = items
        self.calls = []
        self.list_calls = []

    def search(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return self.items

    def list_profile_memories(self, member_id=None, limit=50):
        self.list_calls.append((member_id, limit))
        return self.items


def test_meal_plan_member_avoids_fish_from_memory(db_session):
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=["高血压"],
    )
    memory = FakeMemoryService([MemoryItem(content="爸爸不喜欢鱼", memory_type="avoidance", member_id="mem_dad")])

    generator = FakeMealPlanGenerator("家人：李建国（爸爸）\n午餐：鸡胸肉/豆腐 + 蔬菜\n避免：咸菜")

    result = MealPlanService(db_session, memory_service=memory, generator=generator).build_member_plan("mem_dad")

    assert memory.list_calls == [("mem_dad", 50)]
    assert "清蒸鱼" not in result
    assert "鸡胸肉/豆腐" in result
    assert "爸爸不喜欢鱼" in generator.prompts[0]
    assert "低钠" in generator.prompts[0]


def test_meal_plan_member_keeps_health_safety_above_memory(db_session):
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=["高血压"],
    )
    memory = FakeMemoryService([MemoryItem(content="爸爸喜欢咸口", memory_type="preference", member_id="mem_dad")])

    generator = FakeMealPlanGenerator("家人：李建国（爸爸）\n晚餐：低钠蒸菜\n避免：重盐调味")

    result = MealPlanService(db_session, memory_service=memory, generator=generator).build_member_plan("mem_dad")

    assert "低钠" in result
    assert "爸爸喜欢咸口" in generator.prompts[0]
    assert "重盐调味" in generator.prompts[0]


def test_meal_plan_service_builds_report_and_device_evidence_items(db_session):
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=[],
    )
    db_session.add(
        HealthFact(
            fact_id="fact_bp",
            member_id="mem_dad",
            fact_type="metric",
            name="血压偏高",
            value="152",
            unit="mmHg",
            reference_range="90-140",
            status="warning",
            source_document_id="doc_checkup",
            source_page_no=3,
            source_chunk_id="chunk_1",
            evidence_text="收缩压高于参考范围",
        )
    )
    for days_ago in range(7):
        db_session.add(
            DeviceDailyMetric(
                member_id="mem_dad",
                metric_date=date.today() - timedelta(days=days_ago),
                steps=4200,
                avg_heart_rate=72,
                systolic_bp=136,
                diastolic_bp=88,
                sleep_hours=5.2,
                blood_oxygen=98,
                sync_status="success",
                sync_source="test",
            )
        )
    db_session.commit()

    items = MealPlanService(db_session, generator=FakeMealPlanGenerator("ok")).get_evidence_items(
        scope="member",
        member_id="mem_dad",
    )

    assert [item.type for item in items] == ["report_fact", "device"]
    assert items[0].title == "李建国·血压偏高"
    assert items[0].source_label == "doc_checkup p3"
    assert "睡眠不足" in items[1].excerpt
    assert "步数偏低" in items[1].excerpt
