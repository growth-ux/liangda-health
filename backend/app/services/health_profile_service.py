from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.device import DeviceDailyMetric
from app.models.health_fact import HealthFact
from app.models.member import Member
from app.repositories.device_repository import SqlAlchemyDeviceRepository
from app.repositories.health_fact_repository import SqlAlchemyHealthFactRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.services.device_service import DeviceService
from app.services.memory_service import MemoryItem, MemoryService


@dataclass(frozen=True)
class HealthProfile:
    scope: str
    member_id: str | None
    name: str
    relation: str
    age: int
    bmi: float | None
    health_tags: list[str]
    allergies: list[str]
    taste_preferences: list[str]
    long_term_risks: list[str]
    recent_states: list[str]
    diet_principles: list[str]
    avoid_tags: list[str]
    preferences: list[str]
    goals: list[str]
    marketing_feedback: list[str]
    today_modifiers: list[str]
    source_notes: list[str]
    evidence_notes: list[str]


@dataclass(frozen=True)
class FamilyHealthProfile:
    scope: str
    members: list[HealthProfile]
    shared_risks: list[str]
    shared_principles: list[str]
    shared_avoid_tags: list[str]
    family_preferences: list[str]
    family_goals: list[str]
    family_marketing_feedback: list[str]
    family_modifiers: list[str]
    member_adjustments: list[str]
    source_notes: list[str]
    evidence_notes: list[str]


class HealthProfileService:
    def __init__(self, db: Session, memory_service: MemoryService | None = None):
        self.db = db
        self.member_repository = SqlAlchemyMemberRepository(db)
        self.device_repository = SqlAlchemyDeviceRepository(db)
        self.fact_repository = SqlAlchemyHealthFactRepository(db)
        self.device_service = DeviceService(db)
        self.memory_service = memory_service

    def get_member_profile(self, member_id: str) -> HealthProfile:
        member = self.member_repository.get_member(member_id)
        if member is None:
            raise ValueError("member not found")
        return self._build_member_profile(member)

    def get_family_profile(self) -> FamilyHealthProfile:
        members = self.db.query(Member).order_by(Member.created_at.desc(), Member.id.desc()).all()
        profiles = [self._build_member_profile(member) for member in members]
        family_memory = self._memory_groups("全家 饮食 偏好 排斥 阶段目标 购买反馈")
        shared_risks = _unique(item for profile in profiles for item in profile.long_term_risks)
        shared_principles = _unique(item for profile in profiles for item in profile.diet_principles)
        shared_avoid_tags = _unique(item for profile in profiles for item in profile.avoid_tags)
        family_modifiers = _unique(item for profile in profiles for item in profile.today_modifiers)
        adjustments = [self._member_adjustment(profile) for profile in profiles]
        source_notes = _unique(
            [
                *(item for profile in profiles for item in profile.source_notes),
                *(["互动记忆"] if any(family_memory.values()) else []),
            ]
        )
        evidence_notes = _unique(item for profile in profiles for item in profile.evidence_notes)
        return FamilyHealthProfile(
            scope="family",
            members=profiles,
            shared_risks=shared_risks,
            shared_principles=shared_principles,
            shared_avoid_tags=shared_avoid_tags,
            family_preferences=family_memory["preferences"],
            family_goals=family_memory["goals"],
            family_marketing_feedback=family_memory["marketing_feedback"],
            family_modifiers=family_modifiers,
            member_adjustments=[item for item in adjustments if item],
            source_notes=source_notes,
            evidence_notes=evidence_notes,
        )

    def _build_member_profile(self, member: Member) -> HealthProfile:
        self.device_service.ensure_recent_7_days(member.member_id)
        health_tags = _safe_json_list(member.health_tags)
        allergies = _split_csv(member.allergies)
        taste_preferences = _split_csv(member.taste_preferences)
        age = max(0, datetime.now().year - member.birth_year)
        bmi = _bmi(member)
        principles: list[str] = []
        avoid_tags: list[str] = []
        long_term_risks: list[str] = []
        recent_states: list[str] = []
        evidence_notes: list[str] = []

        self._apply_health_rules(health_tags, principles, avoid_tags, long_term_risks)
        facts = self.fact_repository.list_by_member(member.member_id)
        self._apply_fact_rules(facts, principles, avoid_tags, long_term_risks, evidence_notes)
        self._apply_bmi_rules(bmi, principles, avoid_tags)
        self._apply_age_rules(age, principles)

        metrics = self.device_repository.list_metrics_for_dates(member.member_id, _recent_7_days())
        modifiers = self._device_modifiers(metrics, principles, recent_states)
        memory_groups = self._memory_groups(
            f"{member.name} {member.relation} 饮食 偏好 排斥 阶段目标 购买反馈",
            member_id=member.member_id,
        )
        preferences = _unique([*taste_preferences, *memory_groups["preferences"]])
        source_notes = ["健康档案"]
        if any(fact.status in {"warning", "danger"} for fact in facts):
            source_notes.append("报告健康事实")
        if metrics:
            source_notes.append("最近7天手环")
        if any(memory_groups.values()):
            source_notes.append("互动记忆")

        return HealthProfile(
            scope="member",
            member_id=member.member_id,
            name=member.name,
            relation=member.relation,
            age=age,
            bmi=bmi,
            health_tags=health_tags,
            allergies=allergies,
            taste_preferences=taste_preferences,
            long_term_risks=_unique(long_term_risks),
            recent_states=_unique(recent_states),
            diet_principles=_unique(principles),
            avoid_tags=_unique([*avoid_tags, *allergies]),
            preferences=preferences,
            goals=memory_groups["goals"],
            marketing_feedback=memory_groups["marketing_feedback"],
            today_modifiers=_unique(modifiers),
            source_notes=source_notes,
            evidence_notes=_unique(evidence_notes),
        )

    def _apply_health_rules(
        self,
        health_tags: list[str],
        principles: list[str],
        avoid_tags: list[str],
        long_term_risks: list[str],
    ) -> None:
        if _has_tag(health_tags, ("高血压", "血压偏高", "血压高")):
            long_term_risks.append("血压偏高")
            principles.extend(["低钠", "清淡", "足量蔬菜"])
            avoid_tags.extend(["腌制品", "咸菜", "浓汤", "重盐调味"])
        if _has_tag(health_tags, ("糖尿病", "血糖偏高", "控糖", "血糖高")):
            long_term_risks.append("血糖风险")
            principles.extend(["控糖", "低GI", "主食定量"])
            avoid_tags.extend(["甜饮", "甜点", "精制主食过量"])
        if _has_tag(health_tags, ("高血脂", "血脂偏高")):
            long_term_risks.append("血脂偏高")
            principles.extend(["少油", "优质蛋白", "高纤维"])
            avoid_tags.extend(["油炸", "肥肉", "动物油"])
        if _has_tag(health_tags, ("骨质疏松", "骨密度低")):
            long_term_risks.append("骨密度风险")
            principles.extend(["高钙", "优质蛋白", "维生素D"])
            avoid_tags.extend(["长期低蛋白", "过量浓茶咖啡"])
        if _has_tag(health_tags, ("痛风", "尿酸偏高")):
            long_term_risks.append("尿酸风险")
            principles.extend(["低嘌呤", "足量饮水"])
            avoid_tags.extend(["动物内脏", "浓肉汤", "酒"])
        if _has_tag(health_tags, ("胃肠",)):
            long_term_risks.append("胃肠敏感")
            principles.extend(["规律", "温和", "少刺激"])
            avoid_tags.extend(["辛辣", "生冷", "过油"])

    def _apply_bmi_rules(self, bmi: float | None, principles: list[str], avoid_tags: list[str]) -> None:
        if bmi is None:
            return
        if bmi >= 24:
            principles.extend(["控制总热量", "高纤维", "晚餐减轻"])
            avoid_tags.extend(["夜宵", "油炸", "高糖饮料"])
        elif bmi < 18.5:
            principles.extend(["保证能量", "优质蛋白"])

    def _apply_age_rules(self, age: int, principles: list[str]) -> None:
        if age >= 60:
            principles.extend(["高钙", "优质蛋白", "易消化"])
        elif age < 18:
            principles.extend(["生长发育", "优质蛋白", "高钙"])

    def _device_modifiers(
        self,
        metrics: list[DeviceDailyMetric],
        principles: list[str],
        recent_states: list[str],
    ) -> list[str]:
        if not metrics:
            return []
        averages = _metric_averages(metrics)
        modifiers: list[str] = []
        if averages.get("sleep_hours", 8) < 6.5:
            recent_states.append("睡眠不足")
            modifiers.append("睡眠近期不足，晚餐建议清淡并避免浓茶咖啡")
        if averages.get("steps", 10000) < 5000:
            recent_states.append("步数偏低")
            modifiers.append("步数近期偏低，晚餐主食稍减并减少油炸高糖")
        systolic = averages.get("systolic_bp")
        diastolic = averages.get("diastolic_bp")
        if (systolic is not None and systolic >= 130) or (diastolic is not None and diastolic >= 85):
            recent_states.append("血压近期偏高")
            modifiers.append("血压近期偏高，今天低钠策略更严格")
            principles.append("低钠")
        if averages.get("avg_heart_rate", 0) >= 90:
            recent_states.append("心率近期偏高")
            modifiers.append("心率近期偏高，避免刺激性饮品并关注状态")
        latest = metrics[-1]
        if latest.blood_oxygen < 95:
            recent_states.append("血氧偏低")
            modifiers.append("最近血氧偏低，建议复测并关注身体状态")
        return modifiers

    def _apply_fact_rules(
        self,
        facts: list[HealthFact],
        principles: list[str],
        avoid_tags: list[str],
        long_term_risks: list[str],
        evidence_notes: list[str],
    ) -> None:
        for fact in facts:
            evidence_notes.append(f"报告事实：{fact.name}，来源 {fact.source_document_id} 第 {fact.source_page_no} 页")
            if fact.status not in {"warning", "danger"}:
                continue
            names = [fact.name, fact.evidence_text]
            if _has_tag(names, ("高血压", "血压偏高", "血压高")):
                long_term_risks.append("血压偏高")
                principles.extend(["低钠", "清淡", "足量蔬菜"])
                avoid_tags.extend(["腌制品", "咸菜", "浓汤", "重盐调味"])
            if _has_tag(names, ("糖尿病", "血糖偏高", "控糖", "血糖高")):
                long_term_risks.append("血糖风险")
                principles.extend(["控糖", "低GI", "主食定量"])
                avoid_tags.extend(["甜饮", "甜点", "精制主食过量"])
            if _has_tag(names, ("高血脂", "血脂偏高", "总胆固醇偏高", "甘油三酯偏高")):
                long_term_risks.append("血脂偏高")
                principles.extend(["少油", "优质蛋白", "高纤维"])
                avoid_tags.extend(["油炸", "肥肉", "动物油"])
            if _has_tag(names, ("骨质疏松", "骨密度低")):
                long_term_risks.append("骨密度风险")
                principles.extend(["高钙", "优质蛋白", "维生素D"])
                avoid_tags.extend(["长期低蛋白", "过量浓茶咖啡"])
            if _has_tag(names, ("痛风", "尿酸偏高")):
                long_term_risks.append("尿酸风险")
                principles.extend(["低嘌呤", "足量饮水"])
                avoid_tags.extend(["动物内脏", "浓肉汤", "酒"])
            if _has_tag(names, ("胃肠",)):
                long_term_risks.append("胃肠敏感")
                principles.extend(["规律", "温和", "少刺激"])
                avoid_tags.extend(["辛辣", "生冷", "过油"])

    def _memory_groups(self, query: str, member_id: str | None = None) -> dict[str, list[str]]:
        groups = {"preferences": [], "goals": [], "marketing_feedback": []}
        if self.memory_service is None:
            return groups
        items = self.memory_service.list_profile_memories(member_id=member_id, limit=50)
        for item in items:
            target = _memory_group(item)
            if target:
                groups[target].append(item.content)
        return {key: _unique(value) for key, value in groups.items()}

    @staticmethod
    def _member_adjustment(profile: HealthProfile) -> str:
        label = profile.relation or profile.name
        if "控糖" in profile.diet_principles:
            return f"{label}控糖：主食定量，甜饮甜点不安排。"
        if "低钠" in profile.diet_principles:
            return f"{label}低钠：不额外加咸菜、腌制品和重盐调味。"
        if "高钙" in profile.diet_principles:
            return f"{label}高钙：可增加牛奶、鸡蛋或豆制品。"
        if "控制总热量" in profile.diet_principles:
            return f"{label}控热量：晚餐主食稍减，少油炸。"
        return ""


def _recent_7_days() -> list[date]:
    return [date.today() - timedelta(days=offset) for offset in range(6, -1, -1)]


def _safe_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]


def _has_tag(tags: list[str], keywords: tuple[str, ...]) -> bool:
    return any(any(keyword in tag for keyword in keywords) for tag in tags)


def _bmi(member: Member) -> float | None:
    if not member.height_cm or not member.weight_kg or member.height_cm <= 0:
        return None
    return round(member.weight_kg / ((member.height_cm / 100) ** 2), 1)


def _metric_averages(metrics: list[DeviceDailyMetric]) -> dict[str, float]:
    if not metrics:
        return {}
    fields = ["steps", "avg_heart_rate", "systolic_bp", "diastolic_bp", "sleep_hours", "blood_oxygen"]
    return {
        field: sum(float(getattr(metric, field)) for metric in metrics) / len(metrics)
        for field in fields
    }


def _unique(items) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _memory_group(item: MemoryItem) -> str | None:
    text = item.content
    memory_type = item.memory_type or ""
    if memory_type == "goal" or any(keyword in text for keyword in ("目标", "最近要", "想控", "想减", "想增")):
        return "goals"
    if memory_type == "marketing_feedback" or any(keyword in text for keyword in ("贵", "便宜", "跳过", "购买", "不买")):
        return "marketing_feedback"
    if memory_type in {"preference", "avoidance"} or any(keyword in text for keyword in ("喜欢", "偏好", "不喜欢", "不吃", "排斥")):
        return "preferences"
    return None
