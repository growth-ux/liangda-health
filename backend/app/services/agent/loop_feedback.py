"""Loop Engineering: 反馈理解层 — 冲突检测 + 安全替代策略。

检测用户偏好/规避记忆与健康约束之间的冲突，并生成安全替代建议。
冲突不会阻止偏好记录，但会阻止按冲突偏好直接推荐高风险内容。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── 冲突规则表 ─────────────────────────────────────────────────────
# (偏好关键词, 健康约束关键词, 冲突描述, 安全替代建议)
CONFLICT_RULES: list[tuple[tuple[str, ...], tuple[str, ...], str, str]] = [
    # 咸口 vs 血压
    (
        ("咸口", "咸", "重口", "重盐", "口味重"),
        ("血压偏高", "高血压", "低钠"),
        "喜欢咸口但血压偏高",
        "可用低钠酱油、香辛料、醋汁、柠檬汁提味替代",
    ),
    # 甜食 vs 控糖
    (
        ("甜", "甜食", "糖", "甜品", "蛋糕", "巧克力"),
        ("血糖风险", "糖尿病", "控糖"),
        "喜欢甜食但需控糖",
        "可用无糖酸奶、低糖水果（蓝莓/草莓）、坚果替代",
    ),
    # 油炸 vs 血脂
    (
        ("油炸", "炸鸡", "炸", "煎炸", "酥脆"),
        ("血脂偏高", "高血脂"),
        "喜欢油炸但血脂偏高",
        "可用空气炸锅、清蒸、少油煎替代",
    ),
    # 高脂 vs 血脂
    (
        ("肥肉", "五花肉", "动物油", "猪油"),
        ("血脂偏高", "高血脂"),
        "偏好高脂食材但血脂偏高",
        "可用鸡胸肉、鱼虾、豆腐、蛋清等低脂优质蛋白替代",
    ),
    # 酒 vs 多种禁忌
    (
        ("喝酒", "白酒", "啤酒", "红酒", "饮酒"),
        ("尿酸", "痛风", "血压偏高", "血脂偏高", "肝"),
        "有饮酒偏好但存在健康禁忌",
        "可用无醇饮品、气泡水加柠檬、淡茶替代",
    ),
    # 零食 vs 体重
    (
        ("零食", "薯片", "饼干", "膨化"),
        ("控制总热量", "BMI"),
        "喜欢吃零食但需控制体重",
        "可用坚果小把、低糖酸奶、水果替代",
    ),
]

# 规避记忆 vs 健康需求的冲突（用户不吃某物但该物是推荐的健康替代品）
AVOIDANCE_CONFLICT_RULES: list[tuple[tuple[str, ...], tuple[str, ...], str, str]] = [
    (
        ("鱼", "海鲜", "虾"),
        ("优质蛋白", "高蛋白"),
        "排斥鱼类但需要优质蛋白",
        "可用鸡胸肉、豆腐、鸡蛋、牛奶替代蛋白来源",
    ),
    (
        ("蔬菜", "青菜", "绿叶菜"),
        ("高纤维", "足量蔬菜"),
        "排斥蔬菜但需要膳食纤维",
        "可用水果、杂粮、菌菇类替代纤维来源",
    ),
    (
        ("牛奶", "奶"),
        ("高钙", "骨密度"),
        "排斥乳制品但需要补钙",
        "可用豆制品、芝麻、深绿叶蔬菜替代钙来源",
    ),
]


@dataclass(frozen=True)
class Conflict:
    """一条偏好/规避与健康约束的冲突记录。"""
    preference: str
    constraint: str
    description: str
    safe_alternative: str


def detect_conflicts(
    *,
    preferences: list[str],
    avoidance_memories: list[str],
    avoid_tags: list[str],
    long_term_risks: list[str],
    health_tags: list[str],
) -> list[dict]:
    """检测偏好/规避记忆与健康约束之间的冲突。

    返回冲突字典列表，每个包含 preference, constraint, description, safe_alternative。
    """
    conflicts: list[dict] = []

    # 收集所有健康约束文本
    constraint_text = " ".join(avoid_tags + long_term_risks + health_tags)

    # 1) 正向偏好 vs 健康约束
    for pref in preferences:
        for pref_keywords, constraint_keywords, description, alternative in CONFLICT_RULES:
            if not any(kw in pref for kw in pref_keywords):
                continue
            if not any(kw in constraint_text for kw in constraint_keywords):
                continue
            conflict = {
                "preference": pref,
                "constraint": _matched_constraint(constraint_text, constraint_keywords),
                "description": description,
                "safe_alternative": alternative,
            }
            if conflict not in conflicts:
                conflicts.append(conflict)
                logger.info(
                    "conflict_detected type=preference preference=%s constraint=%s",
                    pref,
                    conflict["constraint"],
                )

    # 2) 规避记忆 vs 健康需求
    need_text = " ".join(avoid_tags + long_term_risks)
    for avoid_mem in avoidance_memories:
        for avoid_keywords, need_keywords, description, alternative in AVOIDANCE_CONFLICT_RULES:
            if not any(kw in avoid_mem for kw in avoid_keywords):
                continue
            if not any(kw in need_text for kw in need_keywords):
                continue
            conflict = {
                "preference": avoid_mem,
                "constraint": _matched_constraint(need_text, need_keywords),
                "description": description,
                "safe_alternative": alternative,
            }
            if conflict not in conflicts:
                conflicts.append(conflict)
                logger.info(
                    "conflict_detected type=avoidance avoidance=%s constraint=%s",
                    avoid_mem,
                    conflict["constraint"],
                )

    return conflicts


def suggest_safe_alternatives(conflicts: list[dict] | None) -> list[str]:
    """从冲突列表中提取安全替代建议文本。"""
    if not conflicts:
        return []
    seen: set[str] = set()
    alternatives: list[str] = []
    for conflict in conflicts:
        alt = conflict.get("safe_alternative", "")
        if alt and alt not in seen:
            alternatives.append(alt)
            seen.add(alt)
    return alternatives


def _matched_constraint(text: str, keywords: tuple[str, ...]) -> str:
    """返回文本中命中的第一个约束关键词。"""
    for kw in keywords:
        if kw in text:
            return kw
    return keywords[0]


class ConflictDetector:
    """可注入的冲突检测器，便于测试时 mock。"""

    def detect(self, **kwargs) -> list[dict]:
        return detect_conflicts(**kwargs)

    def suggest(self, conflicts: list[dict] | None) -> list[str]:
        return suggest_safe_alternatives(conflicts)
