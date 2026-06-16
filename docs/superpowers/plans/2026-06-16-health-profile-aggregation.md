# 健康画像聚合实施计划

> **给执行 Agent 的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐任务执行。步骤使用 checkbox（`- [ ]`）跟踪。

**目标：** 按照 `docs/superpowers/specs/2026-06-16-health-profile-aggregation-design.md`，把 `HealthProfileService` 升级为统一健康画像聚合器。

**架构：** 画像仍在 `HealthProfileService` 中实时聚合，不新增 `health_profiles` 表。服务读取 `Member`、`HealthFact`、最近 7 天 `DeviceDailyMetric` 和可选 `MemoryService`，输出扩展后的 dataclass，第一阶段先供 `MealPlanService` 使用。

**技术栈：** FastAPI 后端、SQLAlchemy ORM、pytest、现有 dataclass 服务层。

---

## 文件结构

- 修改：`backend/app/services/health_profile_service.py`
  - 扩展 `HealthProfile` 和 `FamilyHealthProfile`
  - 通过 `SqlAlchemyHealthFactRepository` 读取健康事实
  - 支持注入 `MemoryService` 读取记忆
  - 把事实和标签映射为风险、饮食原则、避免项和依据说明

- 修改：`backend/app/services/meal_plan_service.py`
  - 构造 `HealthProfileService(db, memory_service=memory_service)`
  - 消费 `profile.preferences` 和 `profile.goals`
  - 保留现有“不喜欢鱼”替换 demo

- 修改：`backend/tests/test_health_profile_service.py`
  - 增加健康事实和记忆聚合测试

- 修改：`backend/tests/test_meal_plan_service.py`
  - 调整 fake memory 预期，验证餐单使用画像偏好字段

---

### 任务 1：补充健康画像聚合测试

**文件：**
- 修改：`backend/tests/test_health_profile_service.py`

- [x] **步骤 1：增加 import 和 fake memory service**

在文件顶部增加：

```python
from app.models.health_fact import HealthFact
```

在 `_add_metric` 后增加 helper：

```python
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
```

增加 fake memory service：

```python
class FakeMemoryService:
    def __init__(self, items=None):
        self.items = items or []
        self.calls = []

    def search(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return self.items
```

- [x] **步骤 2：增加总胆固醇健康事实映射测试**

追加测试：

```python
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
```

- [x] **步骤 3：增加健康事实优先于咸口记忆的测试**

追加测试：

```python
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
```

- [x] **步骤 4：增加主观排斥记忆不进入健康避免项的测试**

追加测试：

```python
def test_health_profile_memory_avoidance_stays_out_of_health_avoid_tags(db_session):
    from app.services.memory_service import MemoryItem

    _add_member(db_session, member_id="mem_dad", name="李建国", relation="爸爸", gender="男", health_tags=["高血压"])
    memory = FakeMemoryService([MemoryItem(content="爸爸不喜欢鱼", memory_type="avoidance", member_id="mem_dad")])

    profile = HealthProfileService(db_session, memory_service=memory).get_member_profile("mem_dad")

    assert memory.calls == [("李建国 爸爸 饮食 偏好 排斥 阶段目标 购买反馈", "mem_dad", 5)]
    assert "爸爸不喜欢鱼" in profile.preferences
    assert "爸爸不喜欢鱼" not in profile.avoid_tags
    assert "互动记忆" in profile.source_notes
```

- [x] **步骤 5：增加家庭画像合并测试**

追加测试：

```python
def test_family_profile_merges_health_facts_and_family_memory(db_session):
    from app.services.memory_service import MemoryItem

    _add_member(db_session, member_id="mem_mom", name="张桂兰", relation="妈妈", health_tags=[])
    _add_member(db_session, member_id="mem_dad", name="李建国", relation="爸爸", gender="男", health_tags=[])
    _add_fact(db_session, member_id="mem_mom", fact_id="fact_bp", name="血压偏高")
    _add_fact(db_session, member_id="mem_dad", fact_id="fact_sugar", name="血糖偏高")
    memory = FakeMemoryService([MemoryItem(content="全家周末在家做饭", memory_type="preference")])

    profile = HealthProfileService(db_session, memory_service=memory).get_family_profile()

    assert "血压偏高" in profile.shared_risks
    assert "血糖风险" in profile.shared_risks
    assert "低钠" in profile.shared_principles
    assert "控糖" in profile.shared_principles
    assert "重盐调味" in profile.shared_avoid_tags
    assert "甜饮" in profile.shared_avoid_tags
    assert "全家周末在家做饭" in profile.family_preferences
```

- [x] **步骤 6：运行测试并确认先失败**

运行：

```bash
pytest backend/tests/test_health_profile_service.py -q
```

预期：失败。原因是新的 dataclass 字段和构造函数行为还没有实现。

---

### 任务 2：实现统一健康画像聚合

**文件：**
- 修改：`backend/app/services/health_profile_service.py`

- [x] **步骤 1：增加 repository 和 memory import**

增加：

```python
from app.models.health_fact import HealthFact
from app.repositories.health_fact_repository import SqlAlchemyHealthFactRepository
from app.services.memory_service import MemoryItem, MemoryService
```

- [x] **步骤 2：扩展 dataclass**

替换 `HealthProfile`：

```python
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
```

替换 `FamilyHealthProfile`：

```python
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
```

- [x] **步骤 3：更新构造函数**

替换构造函数：

```python
def __init__(self, db: Session, memory_service: MemoryService | None = None):
    self.db = db
    self.member_repository = SqlAlchemyMemberRepository(db)
    self.device_repository = SqlAlchemyDeviceRepository(db)
    self.fact_repository = SqlAlchemyHealthFactRepository(db)
    self.device_service = DeviceService(db)
    self.memory_service = memory_service
```

- [x] **步骤 4：更新家庭画像聚合**

替换 `get_family_profile`：

```python
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
```

- [x] **步骤 5：更新单人画像构建流程**

在 `_build_member_profile` 的 `avoid_tags` 后增加：

```python
long_term_risks: list[str] = []
recent_states: list[str] = []
evidence_notes: list[str] = []
```

替换健康规则调用：

```python
self._apply_health_rules(health_tags, principles, avoid_tags, long_term_risks)
facts = self.fact_repository.list_by_member(member.member_id)
self._apply_fact_rules(facts, principles, avoid_tags, long_term_risks, evidence_notes)
```

替换记忆和来源说明逻辑：

```python
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
```

返回新的 dataclass：

```python
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
```

- [x] **步骤 6：更新健康标签规则签名**

替换 `_apply_health_rules` 签名和函数体：

```python
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
```

- [x] **步骤 7：增加健康事实和记忆 helper**

在 `_member_adjustment` 前增加：

```python
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
    items = self.memory_service.search(query, member_id=member_id, limit=5)
    for item in items:
        target = _memory_group(item)
        if target:
            groups[target].append(item.content)
    return {key: _unique(value) for key, value in groups.items()}
```

在 `_unique` 附近增加模块级 helper：

```python
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
```

- [x] **步骤 8：运行画像测试**

运行：

```bash
pytest backend/tests/test_health_profile_service.py -q
```

预期：通过。

---

### 任务 3：让餐单服务消费画像偏好

**文件：**
- 修改：`backend/app/services/meal_plan_service.py`
- 修改：`backend/tests/test_meal_plan_service.py`

- [x] **步骤 1：更新 service 构造函数**

替换构造函数：

```python
def __init__(self, db: Session, memory_service=None):
    self.profile_service = HealthProfileService(db, memory_service=memory_service)
```

- [x] **步骤 2：移除单人餐单中的独立 memory search**

替换 `build_member_plan`：

```python
def build_member_plan(self, member_id: str, goal: str | None = None, meal_type: str = "day") -> str:
    profile = self.profile_service.get_member_profile(member_id)
    meals = _apply_preferences_to_meals(_member_meals(profile), profile.preferences)
    return _format_member_plan(profile, meals, goal, meal_type)
```

- [x] **步骤 3：移除家庭餐单中的独立 memory search**

替换 `build_family_plan`：

```python
def build_family_plan(self, goal: str | None = None, meal_type: str = "day") -> str:
    profile = self.profile_service.get_family_profile()
    meals = _apply_preferences_to_meals(_family_meals(profile), profile.family_preferences)
    return _format_family_plan(profile, meals, goal, meal_type)
```

删除 `_memory_text_for_member` 和 `_memory_text_for_family`。

- [x] **步骤 4：更新格式化函数**

修改 `_format_member_plan` 签名：

```python
def _format_member_plan(
    profile: HealthProfile,
    meals: dict[str, str],
    goal: str | None,
    meal_type: str,
) -> str:
```

把：

```python
if _should_avoid_fish(memory_text):
```

替换为：

```python
if _should_avoid_fish(profile.preferences):
```

修改 `_format_family_plan` 签名：

```python
def _format_family_plan(
    profile: FamilyHealthProfile,
    meals: dict[str, str],
    goal: str | None,
    meal_type: str,
) -> str:
```

把：

```python
if _should_avoid_fish(memory_text):
```

替换为：

```python
if _should_avoid_fish(profile.family_preferences):
```

- [x] **步骤 5：替换 memory helper**

把 `_apply_memory_to_meals` 和 `_should_avoid_fish` 替换为：

```python
def _apply_preferences_to_meals(meals: dict[str, str], preferences: list[str]) -> dict[str, str]:
    if not _should_avoid_fish(preferences):
        return meals
    return {
        key: value.replace("清蒸鱼/鸡胸肉", "鸡胸肉/豆腐")
        .replace("清蒸鱼", "鸡胸肉/豆腐")
        .replace("鱼", "鸡胸肉/豆腐")
        for key, value in meals.items()
    }


def _should_avoid_fish(preferences: list[str]) -> bool:
    text = "\n".join(preferences)
    return "不喜欢鱼" in text or "不喜欢吃鱼" in text or "不吃鱼" in text
```

- [x] **步骤 6：更新餐单测试里的 fake memory**

在 `backend/tests/test_meal_plan_service.py` 中，把 `FakeMemoryService` 替换为：

```python
class FakeMemoryService:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def search(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return self.items
```

在使用记忆的测试中增加：

```python
from app.services.memory_service import MemoryItem
```

把：

```python
memory = FakeMemoryService("[avoidance] 爸爸不喜欢鱼")
```

替换为：

```python
memory = FakeMemoryService([MemoryItem(content="爸爸不喜欢鱼", memory_type="avoidance", member_id="mem_dad")])
```

把：

```python
assert memory.calls == [("李建国 爸爸 饮食 偏好 排斥", "mem_dad", 5)]
```

替换为：

```python
assert memory.calls == [("李建国 爸爸 饮食 偏好 排斥 阶段目标 购买反馈", "mem_dad", 5)]
```

把：

```python
memory = FakeMemoryService("[preference] 爸爸喜欢咸口")
```

替换为：

```python
memory = FakeMemoryService([MemoryItem(content="爸爸喜欢咸口", memory_type="preference", member_id="mem_dad")])
```

- [x] **步骤 7：运行餐单测试**

运行：

```bash
pytest backend/tests/test_meal_plan_service.py -q
```

预期：通过。

---

### 任务 4：聚焦验证

**文件：**
- 除非测试暴露回归，否则不修改源码。

- [x] **步骤 1：运行聚焦后端测试**

运行：

```bash
pytest backend/tests/test_health_profile_service.py backend/tests/test_meal_plan_service.py backend/tests/test_memory_service.py backend/tests/test_agent_tools.py -q
```

预期：通过。

- [x] **步骤 2：运行推荐相关回归测试**

运行：

```bash
pytest backend/tests/test_api_health_analysis.py backend/tests/test_api_mall.py backend/tests/test_agent_service.py -q
```

预期：通过。若被无关外部服务配置阻塞，记录具体失败测试和错误信息后停止。

- [x] **步骤 3：审查 diff**

运行：

```bash
git diff -- backend/app/services/health_profile_service.py backend/app/services/meal_plan_service.py backend/tests/test_health_profile_service.py backend/tests/test_meal_plan_service.py
```

预期：diff 只包含健康画像聚合和餐单消费画像偏好的相关变化。

---

## 自检

规格覆盖：

- 任务 2 通过 `SqlAlchemyHealthFactRepository` 读取健康事实
- 任务 2 支持向 `HealthProfileService` 注入可选 `MemoryService`
- 任务 1 和任务 3 覆盖健康安全优先于记忆偏好
- 不包含画像持久化表、前端页面或商城重构

占位检查：

- 没有占位标记或含糊的实现说明。

类型一致性：

- `HealthProfile.preferences` 和 `FamilyHealthProfile.family_preferences` 先定义，再由 `MealPlanService` 使用
- `MemoryService.search()` 返回 `MemoryItem`，与 `_memory_group(item: MemoryItem)` 匹配
- 保留现有 `today_modifiers`、`shared_principles` 和 `member_adjustments` 名称，降低兼容风险
