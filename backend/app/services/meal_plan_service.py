from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.health_profile_service import FamilyHealthProfile, HealthProfile, HealthProfileService


class MealPlanService:
    def __init__(self, db: Session, memory_service=None):
        self.profile_service = HealthProfileService(db)
        self.memory_service = memory_service

    def build(
        self,
        *,
        scope: str,
        member_id: str | None = None,
        goal: str | None = None,
        meal_type: str = "day",
    ) -> str:
        if scope == "family":
            return self.build_family_plan(goal=goal, meal_type=meal_type)
        if scope == "member":
            if not member_id:
                return "Error: 单人餐单必须传入 member_id"
            return self.build_member_plan(member_id, goal=goal, meal_type=meal_type)
        return "Error: scope 只能是 member 或 family"

    def build_member_plan(self, member_id: str, goal: str | None = None, meal_type: str = "day") -> str:
        profile = self.profile_service.get_member_profile(member_id)
        memory_text = self._memory_text_for_member(profile)
        meals = _apply_memory_to_meals(_member_meals(profile), memory_text)
        return _format_member_plan(profile, meals, goal, meal_type, memory_text)

    def build_family_plan(self, goal: str | None = None, meal_type: str = "day") -> str:
        profile = self.profile_service.get_family_profile()
        memory_text = self._memory_text_for_family()
        meals = _apply_memory_to_meals(_family_meals(profile), memory_text)
        return _format_family_plan(profile, meals, goal, meal_type, memory_text)

    def _memory_text_for_member(self, profile: HealthProfile) -> str:
        if self.memory_service is None:
            return ""
        query = f"{profile.name} {profile.relation} 饮食 偏好 排斥"
        return self.memory_service.search_text(query, member_id=profile.member_id, limit=5)

    def _memory_text_for_family(self) -> str:
        if self.memory_service is None:
            return ""
        return self.memory_service.search_text("全家 饮食 偏好 排斥", limit=5)


def _member_meals(profile: HealthProfile) -> dict[str, str]:
    breakfast = "燕麦牛奶 + 水煮蛋 + 一小份低糖水果"
    lunch = "杂粮饭 + 清蒸鱼/鸡胸肉 + 西兰花 + 豆腐汤"
    dinner = "杂粮粥 + 豆腐青菜 + 少量瘦肉"

    if "控糖" in profile.diet_principles:
        breakfast = "无糖豆浆 + 鸡蛋 + 小份燕麦/全麦主食"
        lunch = "杂粮饭半碗 + 清蒸鱼 + 两份绿叶菜"
        dinner = "豆腐青菜汤 + 少量杂粮主食"
    elif "低钠" in profile.diet_principles:
        breakfast = "燕麦牛奶 + 水煮蛋 + 一小份水果"
        lunch = "杂粮饭 + 清蒸鱼/鸡胸肉 + 西兰花 + 清淡豆腐汤"
        dinner = "小米粥/杂粮粥 + 豆腐青菜 + 少量瘦肉"

    if "高钙" in profile.diet_principles and "牛奶" not in breakfast:
        breakfast = f"{breakfast} + 牛奶/酸奶"
    if "控制总热量" in profile.diet_principles or any("步数近期偏低" in item for item in profile.today_modifiers):
        dinner = f"{dinner}，主食量比午餐少一些"
    return {"breakfast": breakfast, "lunch": lunch, "dinner": dinner}


def _family_meals(profile: FamilyHealthProfile) -> dict[str, str]:
    breakfast = "无糖豆浆/牛奶 + 鸡蛋 + 燕麦/全麦主食 + 一小份水果"
    lunch = "杂粮饭 + 清蒸鱼/鸡胸肉 + 两份蔬菜 + 清淡豆腐汤"
    dinner = "杂粮粥 + 豆制品/瘦肉 + 深色蔬菜"

    if "控糖" in profile.shared_principles:
        breakfast = "无糖豆浆/牛奶 + 鸡蛋 + 小份燕麦/全麦主食"
        lunch = "杂粮饭定量 + 清蒸鱼/鸡胸肉 + 两份蔬菜"
    if "低钠" in profile.shared_principles:
        lunch = f"{lunch}，少盐调味"
        dinner = f"{dinner}，不配咸菜"
    if "控制总热量" in profile.shared_principles or any("步数近期偏低" in item for item in profile.family_modifiers):
        dinner = f"{dinner}，主食少于午餐"
    return {"breakfast": breakfast, "lunch": lunch, "dinner": dinner}


def _format_member_plan(
    profile: HealthProfile,
    meals: dict[str, str],
    goal: str | None,
    meal_type: str,
    memory_text: str = "",
) -> str:
    lines = [
        f"家人：{profile.name}（{profile.relation}）",
        f"健康关注：{_join_or(profile.health_tags, '暂无明确健康标签')}",
        f"饮食原则：{_join_or(profile.diet_principles, '均衡清淡')}",
    ]
    if goal:
        lines.append(f"本次目标：{goal}")
    if profile.today_modifiers:
        lines.append(f"今日修正：{_join_or(profile.today_modifiers, '')}")
    if _should_avoid_fish(memory_text):
        lines.append(f"个性化记忆：已避开{profile.relation or profile.name}不喜欢的鱼。")
    lines.append("")
    lines.extend(_meal_lines(meals, meal_type))
    lines.extend(
        [
            "",
            "原因：结合长期健康状态和最近手环状态，优先保证清淡、稳定主食和足量优质蛋白。",
            "",
            "避免：",
            f"- {_join_or(profile.avoid_tags, '高油高糖和过量重口调味')}",
        ]
    )
    return "\n".join(lines)


def _format_family_plan(
    profile: FamilyHealthProfile,
    meals: dict[str, str],
    goal: str | None,
    meal_type: str,
    memory_text: str = "",
) -> str:
    if not profile.members:
        return "当前没有可用家人，无法生成全家餐单。"
    lines = [
        f"全家共餐原则：{_join_or(profile.shared_principles, '均衡清淡')}",
        f"共同避免：{_join_or(profile.shared_avoid_tags, '高油高糖和过量重口调味')}",
    ]
    if goal:
        lines.append(f"本次目标：{goal}")
    if profile.family_modifiers:
        lines.append(f"今日修正：{_join_or(profile.family_modifiers, '')}")
    if _should_avoid_fish(memory_text):
        lines.append("个性化记忆：已避开家人不喜欢的鱼。")
    lines.append("")
    lines.extend(_meal_lines(meals, meal_type))
    if profile.member_adjustments:
        lines.extend(["", "成员调整："])
        lines.extend(f"- {item}" for item in profile.member_adjustments)
    return "\n".join(lines)


def _meal_lines(meals: dict[str, str], meal_type: str) -> list[str]:
    labels = {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
    }
    if meal_type in labels:
        return [f"{labels[meal_type]}：", f"- {meals[meal_type]}"]
    return [
        "早餐：",
        f"- {meals['breakfast']}",
        "",
        "午餐：",
        f"- {meals['lunch']}",
        "",
        "晚餐：",
        f"- {meals['dinner']}",
    ]


def _join_or(items: list[str], fallback: str) -> str:
    return "、".join(items) if items else fallback


def _apply_memory_to_meals(meals: dict[str, str], memory_text: str) -> dict[str, str]:
    if not _should_avoid_fish(memory_text):
        return meals
    return {
        key: value.replace("清蒸鱼/鸡胸肉", "鸡胸肉/豆腐")
        .replace("清蒸鱼", "鸡胸肉/豆腐")
        .replace("鱼", "鸡胸肉/豆腐")
        for key, value in meals.items()
    }


def _should_avoid_fish(memory_text: str) -> bool:
    return "不喜欢鱼" in memory_text or "不喜欢吃鱼" in memory_text or "不吃鱼" in memory_text
