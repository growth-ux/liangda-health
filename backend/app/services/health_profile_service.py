from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.device import DeviceDailyMetric
from app.models.member import Member
from app.repositories.device_repository import SqlAlchemyDeviceRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.services.device_service import DeviceService


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
    diet_principles: list[str]
    avoid_tags: list[str]
    today_modifiers: list[str]
    source_notes: list[str]


@dataclass(frozen=True)
class FamilyHealthProfile:
    scope: str
    members: list[HealthProfile]
    shared_principles: list[str]
    shared_avoid_tags: list[str]
    family_modifiers: list[str]
    member_adjustments: list[str]
    source_notes: list[str]


class HealthProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.member_repository = SqlAlchemyMemberRepository(db)
        self.device_repository = SqlAlchemyDeviceRepository(db)
        self.device_service = DeviceService(db)

    def get_member_profile(self, member_id: str) -> HealthProfile:
        member = self.member_repository.get_member(member_id)
        if member is None:
            raise ValueError("member not found")
        return self._build_member_profile(member)

    def get_family_profile(self) -> FamilyHealthProfile:
        members = self.db.query(Member).order_by(Member.created_at.desc(), Member.id.desc()).all()
        profiles = [self._build_member_profile(member) for member in members]
        shared_principles = _unique(item for profile in profiles for item in profile.diet_principles)
        shared_avoid_tags = _unique(item for profile in profiles for item in profile.avoid_tags)
        family_modifiers = _unique(item for profile in profiles for item in profile.today_modifiers)
        adjustments = [self._member_adjustment(profile) for profile in profiles]
        source_notes = _unique(item for profile in profiles for item in profile.source_notes)
        return FamilyHealthProfile(
            scope="family",
            members=profiles,
            shared_principles=shared_principles,
            shared_avoid_tags=shared_avoid_tags,
            family_modifiers=family_modifiers,
            member_adjustments=[item for item in adjustments if item],
            source_notes=source_notes,
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

        self._apply_health_rules(health_tags, principles, avoid_tags)
        self._apply_bmi_rules(bmi, principles, avoid_tags)
        self._apply_age_rules(age, principles)

        metrics = self.device_repository.list_metrics_for_dates(member.member_id, _recent_7_days())
        modifiers = self._device_modifiers(metrics, principles)
        source_notes = ["健康档案"]
        if metrics:
            source_notes.append("最近7天手环")

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
            diet_principles=_unique(principles),
            avoid_tags=_unique([*avoid_tags, *allergies]),
            today_modifiers=_unique(modifiers),
            source_notes=source_notes,
        )

    def _apply_health_rules(self, health_tags: list[str], principles: list[str], avoid_tags: list[str]) -> None:
        if _has_tag(health_tags, ("高血压", "血压偏高", "血压高")):
            principles.extend(["低钠", "清淡", "足量蔬菜"])
            avoid_tags.extend(["腌制品", "咸菜", "浓汤", "重盐调味"])
        if _has_tag(health_tags, ("糖尿病", "血糖偏高", "控糖", "血糖高")):
            principles.extend(["控糖", "低GI", "主食定量"])
            avoid_tags.extend(["甜饮", "甜点", "精制主食过量"])
        if _has_tag(health_tags, ("高血脂",)):
            principles.extend(["少油", "优质蛋白", "高纤维"])
            avoid_tags.extend(["油炸", "肥肉", "动物油"])
        if _has_tag(health_tags, ("骨质疏松", "骨密度低")):
            principles.extend(["高钙", "优质蛋白", "维生素D"])
            avoid_tags.extend(["长期低蛋白", "过量浓茶咖啡"])
        if _has_tag(health_tags, ("痛风", "尿酸偏高")):
            principles.extend(["低嘌呤", "足量饮水"])
            avoid_tags.extend(["动物内脏", "浓肉汤", "酒"])
        if _has_tag(health_tags, ("胃肠",)):
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

    def _device_modifiers(self, metrics: list[DeviceDailyMetric], principles: list[str]) -> list[str]:
        if not metrics:
            return []
        averages = _metric_averages(metrics)
        modifiers: list[str] = []
        if averages.get("sleep_hours", 8) < 6.5:
            modifiers.append("睡眠近期不足，晚餐建议清淡并避免浓茶咖啡")
        if averages.get("steps", 10000) < 5000:
            modifiers.append("步数近期偏低，晚餐主食稍减并减少油炸高糖")
        systolic = averages.get("systolic_bp")
        diastolic = averages.get("diastolic_bp")
        if (systolic is not None and systolic >= 130) or (diastolic is not None and diastolic >= 85):
            modifiers.append("血压近期偏高，今天低钠策略更严格")
            principles.append("低钠")
        if averages.get("avg_heart_rate", 0) >= 90:
            modifiers.append("心率近期偏高，避免刺激性饮品并关注状态")
        latest = metrics[-1]
        if latest.blood_oxygen < 95:
            modifiers.append("最近血氧偏低，建议复测并关注身体状态")
        return modifiers

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
