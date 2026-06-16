# 健康画像聚合设计

日期：2026-06-16

## 1. 背景与目标

根据 `docs/liangda-health-iteration-roadmap.md`，系统主线需要从报告理解、健康事实、手环状态和互动记忆中形成统一健康画像，再供餐单、Agent 和后续商城推荐使用。

当前项目已经具备基础能力：

- `health_facts` 表和健康事实抽取链路
- `MemoryService`，支持成员级和家庭级记忆
- `HealthProfileService`，已聚合成员档案、年龄、BMI、过敏、口味和最近 7 天手环
- `MealPlanService` 已通过 `HealthProfileService` 生成单人和家庭餐单

本阶段目标是把现有 `HealthProfileService` 升级为统一健康画像聚合器，让画像稳定输出以下信息：

```text
长期风险
近期状态
饮食原则
禁忌/避免项
偏好
阶段目标
营销反馈
依据来源
```

本阶段只做后端服务层聚合，不新增画像表，不做前端画像管理页。

## 2. 范围

包含：

- `HealthProfileService` 读取 `health_facts`
- `HealthProfileService` 可选读取 `MemoryService`
- 健康事实映射到长期风险、饮食原则和避免项
- 记忆映射到偏好、阶段目标和营销反馈
- 家庭画像合并多个成员画像
- 餐单服务优先消费画像中的记忆字段
- 增加后端单元测试

不包含：

- 不新增 `health_profiles` 持久化表
- 不做画像历史版本
- 不做画像刷新任务
- 不做复杂医学规则引擎
- 不做前端页面
- 不重构整个商城推荐
- 不做逻辑删除
- 不做推荐证据链 UI

## 3. 推荐方案

采用方案 A：

```text
升级现有 HealthProfileService
+ 实时聚合 Member / HealthFact / Device / Memory
+ 输出统一画像 dataclass
```

原因：

- 符合 roadmap 第 5 节对健康画像聚合的定位
- 不新增额外存储和同步机制
- 改动集中，能直接服务餐单和 Agent
- 后续商城推荐可以逐步迁移到同一画像入口

不采用新增画像表的方案。当前事实、手环和记忆都会变化，第一版持久化画像会引入刷新、失效和一致性问题，超出当前最简流程。

不采用餐单、商城、Agent 各自读取多源数据的方案。规则分散后会导致健康安全优先级不一致，例如餐单低钠但商城推荐重盐调味品。

## 4. 数据优先级

健康画像聚合必须遵守 roadmap 中的推荐决策优先级：

```text
过敏/禁忌
> 报告健康事实
> 个人健康标签
> 手环近期状态
> 当前问题
> 记忆偏好
> 营销转化
```

记忆不能覆盖健康安全约束。

示例：

```text
报告事实：爸爸血压偏高
记忆：爸爸喜欢咸口
```

画像可以保留“喜欢咸口”作为偏好，但饮食原则仍必须是低钠，避免项仍必须包含重盐调味、腌制品和咸菜。

## 5. 画像结构

### 5.1 单人画像

扩展 `backend/app/services/health_profile_service.py` 中的 `HealthProfile`。

建议结构：

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

字段说明：

- `long_term_risks`：来自健康标签和报告健康事实，例如高血压、血脂偏高、骨密度低
- `recent_states`：来自最近 7 天手环，例如睡眠不足、步数偏低、血压近期偏高
- `diet_principles`：用于餐单和推荐的正向饮食原则
- `avoid_tags`：过敏、禁忌和健康风险对应的避免项
- `preferences`：来自档案口味和 memory preference
- `goals`：来自 memory goal
- `marketing_feedback`：来自 memory marketing_feedback
- `today_modifiers`：保留现有短期修正文案，兼容餐单输出
- `source_notes`：数据来源摘要，例如健康档案、报告健康事实、最近 7 天手环、互动记忆
- `evidence_notes`：报告事实依据摘要，第一版用短文本，不做证据链 UI

### 5.2 家庭画像

扩展 `FamilyHealthProfile`。

建议结构：

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

家庭画像不做复杂冲突合并。第一版采用最简单规则：

- 风险、原则、避免项直接去重合并
- 任一成员过敏或禁忌会进入家庭共同避免项
- 成员差异通过 `member_adjustments` 输出
- 家庭级记忆单独进入 `family_preferences`、`family_goals` 和 `family_marketing_feedback`

## 6. 健康事实映射规则

第一版只实现常见规则，避免做复杂医学规则引擎。

| 健康事实或标签关键词 | 长期风险 | 饮食原则 | 避免项 |
| --- | --- | --- | --- |
| 高血压、血压偏高、血压高 | 血压偏高 | 低钠、清淡、足量蔬菜 | 腌制品、咸菜、浓汤、重盐调味 |
| 糖尿病、血糖偏高、控糖、血糖高 | 血糖风险 | 控糖、低GI、主食定量 | 甜饮、甜点、精制主食过量 |
| 高血脂、血脂偏高、总胆固醇偏高、甘油三酯偏高 | 血脂偏高 | 少油、优质蛋白、高纤维 | 油炸、肥肉、动物油 |
| 骨质疏松、骨密度低 | 骨密度风险 | 高钙、优质蛋白、维生素D | 长期低蛋白、过量浓茶咖啡 |
| 痛风、尿酸偏高 | 尿酸风险 | 低嘌呤、足量饮水 | 动物内脏、浓肉汤、酒 |
| 胃肠 | 胃肠敏感 | 规律、温和、少刺激 | 辛辣、生冷、过油 |

健康事实只读取 `status` 为 `warning` 或 `danger` 的记录。`normal` 记录第一版只进入依据，不主动生成风险和限制。

每条参与聚合的健康事实写入 `evidence_notes`：

```text
报告事实：总胆固醇偏高，来源 doc_2026_checkup 第 3 页
```

## 7. 记忆聚合规则

`HealthProfileService` 构造函数新增可选参数：

```python
def __init__(self, db: Session, memory_service: MemoryService | None = None):
    ...
```

单人画像读取：

```text
query = "{name} {relation} 饮食 偏好 排斥 阶段目标 购买反馈"
member_id = profile.member_id
```

家庭画像读取：

```text
query = "全家 饮食 偏好 排斥 阶段目标 购买反馈"
member_id = None
```

第一版解析记忆采用最简单关键词规则：

- `memory_type == "preference"` 或文本包含“喜欢 / 偏好” → `preferences`
- `memory_type == "avoidance"` 或文本包含“不喜欢 / 不吃 / 排斥” → `preferences` 中保留原文，同时不写入健康 `avoid_tags`
- `memory_type == "goal"` 或文本包含“想 / 目标 / 最近要” → `goals`
- `memory_type == "marketing_feedback"` 或文本包含“贵 / 便宜 / 跳过 / 购买 / 不买” → `marketing_feedback`

注意：memory avoidance 表达的是用户主观排斥，不等同于健康禁忌。它可以影响餐单替换，但不能进入健康安全 `avoid_tags` 覆盖报告和过敏。

## 8. 餐单服务接入

`MealPlanService` 当前已经单独检索 memory 文本并处理“不喜欢鱼”。本阶段改为优先使用画像字段：

```text
HealthProfile.preferences
HealthProfile.goals
FamilyHealthProfile.family_preferences
FamilyHealthProfile.family_goals
```

保留现有“不喜欢鱼”替换规则，但输入从 `memory_text` 迁移为画像偏好列表。

第一版只做一个明确 demo：

```text
如果 preferences 中包含“不喜欢鱼 / 不喜欢吃鱼 / 不吃鱼”
则餐单中的清蒸鱼替换为鸡胸肉/豆腐
并输出个性化记忆说明
```

## 9. 商城推荐接入边界

本阶段不重构商城推荐。

但后续商城推荐应从当前直接读取 `Member.health_tags` 逐步迁移为读取健康画像：

```text
HealthProfile.diet_principles
HealthProfile.avoid_tags
HealthProfile.preferences
HealthProfile.marketing_feedback
```

这样可以保证餐单和商品推荐使用同一套健康安全优先级。

## 10. 测试计划

新增或扩展 `backend/tests/test_health_profile_service.py`。

覆盖用例：

1. 报告事实“总胆固醇偏高”生成 `long_term_risks`、`少油` 和 `高纤维`
2. 报告事实“血压偏高”与记忆“喜欢咸口”同时存在时，画像仍保留 `低钠` 和 `重盐调味` 避免项
3. 成员记忆“爸爸不喜欢鱼”进入 `preferences`，但不进入健康 `avoid_tags`
4. 家庭画像合并多个成员的健康事实和避免项
5. 没有健康事实和记忆时，现有健康标签、BMI、年龄、手环逻辑保持兼容

扩展 `backend/tests/test_meal_plan_service.py`。

覆盖用例：

1. 餐单使用画像偏好避开鱼
2. 健康安全规则优先于偏好，低钠原则仍出现在餐单原因和避免项中

## 11. 后续计划

本阶段完成后，下一步再做：

- `health_profile_tool` 暴露给 Agent 工具编排
- 商城推荐接入健康画像
- 推荐依据展示中引用 `evidence_notes`
- 商品推荐结合 `marketing_feedback`

这些内容不进入本阶段实现，避免扩大范围。
