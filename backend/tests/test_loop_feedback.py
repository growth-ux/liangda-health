"""Loop Engineering: 冲突检测 + 安全替代策略测试。"""
from app.services.agent.loop_feedback import (
    ConflictDetector,
    detect_conflicts,
    suggest_safe_alternatives,
)


class TestDetectConflicts:
    """偏好 vs 健康约束冲突检测。"""

    def test_salty_preference_vs_hypertension(self):
        conflicts = detect_conflicts(
            preferences=["喜欢咸口"],
            avoidance_memories=[],
            avoid_tags=["低钠", "腌制品", "重盐调味"],
            long_term_risks=["血压偏高"],
            health_tags=["高血压"],
        )
        assert len(conflicts) >= 1
        assert conflicts[0]["description"] == "喜欢咸口但血压偏高"
        assert "低钠酱油" in conflicts[0]["safe_alternative"]

    def test_sweet_preference_vs_diabetes(self):
        conflicts = detect_conflicts(
            preferences=["喜欢甜食"],
            avoidance_memories=[],
            avoid_tags=["甜饮", "甜点"],
            long_term_risks=["血糖风险"],
            health_tags=["糖尿病"],
        )
        assert len(conflicts) >= 1
        assert conflicts[0]["description"] == "喜欢甜食但需控糖"
        assert "无糖酸奶" in conflicts[0]["safe_alternative"]

    def test_fried_preference_vs_high_blood_lipid(self):
        conflicts = detect_conflicts(
            preferences=["喜欢吃油炸食品"],
            avoidance_memories=[],
            avoid_tags=["油炸", "肥肉"],
            long_term_risks=["血脂偏高"],
            health_tags=["高血脂"],
        )
        assert len(conflicts) >= 1
        assert "空气炸锅" in conflicts[0]["safe_alternative"]

    def test_no_conflict_when_preferences_match_health(self):
        """偏好和健康约束不冲突时，不产出冲突记录。"""
        conflicts = detect_conflicts(
            preferences=["喜欢清淡饮食"],
            avoidance_memories=[],
            avoid_tags=["低钠"],
            long_term_risks=["血压偏高"],
            health_tags=["高血压"],
        )
        assert conflicts == []

    def test_no_conflict_when_no_health_constraints(self):
        """无健康约束时不产生冲突。"""
        conflicts = detect_conflicts(
            preferences=["喜欢咸口", "喜欢甜食"],
            avoidance_memories=[],
            avoid_tags=[],
            long_term_risks=[],
            health_tags=[],
        )
        assert conflicts == []


class TestAvoidanceConflicts:
    """规避记忆 vs 健康需求冲突检测。"""

    def test_avoid_fish_but_needs_protein(self):
        conflicts = detect_conflicts(
            preferences=[],
            avoidance_memories=["不喜欢鱼"],
            avoid_tags=["优质蛋白", "高蛋白"],
            long_term_risks=[],
            health_tags=[],
        )
        assert len(conflicts) >= 1
        assert conflicts[0]["description"] == "排斥鱼类但需要优质蛋白"
        assert "鸡胸肉" in conflicts[0]["safe_alternative"]
        assert "豆腐" in conflicts[0]["safe_alternative"]

    def test_avoid_milk_but_needs_calcium(self):
        conflicts = detect_conflicts(
            preferences=[],
            avoidance_memories=["不喜欢喝牛奶"],
            avoid_tags=["高钙"],
            long_term_risks=["骨密度风险"],
            health_tags=["骨质疏松"],
        )
        assert len(conflicts) >= 1
        assert conflicts[0]["description"] == "排斥乳制品但需要补钙"

    def test_avoid_fish_no_protein_need(self):
        """排斥鱼但健康画像无需优质蛋白时不冲突。"""
        conflicts = detect_conflicts(
            preferences=[],
            avoidance_memories=["不喜欢鱼"],
            avoid_tags=["低钠"],
            long_term_risks=["血压偏高"],
            health_tags=["高血压"],
        )
        # 不应匹配 AVOIDANCE_CONFLICT_RULES 中的鱼+优质蛋白规则
        fish_conflicts = [c for c in conflicts if "鱼" in c.get("preference", "")]
        assert fish_conflicts == []


class TestSuggestSafeAlternatives:
    """安全替代建议提取。"""

    def test_extracts_unique_alternatives(self):
        conflicts = [
            {"preference": "咸口", "constraint": "血压偏高", "description": "x", "safe_alternative": "用低钠酱油替代"},
            {"preference": "甜食", "constraint": "控糖", "description": "y", "safe_alternative": "用无糖酸奶替代"},
        ]
        alts = suggest_safe_alternatives(conflicts)
        assert alts == ["用低钠酱油替代", "用无糖酸奶替代"]

    def test_dedupes_same_alternative(self):
        conflicts = [
            {"preference": "咸口", "constraint": "a", "description": "x", "safe_alternative": "用低钠酱油替代"},
            {"preference": "重盐", "constraint": "b", "description": "y", "safe_alternative": "用低钠酱油替代"},
        ]
        alts = suggest_safe_alternatives(conflicts)
        assert alts == ["用低钠酱油替代"]

    def test_returns_empty_for_no_conflicts(self):
        assert suggest_safe_alternatives(None) == []
        assert suggest_safe_alternatives([]) == []


class TestConflictDetector:
    """可注入冲突检测器测试。"""

    def test_detect_and_suggest(self):
        detector = ConflictDetector()
        conflicts = detector.detect(
            preferences=["喜欢咸口"],
            avoidance_memories=[],
            avoid_tags=["低钠"],
            long_term_risks=["血压偏高"],
            health_tags=["高血压"],
        )
        assert len(conflicts) >= 1
        alts = detector.suggest(conflicts)
        assert any("低钠" in alt for alt in alts)
