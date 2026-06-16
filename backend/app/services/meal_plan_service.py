from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.health_profile_service import FamilyHealthProfile, HealthProfile, HealthProfileService

logger = logging.getLogger(__name__)


class MealPlanGenerationError(Exception):
    pass


class LangChainMealPlanGenerator:
    def generate(self, prompt: str) -> str:
        if not settings.llm_api_key:
            raise MealPlanGenerationError("未配置模型 API Key，无法生成智能餐单")

        from langchain.chat_models import init_chat_model

        model = init_chat_model(
            model=settings.llm_model,
            model_provider="openai",
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )
        response = model.invoke(prompt)
        return _content_to_text(response.content).strip()


class MealPlanService:
    def __init__(self, db: Session, memory_service=None, generator=None):
        self.profile_service = HealthProfileService(db, memory_service=memory_service)
        self.generator = generator or LangChainMealPlanGenerator()

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
        prompt = _member_prompt(profile, goal=goal, meal_type=meal_type)
        logger.info(
            "meal_plan llm_generate start scope=member member_id=%s meal_type=%s prompt=%s",
            member_id,
            meal_type,
            prompt,
        )
        return self._generate(prompt)

    def build_family_plan(self, goal: str | None = None, meal_type: str = "day") -> str:
        profile = self.profile_service.get_family_profile()
        if not profile.members:
            return "当前没有可用家人，无法生成全家餐单。"
        prompt = _family_prompt(profile, goal=goal, meal_type=meal_type)
        logger.info(
            "meal_plan llm_generate start scope=family meal_type=%s prompt_chars=%s",
            meal_type,
            len(prompt),
        )
        return self._generate(prompt)

    def _generate(self, prompt: str) -> str:
        try:
            result = self.generator.generate(prompt)
        except MealPlanGenerationError as exc:
            logger.info("meal_plan llm_generate rejected reason=%s", exc)
            return f"Error: {exc}"
        except Exception:
            logger.exception("meal_plan llm_generate failed")
            return "Error: 模型生成餐单失败"
        logger.info("meal_plan llm_generate done output_chars=%s", len(result))
        return result


def _member_prompt(profile: HealthProfile, *, goal: str | None, meal_type: str) -> str:
    return "\n".join(
        [
            "你是粮达健康的家庭营养餐单助手。请基于健康画像生成餐单，不要使用固定模板。",
            "必须遵守：健康禁忌、过敏、报告事实和饮食原则优先于口味偏好；不做诊断，不替代医生。",
            "如果偏好与健康约束冲突，保留健康约束，并用温和替代方案满足偏好。",
            "输出要求：只输出给用户看的简体中文餐单；不要输出 member_id、内部字段名或工具调用信息。",
            f"餐单范围：{_meal_type_text(meal_type)}",
            f"本次目标：{goal or '无'}",
            "",
            "单人健康画像：",
            f"- 家人：{profile.name}（{profile.relation}）",
            f"- 年龄：{profile.age}",
            f"- BMI：{profile.bmi if profile.bmi is not None else '未知'}",
            f"- 健康标签：{_join_or(profile.health_tags, '无')}",
            f"- 长期风险：{_join_or(profile.long_term_risks, '无')}",
            f"- 近期状态：{_join_or(profile.recent_states, '无')}",
            f"- 饮食原则：{_join_or(profile.diet_principles, '均衡清淡')}",
            f"- 健康避免项：{_join_or(profile.avoid_tags, '高油高糖和过量重口调味')}",
            f"- 过敏：{_join_or(profile.allergies, '无')}",
            f"- 口味和互动偏好：{_join_or(profile.preferences, '无')}",
            f"- 阶段目标：{_join_or(profile.goals, '无')}",
            f"- 今日修正：{_join_or(profile.today_modifiers, '无')}",
            f"- 依据来源：{_join_or(profile.source_notes, '无')}",
            f"- 报告依据：{_join_or(profile.evidence_notes, '无')}",
            "",
            "请按以下结构输出：",
            "1. 家人和健康关注",
            "2. 早餐/午餐/晚餐，若只要求某一餐则只输出该餐",
            "3. 为什么这样安排",
            "4. 需要避免或替代的食物",
        ]
    )


def _family_prompt(profile: FamilyHealthProfile, *, goal: str | None, meal_type: str) -> str:
    members = [
        f"{item.name}（{item.relation}）：原则={_join_or(item.diet_principles, '均衡清淡')}；避免={_join_or(item.avoid_tags, '无')}；偏好={_join_or(item.preferences, '无')}"
        for item in profile.members
    ]
    return "\n".join(
        [
            "你是粮达健康的家庭营养餐单助手。请基于全家健康画像生成共餐餐单，不要使用固定模板。",
            "必须遵守：任一成员的过敏、健康禁忌、报告事实和饮食原则都优先于口味偏好。",
            "共餐方案要兼顾全家，成员差异用局部替换或份量调整解决；不做诊断，不替代医生。",
            "输出要求：只输出给用户看的简体中文餐单；不要输出 member_id、内部字段名或工具调用信息。",
            f"餐单范围：{_meal_type_text(meal_type)}",
            f"本次目标：{goal or '无'}",
            "",
            "全家健康画像：",
            f"- 共同风险：{_join_or(profile.shared_risks, '无')}",
            f"- 共餐原则：{_join_or(profile.shared_principles, '均衡清淡')}",
            f"- 共同避免项：{_join_or(profile.shared_avoid_tags, '高油高糖和过量重口调味')}",
            f"- 家庭偏好：{_join_or(profile.family_preferences, '无')}",
            f"- 家庭目标：{_join_or(profile.family_goals, '无')}",
            f"- 今日修正：{_join_or(profile.family_modifiers, '无')}",
            f"- 成员调整：{_join_or(profile.member_adjustments, '无')}",
            f"- 依据来源：{_join_or(profile.source_notes, '无')}",
            f"- 报告依据：{_join_or(profile.evidence_notes, '无')}",
            "",
            "成员画像摘要：",
            *[f"- {item}" for item in members],
            "",
            "请按以下结构输出：",
            "1. 全家共餐原则",
            "2. 早餐/午餐/晚餐，若只要求某一餐则只输出该餐",
            "3. 成员差异调整",
            "4. 需要避免或替代的食物",
        ]
    )


def _meal_type_text(meal_type: str) -> str:
    return {
        "breakfast": "早餐",
        "lunch": "午餐",
        "dinner": "晚餐",
        "day": "一日三餐",
    }.get(meal_type, "一日三餐")


def _join_or(items: list[str], fallback: str) -> str:
    return "、".join(items) if items else fallback


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content) if content is not None else ""
