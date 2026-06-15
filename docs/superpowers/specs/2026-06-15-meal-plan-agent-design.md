# 一日三餐推荐 Agent 设计

日期：2026-06-15

## 1. 背景与目标

当前 Agent 主链路更像“健康报告问答”：系统提示词、工具和页面默认问题都围绕报告检索与报告解读。下一阶段需要把 Agent 的主要能力改成“根据家人健康状态推荐一日三餐”。

第一阶段目标：

- 支持用户按单个家人提问，例如“妈妈今天怎么吃”“爸爸控糖早餐吃什么”
- 支持用户按全家提问，例如“给全家安排今天一日三餐”“今晚做什么适合全家”
- 推荐内容覆盖早餐、午餐、晚餐，可按问题只输出某一餐
- 推荐依据优先使用家人健康档案、过敏忌口、年龄、BMI 和最近 7 天手环数据
- 报告检索保留，但只在用户明确要求“根据报告/体检结果”时参与

本阶段不包含：

- 商品推荐
- 下单、购物车、商城跳转
- 精确克重、热量和营养素计算
- 周食谱、月食谱
- 真实医疗诊断
- 复杂知识图谱或新图数据库
- 从 PDF 报告中结构化抽取体检指标

目标是先形成可运行闭环：用户在现有聊天页提问，Agent 能根据单人或全家的健康状态给出可执行的一日三餐建议。

## 2. 约束

- 使用现有技术栈：
  - 后端：FastAPI + SQLAlchemy + LangChain
  - 前端：React + Vite + React Query
- 不引入新框架和重型依赖
- 前端首版可以不改页面结构，只复用现有聊天页
- 不把商品推荐提前混进餐单
- 推荐逻辑优先规则化，LLM 主要负责识别用户意图和组织自然语言
- 当用户提到具体家人时必须显式识别 `member_id`
- 当用户问“全家/我们家”时按全家模式处理

## 3. 核心原则

一日三餐推荐不是“报告 vs 手环”二选一，而是分层使用数据：

```text
健康档案/报告 = 长期饮食原则
手环数据 = 今日状态微调
```

数据优先级：

```text
过敏/忌口 > 明确疾病/健康标签/报告异常 > 手环最近状态 > 口味偏好
```

具体规则：

- 过敏和忌口最高优先级，推荐餐单必须避开
- 高血压、糖尿病、高血脂、骨质疏松、痛风等长期健康状态决定基础饮食原则
- 最近 7 天手环数据只做短期微调，不覆盖长期健康原则
- 数据冲突时保守处理，例如报告未标高血压但手环连续血压偏高，则按低钠建议处理，并提示建议复测
- 数据缺失时直接说明依据不足，不编造报告或手环结论

## 4. 阶段划分

### 4.1 第一阶段：一日三餐推荐

本阶段实现：

- 健康画像聚合
- 单人餐单生成
- 全家餐单生成
- Agent `meal_plan` 工具
- Agent 系统提示词从报告问答改为三餐推荐
- 三餐相关快捷问题

不实现商品推荐。

### 4.2 第二阶段：餐单接商品

第二阶段再把餐单中的食材方向映射到商城商品。

预留方向：

- 餐单项提取食材标签，例如燕麦、牛奶、杂粮、低钠调味
- 复用现有 `mall_recommendation.py` 商品打分规则
- 在 Agent 回复中追加“可选购买”建议

第二阶段不影响第一阶段的餐单主链路。

## 5. 后端设计

### 5.1 新增 `HealthProfileService`

新增文件：

- `backend/app/services/health_profile_service.py`

职责：

- 聚合单人健康画像
- 聚合全家健康画像
- 统一处理长期健康状态和最近手环状态
- 给 `MealPlanService` 提供稳定输入

单人画像建议结构：

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
    diet_principles: list[str]
    avoid_tags: list[str]
    today_modifiers: list[str]
    source_notes: list[str]
```

全家画像建议结构：

```python
@dataclass(frozen=True)
class FamilyHealthProfile:
    scope: str
    members: list[HealthProfile]
    shared_principles: list[str]
    shared_avoid_tags: list[str]
    family_modifiers: list[str]
    member_adjustments: list[str]
    source_notes: list[str]
```

首版数据来源：

- `Member.health_tags`
- `Member.allergies`
- `Member.taste_preferences`
- `Member.birth_year`
- `Member.height_cm`
- `Member.weight_kg`
- `DeviceDailyMetric` 最近 7 天

报告数据首版不在 `HealthProfileService` 默认读取。用户明确要求“根据报告”时，仍由 Agent 调用现有 `kb_search` 工具获取报告片段。

### 5.2 健康标签到饮食原则

首版规则：

| 健康状态 | 饮食原则 | 避免项 |
| --- | --- | --- |
| 高血压、血压偏高 | 低钠、清淡、足量蔬菜 | 腌制品、咸菜、浓汤、重盐调味 |
| 糖尿病、血糖偏高、控糖 | 控糖、低 GI、主食定量 | 甜饮、甜点、精制主食过量 |
| 高血脂 | 少油、优质蛋白、高纤维 | 油炸、肥肉、动物油 |
| 骨质疏松、骨密度低 | 高钙、优质蛋白、维生素 D | 长期低蛋白、过量浓茶咖啡 |
| 超重、BMI 偏高 | 控制总热量、高蛋白、高纤维 | 夜宵、油炸、高糖饮料 |
| 痛风、尿酸偏高 | 低嘌呤、足量饮水 | 动物内脏、浓肉汤、酒 |
| 胃肠问题 | 规律、温和、少刺激 | 辛辣、生冷、过油 |

BMI 规则：

- `BMI >= 24`：增加“控制总热量、高纤维、晚餐减轻”
- `BMI < 18.5`：增加“保证能量和蛋白质”，但不覆盖控糖、低钠等原则

年龄规则：

- `age >= 60`：关注高钙、优质蛋白、易消化
- `age < 18`：关注生长发育、优质蛋白、高钙

### 5.3 手环数据微调

使用最近 7 天 `DeviceDailyMetric` 计算均值和最新值。

首版规则：

| 手环状态 | 触发条件 | 今日微调 |
| --- | --- | --- |
| 睡眠不足 | 近 7 天平均睡眠 `< 6.5h` | 晚餐清淡，避免浓茶咖啡和过晚进食 |
| 步数偏低 | 近 7 天平均步数 `< 5000` | 晚餐主食稍减，减少油炸和高糖 |
| 血压偏高 | 近 7 天平均收缩压 `>= 130` 或舒张压 `>= 85` | 低钠策略更严格 |
| 心率偏高 | 近 7 天平均心率 `>= 90` | 避免刺激性饮品，提醒关注状态 |
| 血氧偏低 | 最新血氧 `< 95` | 不给饮食诊断，提示关注或复测 |

手环数据只改变餐单轻重和提醒，不改变长期禁忌。

### 5.4 新增 `MealPlanService`

新增文件：

- `backend/app/services/meal_plan_service.py`

职责：

- 根据 `HealthProfile` 生成单人餐单
- 根据 `FamilyHealthProfile` 生成全家餐单
- 返回结构化文本，供 Agent 工具直接使用

工具输出不要求 JSON，首版可以返回稳定的 Markdown 文本，便于 LLM 继续组织回答。

单人输出格式：

```text
家人：张桂兰（妈妈）
健康关注：高血压、骨密度低
饮食原则：低钠、高钙、优质蛋白
今日修正：最近睡眠偏少，晚餐建议清淡

早餐：
- 燕麦牛奶 + 水煮蛋 + 一小份低糖水果
原因：兼顾高钙、蛋白质和稳定能量，不增加过多盐分。

午餐：
- 杂粮饭 + 清蒸鱼/鸡胸肉 + 西兰花 + 豆腐汤
原因：主食更稳，蛋白质充足，整体低盐少油。

晚餐：
- 小米粥/杂粮粥 + 豆腐青菜 + 少量瘦肉
原因：晚餐减轻负担，适合睡眠不足时保持清淡。

避免：
- 咸菜、腊肉、浓汤、重盐调味、过量浓茶咖啡
```

全家输出格式：

```text
全家共餐原则：低钠、控糖、少油、高纤维
共同避免：甜饮、咸菜、油炸、浓汤
今日修正：家中有人最近步数偏低，晚餐建议减轻

早餐：
- 无糖豆浆/牛奶 + 鸡蛋 + 燕麦/全麦主食 + 一小份水果

午餐：
- 杂粮饭 + 清蒸鱼/鸡胸肉 + 两份蔬菜 + 清淡豆腐汤

晚餐：
- 杂粮粥 + 豆制品/瘦肉 + 深色蔬菜

成员调整：
- 爸爸控糖：主食减量，水果放到两餐之间。
- 妈妈高血压：不额外加咸菜和重盐调味。
- 女儿成长发育：可增加牛奶、鸡蛋或豆制品。
```

### 5.5 全家模式规则

全家模式不为每个人生成完全独立的三餐，而是生成一份共餐基础方案，再输出成员调整。

共同餐单按最严格限制处理：

- 有高血压成员：全家基础餐默认低钠
- 有糖尿病成员：默认控糖、低 GI，不安排甜饮甜点
- 有高血脂或 BMI 偏高成员：默认少油炸、少肥肉
- 有过敏成员：基础餐避开过敏源
- 有老人或儿童：增加高钙、优质蛋白，但不和控糖、低钠冲突

## 6. Agent 集成

### 6.1 新增工具

修改文件：

- `backend/app/services/agent_tools.py`
- `backend/app/services/langchain_agent.py`
- `backend/app/api/agent.py`

新增工具：

```python
def meal_plan(
    scope: str,
    member_id: str | None = None,
    goal: str | None = None,
    meal_type: str = "day",
) -> str:
    """根据单人或全家健康状态生成一日三餐或指定餐次建议。"""
```

参数规则：

- `scope="member"` 时必须传 `member_id`
- `scope="family"` 时不传 `member_id`
- `meal_type` 支持 `day`、`breakfast`、`lunch`、`dinner`
- `goal` 可选，例如“控糖”“低钠”“减脂”“高钙”“清淡晚餐”

### 6.2 系统提示词调整

`SYSTEM_PROMPT_TEMPLATE` 从报告解读改为三餐推荐。

核心要求：

1. 你是粮达健康的一日三餐膳食推荐 Agent。
2. 首要任务是根据家人健康状态、过敏忌口、年龄、BMI 和最近手环状态，给出早餐、午餐、晚餐建议。
3. 用户问具体家人时，识别该家人的 `member_id` 并调用 `meal_plan(scope="member")`。
4. 用户问全家、我们家、今晚做什么适合全家时，调用 `meal_plan(scope="family")`。
5. 用户要求基于报告、体检结果、某份报告时，才调用 `kb_search`。
6. 推荐餐单时必须调用 `meal_plan`，不要只凭模型自由生成。
7. 不做诊断，不替代医生。
8. 信息不足时直接说明缺什么信息，例如没有家人、指代不明、没有身高体重。
9. 回答要具体、可执行，避免泛泛而谈。

保留当前家人列表注入逻辑，用于模型识别“爸爸/妈妈/女儿”等指代。

### 6.3 快捷问题

修改：

- `GET /api/agent/quick-actions`

返回：

```json
[
  { "label": "给全家安排今天一日三餐", "action": "meal_plan_family_day" },
  { "label": "妈妈高血压今天怎么吃", "action": "meal_plan_hypertension" },
  { "label": "爸爸控糖早餐吃什么", "action": "meal_plan_diabetes_breakfast" },
  { "label": "今晚做什么适合全家", "action": "meal_plan_family_dinner" }
]
```

前端现有 `ChatInput` 已支持快捷问题展示。本阶段不要求改页面标题和布局。

实现时需要在 `ChatPage` 给 `ChatInput` 传入 `onQuickAction`。首版点击快捷问题后直接把 `action.label` 填入输入框，不自动发送，避免用户误触后立即调用模型。

## 7. API 与前端范围

本阶段不新增独立餐单 API。餐单能力通过 Agent 工具暴露。

前端首版不改页面结构：

- 继续使用 `/chat`
- 继续使用现有 SSE 流式输出
- 继续使用现有会话、消息、快捷问题组件
- 点击快捷问题时填入输入框
- 不新增餐单卡片 UI

如后续需要更强展示，再新增结构化餐单 API 和专用餐单卡片。

## 8. 测试计划

后端测试：

- `HealthProfileService` 能把高血压成员转换为低钠原则和高盐避免项
- `HealthProfileService` 能把最近 7 天血压偏高转换为今日低钠微调
- `HealthProfileService` 能处理无设备数据的成员，只输出长期原则
- `MealPlanService` 单人模式返回早餐、午餐、晚餐和避免项
- `MealPlanService` 全家模式按最严格限制合并原则，并输出成员调整
- Agent runner 暴露 `meal_plan` 工具
- `/api/agent/quick-actions` 返回三餐相关快捷问题

现有测试需要同步调整：

- 原 Agent prompt 测试中关于“报告 Agent”的断言改为“三餐膳食 Agent”
- Agent API 的 fake runner 测试不依赖真实工具，保持会话和流式逻辑不变

## 9. 验收标准

满足以下条件即认为阶段一完成：

1. 用户问“妈妈今天一日三餐怎么吃”，Agent 调用 `meal_plan(scope="member")` 并返回三餐建议
2. 用户问“给全家安排今天一日三餐”，Agent 调用 `meal_plan(scope="family")` 并返回共餐方案和成员调整
3. 高血压成员的餐单体现低钠和避免腌制/重盐
4. 糖尿病成员的餐单体现控糖、低 GI 和主食定量
5. 最近 7 天手环睡眠不足或步数偏低时，餐单体现今日微调
6. 用户问“根据妈妈报告安排饮食”时，Agent 可以额外调用 `kb_search`
7. 不出现商品推荐、购买入口、下单建议

## 10. 后续扩展

阶段二再考虑：

- 餐单食材标签化
- 食材标签到商城商品的映射
- 推荐商品解释
- 专用餐单卡片 UI
- 报告指标结构化后自动进入健康画像
- 多日食谱
