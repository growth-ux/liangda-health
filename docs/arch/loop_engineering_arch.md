# Loop Engineering 技术架构

日期：2026-06-21

## 1. 架构目标

Loop Engineering Layer 负责把粮达健康中的用户反馈、对话表达和行为信号转化为可复用的长期记忆与营销策略信号，并反向影响下一轮健康建议、餐单生成和商品推荐。

它解决的问题不是“记住用户说过什么”这么简单，而是建立一条持续优化闭环：

```text
推荐结果
→ 用户反馈
→ 反馈理解
→ 记忆和营销信号写入
→ 健康画像和推荐策略更新
→ 下一轮个性化推荐
→ Harness 验证闭环是否生效
```

核心目标：

```text
让 Agent 记住成员级和家庭级偏好
让用户反馈影响后续餐单和商品排序
让营销反馈沉淀为可计算信号
让推荐策略随用户行为持续收敛
让偏好和营销目标不突破健康安全边界
让反馈闭环可以被 Harness 测试和回归
```

比赛展示时，Loop Engineering 可以作为系统持续进化能力：

```text
粮达健康不是一次性问答系统，而是能把用户反馈转化为长期记忆和推荐策略的持续优化 Agent。
```

## 2. 总体分层

```text
Loop Engineering Layer
    ├─ Feedback Capture Layer
    │   ├─ Explicit Feedback
    │   ├─ Implicit Behavior
    │   ├─ Conversation Signal
    │   ├─ Purchase Signal
    │   └─ Negative Signal
    ├─ Feedback Understanding Layer
    │   ├─ Feedback Classification
    │   ├─ Member Scope Resolution
    │   ├─ Preference Extraction
    │   ├─ Confidence Scoring
    │   ├─ Noise Filtering
    │   └─ Conflict Detection
    ├─ Memory Write-back Layer
    │   ├─ Preference Memory
    │   ├─ Avoidance Memory
    │   ├─ Goal Memory
    │   ├─ Marketing Feedback
    │   └─ Write Guard
    ├─ Strategy Update Layer
    │   ├─ Profile Refresh
    │   ├─ Meal Plan Adjustment
    │   ├─ Product Re-ranking
    │   ├─ Budget Sensitivity Update
    │   ├─ Category Preference Update
    │   └─ Safe Alternative Policy
    └─ Loop Evaluation Layer
        ├─ Feedback Write Check
        ├─ Next-turn Influence Check
        ├─ Safety Override Check
        ├─ Memory Drift Check
        └─ Conversion Quality Check
```

边界：

```text
Feedback Capture Layer 负责捕获用户反馈和行为。
Feedback Understanding Layer 负责把反馈理解成结构化信号。
Memory Write-back Layer 负责写入长期记忆和营销反馈。
Strategy Update Layer 负责让信号影响下一轮推荐。
Loop Evaluation Layer 负责验证闭环是否真的生效。
```

## 3. 架构关系

```text
Agent Response
    ↓
User Feedback / User Behavior
    ↓
Feedback Capture
    ↓
Feedback Understanding
    ├─ Classification
    ├─ Member Scope Resolution
    ├─ Confidence Scoring
    └─ Conflict Detection
    ↓
Memory Write-back
    ├─ preference
    ├─ avoidance
    ├─ goal
    └─ marketing_feedback
    ↓
Strategy Update
    ├─ Health Profile Refresh
    ├─ Meal Plan Adjustment
    └─ Product Re-ranking
    ↓
Next Agent Response
    ↓
Loop Evaluation / Harness
```

Loop Engineering 和其他层的关系：

```text
Context Engineering：负责在下一轮 Agent 调用前读取记忆和反馈信号。
Harness Engineering：负责验证反馈是否写入、是否影响下一轮推荐、是否没有突破安全规则。
Evidence Chain：负责向用户解释推荐中哪些依据来自报告、画像、记忆或反馈。
```

安全优先级：

```text
过敏 / 禁忌
> 报告事实
> 健康标签
> 近期设备状态
> 当前问题
> 长期记忆偏好
> 营销转化目标
```

## 4. Feedback Capture Layer

### 4.1 Explicit Feedback

定位：捕获用户主动表达的偏好、否定、目标和购买反馈。

示例：

```text
爸爸不喜欢鱼
妈妈最近想控糖
这个太贵了，换一个
以后别推荐甜的
这个可以，加入购物车
我想要简单点的晚餐
```

可抽取信号：

| 用户表达 | 信号类型 | 作用 |
| --- | --- | --- |
| “不喜欢鱼” | avoidance | 后续餐单避开鱼类 |
| “想控糖” | goal | 后续推荐低糖、低 GI |
| “太贵了” | marketing_feedback | 降低高价商品排序 |
| “别推荐甜的” | avoidance / marketing_feedback | 降低甜味商品 |
| “加入购物车” | positive_feedback | 提高同类商品权重 |

### 4.2 Implicit Behavior

定位：捕获用户没有明确说出口但能反映意图的行为。

行为类型：

```text
点击商品
收藏商品
加入购物车
跳过商品
停留查看
反复查看同类商品
关闭推荐卡片
```

处理原则：

```text
显式反馈置信度高
隐式行为置信度低
单次隐式行为不直接改写强偏好
多次重复行为可以提升置信度
隐式行为不能覆盖健康安全约束
```

### 4.3 Conversation Signal

定位：从多轮对话中抽取可沉淀的长期信息。

示例：

```text
用户连续追问低糖早餐 → 可能存在控糖目标
用户多次要求便宜一点 → 存在价格敏感
用户多次要求简单做法 → 偏好低烹饪复杂度
用户多次问爸爸晚餐 → 当前家庭主要服务对象是爸爸
```

输出示例：

```json
{
  "signal_type": "marketing_feedback",
  "target": "budget",
  "value": "price_sensitive",
  "scope": "family",
  "confidence": 0.72,
  "source": "conversation"
}
```

### 4.4 Purchase Signal

定位：把加入购物车、购买意愿和成交行为转化为推荐策略信号。

信号类型：

```text
add_to_cart：较强正反馈
purchase_intent：中强正反馈
purchase：强正反馈
repeat_purchase：长期偏好或稳定需求
```

应用：

```text
提高相似商品排序
强化商品类目偏好
识别家庭常购健康品类
为后续营销推荐提供依据
```

### 4.5 Negative Signal

定位：捕获用户拒绝、跳过和负反馈。

示例：

```text
不要这个
太贵了
不想吃鱼
换一个清淡的
别推荐零食
这个不适合爸爸
```

处理原则：

```text
负反馈优先影响当前推荐会话
重复负反馈再沉淀为长期记忆
健康安全相关负反馈优先级高于普通营销反馈
```

## 5. Feedback Understanding Layer

### 5.1 Feedback Classification

定位：把用户反馈分类为可写入和可计算的信号。

分类类型：

```text
preference：喜欢、偏好
avoidance：不喜欢、排斥
goal：阶段目标
marketing_feedback：价格、类目、购买意愿、转化反馈
safety_signal：过敏、禁忌、不适反应
session_only：只对当前对话有效
```

分类示例：

```json
{
  "text": "爸爸不喜欢鱼，预算别太高",
  "signals": [
    {
      "type": "avoidance",
      "target": "fish",
      "scope": "member",
      "member": "爸爸"
    },
    {
      "type": "marketing_feedback",
      "target": "price",
      "value": "budget_sensitive",
      "scope": "member",
      "member": "爸爸"
    }
  ]
}
```

### 5.2 Member Scope Resolution

定位：判断反馈属于某个成员、全家，还是当前会话。

规则：

```text
明确说爸爸、妈妈、孩子 → 成员级
明确说全家、我们家、家里人 → 家庭级
只说“这个太贵了” → 默认绑定当前推荐上下文
只说“我不喜欢” → 默认绑定当前用户或当前会话，必要时追问
无法确定成员且影响较大 → 不直接写长期记忆
```

失败风险：

```text
把爸爸不喜欢鱼写成全家不喜欢鱼。
把用户觉得太贵写成妈妈价格敏感。
把一次性当前餐单反馈写成长期偏好。
```

### 5.3 Preference Extraction

定位：从自然语言中抽取偏好对象、方向和强度。

输出字段：

```text
target：偏好对象，例如鱼、杂粮、低糖、便宜、简单做法
polarity：positive / negative
strength：强 / 中 / 弱
scope：member / family / session
source：explicit / implicit / conversation / purchase
confidence：置信度
```

示例：

```json
{
  "target": "fish",
  "polarity": "negative",
  "strength": "strong",
  "scope": "member",
  "member_id": "mem_dad",
  "source": "explicit",
  "confidence": 0.95
}
```

### 5.4 Confidence Scoring

定位：避免把偶发反馈误写成长期偏好。

置信度参考：

| 来源 | 初始置信度 |
| --- | --- |
| 明确语言表达 | 高 |
| 加入购物车 | 中高 |
| 收藏 | 中 |
| 点击 | 低 |
| 跳过 | 低到中 |
| 多次重复行为 | 累计提升 |

写入策略：

```text
高置信度反馈可以写入长期记忆
中置信度反馈可以写入 marketing_feedback
低置信度反馈优先保留为 session signal
涉及安全和过敏的反馈必须单独确认或进入硬约束流程
```

### 5.5 Noise Filtering

定位：过滤无效、临时或不可靠反馈。

过滤示例：

```text
“随便”不写长期记忆
“今天不想吃鱼”只作为当前会话约束
“这个看起来一般”不直接降低整个类目
“先看看”不作为购买偏好
```

### 5.6 Conflict Detection

定位：识别用户偏好、记忆、健康事实和安全规则之间的冲突。

冲突示例：

```text
爸爸喜欢咸口 + 血压偏高
妈妈想控糖 + 收藏高糖点心
孩子喜欢零食 + 家庭目标是控制体重
用户想买高脂商品 + 报告提示血脂偏高
```

处理策略：

```text
允许记录偏好
不允许按冲突偏好直接推荐高风险商品
优先生成安全替代方案
推荐理由中说明“保留口味，但换成低钠/低糖/低脂版本”
```

## 6. Memory Write-back Layer

### 6.1 Preference Memory

定位：记录正向偏好。

示例：

```json
{
  "type": "preference",
  "scope": "member",
  "member_id": "mem_mom",
  "content": "妈妈偏好低糖早餐",
  "confidence": 0.86,
  "source": "explicit_feedback"
}
```

应用：

```text
餐单口味调整
商品类目排序
推荐文案个性化
后续问答时作为个性化上下文
```

### 6.2 Avoidance Memory

定位：记录排斥、不喜欢和避免项。

示例：

```json
{
  "type": "avoidance",
  "scope": "member",
  "member_id": "mem_dad",
  "content": "爸爸不喜欢鱼",
  "confidence": 0.95,
  "source": "explicit_feedback"
}
```

应用：

```text
餐单避开对应食材
推荐时降低相关商品排序
生成替代方案
```

### 6.3 Goal Memory

定位：记录阶段性健康目标。

示例：

```json
{
  "type": "goal",
  "scope": "member",
  "member_id": "mem_mom",
  "content": "妈妈最近想控糖",
  "confidence": 0.9,
  "source": "conversation"
}
```

应用：

```text
控糖、控脂、补钙、减重等目标影响餐单和商品推荐
目标需要和报告事实、设备状态一起参与画像聚合
```

### 6.4 Marketing Feedback

定位：记录和营销转化相关的行为和偏好。

类型：

```text
price_sensitive：价格敏感
category_preference：类目偏好
brand_preference：品牌偏好
purchase_intent：购买意愿
skip_reason：跳过原因
conversion_signal：转化信号
```

示例：

```json
{
  "type": "marketing_feedback",
  "scope": "family",
  "content": "用户连续跳过高价商品，倾向中低价位",
  "confidence": 0.78,
  "source": "implicit_behavior"
}
```

### 6.5 Write Guard

定位：控制哪些反馈可以写入长期记忆，哪些只能作为当前会话信号。

写入规则：

```text
明确长期偏好可以写入
当前餐次临时约束优先写 session
成员归属不明确时不写成员级长期记忆
低置信度隐式行为不直接写强记忆
健康事实不能被普通反馈覆盖
安全禁忌需要进入更严格的确认流程
```

## 7. Strategy Update Layer

### 7.1 Profile Refresh

定位：把长期记忆和营销反馈纳入健康画像聚合。

输入：

```text
成员档案
健康事实
设备数据
偏好记忆
排斥记忆
阶段目标
营销反馈
```

输出：

```json
{
  "member": "爸爸",
  "health_goals": ["控脂", "晚餐少油"],
  "avoidance": ["鱼"],
  "preference": ["咸口"],
  "marketing": ["价格敏感"],
  "safety": ["避免高盐", "避免高油"]
}
```

### 7.2 Meal Plan Adjustment

定位：让反馈影响下一轮餐单。

示例：

```text
爸爸不喜欢鱼 → 用鸡胸肉、豆腐、鸡蛋替代
妈妈想控糖 → 早餐减少甜粥和高糖点心
用户要求简单做法 → 推荐蒸、煮、拌、少步骤菜品
今晚不想吃主食 → 当前会话减少主食，但不写长期记忆
```

### 7.3 Product Re-ranking

定位：让营销反馈和偏好影响商品排序。

排序信号：

```text
健康匹配
安全过滤
商品标签
成员偏好
排斥记忆
价格敏感
购买意愿
历史点击 / 收藏 / 加购
```

排序优先级：

```text
安全过滤
> 健康匹配
> 商品类目匹配
> 记忆偏好
> 价格和营销反馈
> 转化概率
```

### 7.4 Budget Sensitivity Update

定位：根据用户价格反馈调整推荐区间。

示例：

```text
“太贵了” → 降低同类高价商品排序
连续跳过高价商品 → 写入 price_sensitive
加入购物车中低价商品 → 提高中低价商品权重
用户明确说“质量好贵点也行” → 放宽价格约束
```

### 7.5 Category Preference Update

定位：根据行为判断用户更偏好的健康商品类目。

示例：

```text
经常收藏杂粮主食 → 提高杂粮类推荐
多次跳过零食 → 降低健康零食推荐
多次购买低钠调味品 → 在控盐场景优先推荐调味替代
```

### 7.6 Safe Alternative Policy

定位：当用户偏好和健康安全冲突时，生成安全替代方案。

示例：

```text
喜欢咸口 + 血压偏高 → 低钠酱油、香辛料、醋汁替代
想吃甜食 + 控糖目标 → 无糖酸奶、低糖水果、坚果替代
喜欢油炸 + 血脂偏高 → 空气炸、清蒸、少油煎替代
不喜欢鱼 + 需要优质蛋白 → 鸡胸肉、豆腐、鸡蛋替代
```

## 8. Loop Evaluation Layer

### 8.1 Feedback Write Check

定位：检查反馈是否被正确写入。

检查项：

```text
是否抽取正确反馈类型
是否绑定正确成员或家庭范围
是否写入正确记忆类型
是否带有置信度和来源
是否避免写入低质量噪声
```

### 8.2 Next-turn Influence Check

定位：检查写入后的反馈是否影响下一轮推荐。

示例：

```text
上轮写入“爸爸不喜欢鱼”
下一轮问“爸爸今晚吃什么”
Harness 检查餐单不主推鱼类，并出现合理蛋白替代
```

### 8.3 Safety Override Check

定位：检查反馈没有突破安全约束。

示例：

```text
上轮写入“爸爸喜欢咸口”
爸爸画像包含血压偏高
下一轮推荐不能出现高盐商品，只能出现低钠替代
```

### 8.4 Memory Drift Check

定位：防止长期记忆被噪声污染或逐渐偏离真实需求。

检查项：

```text
低置信度行为是否被错误提升为强偏好
一次性反馈是否被错误写成长期记忆
成员级反馈是否被错误扩散到家庭级
过期目标是否持续影响推荐
```

### 8.5 Conversion Quality Check

定位：检查反馈闭环是否提升推荐转化合理性。

指标：

```text
重复推荐命中偏好
减少用户明确排斥项
降低连续跳过商品比例
提高收藏 / 加购 / 购买意愿
保持安全规则通过率
```

## 9. 和现有系统的关系

Loop Engineering 复用现有记忆、画像、餐单和商品推荐能力。

对应关系：

| 现有模块 | Loop Engineering 作用 |
| --- | --- |
| `memory_service` | 写入和检索 preference、avoidance、goal、marketing_feedback |
| `MemorySearchTool` | Agent 回复前读取相关记忆 |
| `HealthProfileService` | 聚合记忆和健康事实，形成更新后的画像 |
| `MealPlanService` | 根据偏好、排斥和目标调整餐单 |
| `MallRecommendTool` | 根据营销反馈和商品标签重排推荐 |
| `AgentEvidenceCollector` | 记录推荐中使用的记忆和反馈依据 |
| `Harness Engineering` | 验证反馈写入、下一轮影响和安全边界 |

和 Context Engineering 的关系：

```text
Loop Engineering 负责产生和更新长期信号。
Context Engineering 负责在 Agent 调用前选择、压缩和排序这些信号。
```

和 Harness Engineering 的关系：

```text
Loop Engineering 负责形成反馈闭环。
Harness Engineering 负责验证闭环是否正确运转。
```

## 10. 推荐迭代路径

### P1：显式反馈闭环

目标：

```text
支持用户通过自然语言表达偏好、排斥、目标和价格反馈
抽取为 preference / avoidance / goal / marketing_feedback
写入 memory_service
```

优先覆盖：

```text
爸爸不喜欢鱼
妈妈最近想控糖
这个太贵了
以后别推荐甜的
换一个简单点的
```

### P2：下一轮推荐生效

目标：

```text
meal_plan 读取 avoidance 和 goal
mall_recommend 读取 price_sensitive 和 category preference
回复中自然体现“结合你之前反馈”
```

验收示例：

```text
写入“爸爸不喜欢鱼”后，下一次爸爸晚餐不主推鱼类。
写入“太贵了”后，下一次同类商品优先中低价位。
```

### P3：冲突保护

目标：

```text
实现 Conflict Detection 和 Safe Alternative Policy
偏好不能覆盖报告事实、慢病约束和过敏禁忌
```

验收示例：

```text
爸爸喜欢咸口，但血压偏高，系统推荐低钠替代而不是高盐食品。
```

### P4：隐式行为闭环

目标：

```text
捕获点击、收藏、跳过、加购等行为
按置信度转成 marketing_feedback
多次重复行为再影响长期排序
```

验收示例：

```text
用户多次跳过高价商品后，系统降低高价商品排序。
用户多次收藏杂粮类商品后，系统提高杂粮类推荐权重。
```

### P5：Loop Harness

目标：

```text
新增 Loop eval cases
验证反馈是否写入
验证下一轮推荐是否受影响
验证安全规则是否仍然优先
验证记忆没有错误扩散或漂移
```

## 11. 画架构图建议

### 11.1 Loop 总体架构图

推荐节点：

```text
Agent Response
User Feedback / Behavior
Feedback Capture Layer
Feedback Understanding Layer
Memory Write-back Layer
Strategy Update Layer
Next Agent Response
Loop Evaluation Layer
```

推荐连线：

```text
Agent Response → User Feedback / Behavior
User Feedback / Behavior → Feedback Capture Layer
Feedback Capture Layer → Feedback Understanding Layer
Feedback Understanding Layer → Memory Write-back Layer
Memory Write-back Layer → Strategy Update Layer
Strategy Update Layer → Next Agent Response
Next Agent Response → User Feedback / Behavior
Loop Evaluation Layer ↔ Memory Write-back Layer
Loop Evaluation Layer ↔ Strategy Update Layer
```

### 11.2 Feedback Understanding 图

推荐节点：

```text
Raw Feedback
Feedback Classification
Member Scope Resolution
Preference Extraction
Confidence Scoring
Noise Filtering
Conflict Detection
Structured Feedback Signal
```

推荐连线：

```text
Raw Feedback → Feedback Classification
Feedback Classification → Member Scope Resolution
Member Scope Resolution → Preference Extraction
Preference Extraction → Confidence Scoring
Confidence Scoring → Noise Filtering
Noise Filtering → Conflict Detection
Conflict Detection → Structured Feedback Signal
```

### 11.3 安全冲突闭环图

推荐节点：

```text
User Preference
Health Fact
Safety Rule
Conflict Detection
Safe Alternative Policy
Meal Plan Adjustment
Product Re-ranking
Evidence Explanation
```

推荐连线：

```text
User Preference → Conflict Detection
Health Fact → Conflict Detection
Safety Rule → Conflict Detection
Conflict Detection → Safe Alternative Policy
Safe Alternative Policy → Meal Plan Adjustment
Safe Alternative Policy → Product Re-ranking
Meal Plan Adjustment → Evidence Explanation
Product Re-ranking → Evidence Explanation
```

## 12. 示例 Demo 用例

### 12.1 显式偏好写入

```json
{
  "case_id": "loop_dad_avoid_fish_001",
  "step_1_input": "爸爸不喜欢鱼",
  "expected_write": {
    "type": "avoidance",
    "scope": "member",
    "target_member": "爸爸",
    "content": "不喜欢鱼"
  },
  "step_2_input": "爸爸今晚吃什么？",
  "expected_next_turn_effect": [
    "餐单不主推鱼类",
    "推荐鸡胸肉、豆腐或鸡蛋等替代蛋白"
  ]
}
```

### 12.2 价格敏感反馈

```json
{
  "case_id": "loop_budget_sensitive_001",
  "step_1_input": "这个太贵了，换一个",
  "expected_write": {
    "type": "marketing_feedback",
    "target": "price",
    "value": "budget_sensitive"
  },
  "step_2_input": "再推荐一款适合爸爸的杂粮主食",
  "expected_next_turn_effect": [
    "降低高价商品排序",
    "优先推荐中低价位商品"
  ]
}
```

### 12.3 健康安全冲突

```json
{
  "case_id": "loop_dad_salty_conflict_001",
  "precondition": [
    "爸爸血压偏高",
    "爸爸喜欢咸口"
  ],
  "input": "给爸爸推荐点下饭的",
  "expected_behavior": [
    "不能推荐高盐商品",
    "推荐低钠调味替代",
    "解释保留口味但降低盐摄入"
  ],
  "forbidden_product_tags": ["high_sodium"]
}
```

### 12.4 隐式行为闭环

```json
{
  "case_id": "loop_implicit_grain_preference_001",
  "behavior_sequence": [
    "收藏杂粮饭",
    "点击燕麦商品",
    "跳过健康零食"
  ],
  "expected_signal": {
    "type": "marketing_feedback",
    "target": "category_preference",
    "value": "grain_staple",
    "confidence": "medium"
  },
  "expected_next_turn_effect": [
    "提高杂粮主食类商品排序",
    "降低零食类推荐权重"
  ]
}
```
