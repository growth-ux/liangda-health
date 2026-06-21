# Recommendation Engineering 技术架构

日期：2026-06-21

## 1. 架构目标

Recommendation Engineering Layer 负责把粮达健康中的健康画像、餐单场景、长期记忆、商品标签和营销反馈转化为可解释、可约束、可转化的商品推荐结果。

它不是普通电商推荐，也不是 Agent 自由生成几个商品名，而是一个“健康安全优先”的个性化推荐决策层。

核心目标：

```text
根据用户问题识别推荐场景
根据成员或家庭范围读取健康画像
根据健康事实和禁忌过滤不安全商品
根据餐单、商品标签和健康目标生成候选
根据偏好、预算和营销反馈进行排序
生成可追溯的推荐证据链
输出结构化商品卡片
把用户反馈写入 Loop Engineering
```

比赛展示时，Recommendation Engineering 可以作为智能营销主线：

```text
粮达健康不是在健康问答后硬塞商品，而是在健康画像、安全规则、记忆偏好和营销反馈共同约束下完成商品推荐和转化。
```

## 2. 总体分层

```text
Recommendation Engineering Layer
    ├─ Recommendation Input Layer
    │   ├─ User Intent
    │   ├─ Target Member / Family Scope
    │   ├─ Meal Plan Context
    │   ├─ Health Profile Context
    │   ├─ Memory Context
    │   └─ Product Query Context
    ├─ Candidate Generation Layer
    │   ├─ Category Match
    │   ├─ Health Goal Match
    │   ├─ Product Tag Match
    │   ├─ Semantic Retrieval
    │   └─ Candidate Pool
    ├─ Safety Filtering Layer
    │   ├─ Allergy Filter
    │   ├─ Chronic Disease Constraint
    │   ├─ Forbidden Tag Filter
    │   ├─ Conflict Detection
    │   └─ Safe Alternative
    ├─ Ranking Layer
    │   ├─ Health Match Score
    │   ├─ Preference Match Score
    │   ├─ Budget Fit Score
    │   ├─ Conversion Score
    │   ├─ Diversity Control
    │   └─ Final Ranking
    ├─ Evidence Layer
    │   ├─ Health Fact Evidence
    │   ├─ Memory Evidence
    │   ├─ Product Tag Evidence
    │   ├─ Meal Plan Evidence
    │   └─ Recommendation Reason
    └─ Output & Feedback Layer
        ├─ Product Card
        ├─ Structured Recommendation Payload
        ├─ Add to Cart
        ├─ Skip / Like / Purchase Feedback
        └─ Loop Write-back
```

边界：

```text
Recommendation Input Layer 负责收集推荐输入。
Candidate Generation Layer 负责生成候选商品池。
Safety Filtering Layer 负责过滤不安全或冲突商品。
Ranking Layer 负责给候选商品排序。
Evidence Layer 负责生成推荐依据。
Output & Feedback Layer 负责输出商品卡片并接入反馈闭环。
```

推荐决策优先级：

```text
安全禁忌
> 健康事实
> 健康目标
> 当前餐单场景
> 商品标签匹配
> 用户偏好
> 预算反馈
> 营销转化
```

## 3. 架构关系

```text
User Request / Meal Plan
    ↓
Recommendation Input
    ├─ Intent
    ├─ Member / Family Scope
    ├─ Health Profile
    ├─ Memory
    ├─ Product Query
    └─ Meal Plan Context
    ↓
Candidate Generation
    ↓
Safety Filtering
    ↓
Ranking
    ↓
Evidence Generation
    ↓
Structured Product Cards
    ↓
User Feedback
    ↓
Loop Write-back
```

和 Agent 的边界：

```text
Agent 负责识别意图、调用 mall_recommend 工具和解释结果。
Recommendation Engineering 负责决定推荐哪些商品、为什么推荐、如何排序。
Agent 不应绕过推荐引擎自由编造商品。
```

和安全规则的边界：

```text
个性化偏好只能影响安全候选内的排序。
营销转化只能影响安全候选内的排序。
任何推荐都不能突破过敏、禁忌、慢病和报告事实约束。
```

## 4. Recommendation Input Layer

### 4.1 User Intent

定位：识别用户当前是否需要商品推荐，以及属于哪类推荐。

推荐意图：

| 意图 | 示例 | 推荐入口 |
| --- | --- | --- |
| 餐单带商品 | “爸爸今晚吃什么，顺便推荐可以买的” | `meal_plan` 后接 `mall_recommend` |
| 商品类目直推 | “推荐一款适合全家的油” | 直接 `mall_recommend` |
| 健康目标推荐 | “妈妈控糖适合买什么？” | 画像 + 商品标签推荐 |
| 报告依据转推荐 | “爸爸血脂高，买点什么合适？” | 健康事实 + 商品推荐 |
| 替代推荐 | “这个太贵了，换一个” | 反馈 + 重排 |

### 4.2 Target Member / Family Scope

定位：确定推荐对象是单个成员还是全家。

规则：

```text
明确说爸爸、妈妈、孩子 → member scope
明确说全家、我们家、家里人 → family scope
商品类目问题没有成员时，可以默认 family scope
有健康风险的问题必须明确成员或家庭范围
跨成员推荐需要保留成员差异
```

输出示例：

```json
{
  "scope": "member",
  "target_member": "爸爸",
  "member_id": "mem_dad"
}
```

### 4.3 Meal Plan Context

定位：餐单场景下，商品推荐应服务当前餐单。

输入示例：

```text
晚餐建议：低钠、少油、主食减量。
蛋白质选择：豆腐、鸡胸肉、鸡蛋。
避免：高盐调味、油炸食品、大份主食。
```

推荐作用：

```text
从餐单中抽取食材方向
根据饮食原则匹配商品标签
把商品推荐变成可执行购买建议
避免推荐和餐单无关的商品
```

### 4.4 Health Profile Context

定位：提供推荐的健康约束和健康目标。

输入字段：

```text
长期风险
报告健康事实
近期设备状态
饮食原则
禁忌和过敏
阶段性健康目标
```

示例：

```json
{
  "member": "爸爸",
  "health_facts": ["血脂偏高", "BMI 偏高"],
  "diet_principles": ["少油", "低钠", "主食减量"],
  "avoid_tags": ["high_sodium", "high_fat"],
  "goal_tags": ["low_sodium", "high_fiber", "low_fat"]
}
```

### 4.5 Memory Context

定位：提供个性化偏好和营销反馈。

记忆类型：

```text
preference：喜欢、偏好
avoidance：不喜欢、排斥
goal：阶段目标
marketing_feedback：价格、类目、购买意愿
```

示例：

```json
{
  "preferences": ["喜欢咸口"],
  "avoidance": ["不喜欢鱼"],
  "marketing_feedback": ["预算敏感", "经常购买杂粮主食"]
}
```

边界：

```text
记忆只影响候选商品排序和表达方式。
记忆不能覆盖安全过滤和健康事实。
```

### 4.6 Product Query Context

定位：处理用户明确提出的商品类目或商品属性。

示例：

```text
油
米
调料
坚果
低糖早餐
适合控脂的主食
适合全家的牛奶
```

作用：

```text
限定候选商品类目
避免泛化推荐
提升商品推荐和用户问题的一致性
```

## 5. Candidate Generation Layer

### 5.1 Category Match

定位：根据用户问题或餐单场景匹配商品类目。

示例：

| 输入 | 候选类目 |
| --- | --- |
| “推荐一款油” | 食用油 |
| “低钠调味” | 调味品 |
| “控糖早餐” | 早餐、低糖主食、无糖饮品 |
| “晚餐少油” | 杂粮主食、豆制品、低钠调味 |

### 5.2 Health Goal Match

定位：根据健康目标召回相关商品。

目标和标签：

```text
控糖 → low_sugar / low_gi / no_added_sugar
控脂 → low_fat / high_fiber / whole_grain
低钠 → low_sodium / healthy_seasoning
补钙 → high_calcium / dairy / soy
体重管理 → low_calorie / high_protein / high_fiber
```

### 5.3 Product Tag Match

定位：基于商品标签匹配健康画像和餐单需求。

标签类型：

```text
健康标签：low_sodium、low_sugar、high_fiber、low_fat
风险标签：high_sodium、high_sugar、high_fat
类目标签：oil、rice、seasoning、milk、snack
人群标签：elderly、child、family、weight_control
场景标签：breakfast、dinner、meal_replacement
```

### 5.4 Semantic Retrieval

定位：在规则和标签召回之外，使用语义匹配补充候选商品。

流程：

```text
Health Profile Text
    ↓
Profile Embedding
    ↓
Product Embedding Search
    ↓
Semantic Candidate Pool
```

注意：

```text
语义召回只能补充候选，不能绕过安全过滤。
语义相似度高不代表一定适合健康约束。
```

### 5.5 Candidate Pool

定位：合并不同召回来源，形成待过滤商品池。

候选来源：

```text
类目召回
健康标签召回
餐单食材召回
语义召回
历史正反馈召回
热门健康商品召回
```

输出示例：

```json
{
  "candidate_products": [
    {
      "product_id": "p_low_sodium_soy_sauce",
      "name": "低钠酱油",
      "category": "seasoning",
      "tags": ["low_sodium", "healthy_seasoning"]
    }
  ]
}
```

## 6. Safety Filtering Layer

### 6.1 Allergy Filter

定位：过滤过敏或明确禁忌商品。

规则：

```text
成员过敏标签命中商品成分 → 过滤
家庭级过敏未知时不做家庭推荐扩散
过敏禁忌优先级高于所有偏好和营销目标
```

### 6.2 Chronic Disease Constraint

定位：根据慢病风险和报告异常过滤不适合商品。

示例：

```text
血压偏高 → 过滤 high_sodium
血脂偏高 → 过滤 high_fat
控糖目标 → 过滤 high_sugar
肾功能风险 → 谨慎高蛋白推荐
骨密度偏低 → 可优先 high_calcium
```

### 6.3 Forbidden Tag Filter

定位：基于 `avoid_tags` 和商品风险标签过滤候选。

输入：

```json
{
  "avoid_tags": ["high_sodium", "high_fat"],
  "candidate_tags": ["seasoning", "high_sodium"]
}
```

结果：

```text
商品包含 high_sodium，过滤。
```

### 6.4 Conflict Detection

定位：识别偏好和健康安全之间的冲突。

冲突示例：

```text
喜欢咸口 + 血压偏高
想吃甜食 + 控糖目标
喜欢油炸 + 血脂偏高
不喜欢鱼 + 需要优质蛋白
```

处理原则：

```text
允许记录偏好
不允许直接按冲突偏好推荐高风险商品
需要生成安全替代方向
```

### 6.5 Safe Alternative

定位：把冲突偏好转成安全替代商品。

示例：

| 冲突 | 替代 |
| --- | --- |
| 喜欢咸口 + 血压偏高 | 低钠酱油、香辛料、醋汁 |
| 想吃甜食 + 控糖 | 无糖酸奶、低糖水果、坚果 |
| 喜欢油炸 + 血脂偏高 | 空气炸半成品、少油烹饪食材 |
| 不喜欢鱼 + 需要蛋白 | 鸡胸肉、豆腐、鸡蛋、无糖豆浆 |

## 7. Ranking Layer

### 7.1 Health Match Score

定位：计算商品和健康画像的匹配程度。

加分项：

```text
匹配健康目标标签
匹配餐单饮食原则
适合当前成员风险
能作为安全替代方案
```

扣分项：

```text
和健康目标弱相关
类目不符合当前问题
需要复杂解释才成立
```

### 7.2 Preference Match Score

定位：根据用户偏好和排斥调整排序。

示例：

```text
爸爸不喜欢鱼 → 降低鱼类商品
妈妈偏好低糖早餐 → 提高低糖早餐商品
全家常买杂粮主食 → 提高杂粮类商品
```

### 7.3 Budget Fit Score

定位：根据价格敏感度调整排序。

示例：

```text
预算敏感 → 中低价商品加权
用户愿意买高品质 → 放宽价格约束
连续跳过高价商品 → 降低高价商品
```

### 7.4 Conversion Score

定位：结合营销反馈和行为信号估算转化可能性。

信号：

```text
点击
收藏
加入购物车
购买意愿
重复购买
跳过原因
```

边界：

```text
Conversion Score 只能在安全候选内参与排序。
不能为了转化推荐健康风险商品。
```

### 7.5 Diversity Control

定位：避免推荐结果过于单一。

策略：

```text
同类商品不要全部占满
餐单场景下覆盖主食、蛋白、调味或饮品
家庭推荐保留不同成员差异
相似商品只保留排序最高的少数项
```

### 7.6 Final Ranking

定位：合并各类得分生成最终排序。

示例权重：

```text
final_score =
  health_match_score * 0.40
+ preference_match_score * 0.20
+ budget_fit_score * 0.15
+ category_fit_score * 0.15
+ conversion_score * 0.10
```

注意：

```text
权重只作用于已通过 Safety Filtering 的商品。
被过滤商品不能通过高转化分重新进入结果。
```

## 8. Evidence Layer

### 8.1 Health Fact Evidence

定位：说明推荐和健康事实的关系。

示例：

```json
{
  "type": "health_fact",
  "text": "爸爸体检报告提示血脂偏高",
  "source": "2026 体检报告 p3"
}
```

### 8.2 Memory Evidence

定位：说明推荐如何考虑用户偏好和历史反馈。

示例：

```json
{
  "type": "memory",
  "text": "爸爸不喜欢鱼，优先选择豆腐和鸡胸肉替代"
}
```

### 8.3 Product Tag Evidence

定位：说明商品为什么匹配。

示例：

```json
{
  "type": "product_tag",
  "text": "商品标签包含低钠、高纤维"
}
```

### 8.4 Meal Plan Evidence

定位：说明商品如何服务当前餐单。

示例：

```json
{
  "type": "meal_plan",
  "text": "晚餐建议少油、低钠、主食减量"
}
```

### 8.5 Recommendation Reason

定位：生成用户能理解的推荐理由。

推荐理由结构：

```text
推荐给谁
解决什么健康目标
结合了什么偏好或反馈
商品标签为什么匹配
如果有冲突，如何做了安全替代
```

示例：

```text
推荐给爸爸。考虑到爸爸血脂偏高，晚餐建议少油、主食适量；这款杂粮饭高纤维、饱腹感更强，也比精米饭更适合控脂晚餐。
```

## 9. Output & Feedback Layer

### 9.1 Product Card

定位：向前端输出可渲染商品卡片。

字段建议：

```json
{
  "product_id": "p_multigrain_rice",
  "name": "杂粮饭",
  "category": "staple",
  "price": 19.9,
  "tags": ["high_fiber", "whole_grain"],
  "reason": "适合控脂晚餐，主食更有饱腹感",
  "evidence_source": "健康画像 + 商品标签"
}
```

### 9.2 Structured Recommendation Payload

定位：让 Agent 回复和前端卡片解耦。

输出：

```text
Agent summary_text：只做简短说明，不重复商品细节。
Product cards：由结构化 payload 渲染。
Evidence panel：展示推荐依据。
```

### 9.3 Add to Cart

定位：把推荐转成营销动作。

行为：

```text
加入购物车
收藏
立即购买
换一批
不感兴趣
太贵了
```

### 9.4 Skip / Like / Purchase Feedback

定位：把用户行为回流给 Loop Engineering。

反馈映射：

| 行为 | 信号 |
| --- | --- |
| 加入购物车 | purchase_intent |
| 收藏 | positive_feedback |
| 点击 | weak_positive_feedback |
| 跳过 | weak_negative_feedback |
| 太贵了 | price_sensitive |
| 不感兴趣 | avoidance 或 category_negative |

### 9.5 Loop Write-back

定位：将商品推荐反馈写入长期记忆或营销反馈。

示例：

```text
用户连续跳过高价商品 → 写入 price_sensitive
用户收藏杂粮饭 → 提高 grain_staple 类目偏好
用户明确不要甜的 → 写入 avoidance 或控糖偏好
```

## 10. 和现有系统的关系

Recommendation Engineering 复用现有 Agent、画像、记忆、商城和证据链能力。

对应关系：

| 现有模块 | Recommendation Engineering 作用 |
| --- | --- |
| `MallRecommendTool` | 推荐引擎入口，接收 scope、member_id、meal_plan_text、query_text |
| `mall_recommendation` | 候选生成、规则匹配和排序 |
| `meal_product_recommendation_service` | 从餐单转商品推荐 |
| `HealthProfileService` | 提供健康画像、饮食原则和 avoid_tags |
| `MemorySearchTool` | 提供偏好、排斥、目标和营销反馈 |
| `mall_catalog` | 提供商品目录和健康标签 |
| `AgentEvidenceCollector` | 收集商品推荐证据 |
| `Loop Engineering` | 接收推荐反馈并影响下一轮排序 |
| `Harness Engineering` | 检查推荐是否安全、准确、可解释 |

和 Context Engineering 的关系：

```text
Context Engineering 负责把成员、画像、记忆、商品和安全上下文组织好。
Recommendation Engineering 负责用这些上下文完成候选、过滤、排序和解释。
```

和 Loop Engineering 的关系：

```text
Recommendation Engineering 输出推荐和商品卡片。
Loop Engineering 接收点击、跳过、收藏、加购和购买反馈，并反向影响后续推荐。
```

和 Harness Engineering 的关系：

```text
Harness Engineering 验证推荐是否调用正确、是否命中健康依据、是否过滤禁忌商品、是否符合输出结构。
```

## 11. 推荐迭代路径

### P1：推荐边界明确

目标：

```text
区分餐单带商品、商品类目直推、健康目标推荐
明确 Agent 只调用 mall_recommend，不自由编造商品
商品推荐输出结构化 payload
```

验收示例：

```text
“推荐一款适合全家的油”直接走商品推荐，不先生成餐单。
“爸爸今晚吃什么”先生成餐单，再追加商品推荐。
```

### P2：安全过滤

目标：

```text
根据健康画像生成 avoid_tags
过滤高钠、高糖、高脂等风险商品
实现偏好和健康事实冲突时的安全替代
```

验收示例：

```text
爸爸血压偏高时，不推荐 high_sodium 商品。
爸爸喜欢咸口时，推荐低钠调味替代。
```

### P3：健康标签匹配和排序

目标：

```text
基于商品健康标签和成员画像计算 health_match_score
基于用户偏好和预算反馈调整排序
控制推荐结果多样性
```

验收示例：

```text
血脂偏高场景优先低脂、高纤、杂粮类商品。
预算敏感后降低高价商品排序。
```

### P4：推荐证据链

目标：

```text
推荐结果绑定健康事实、餐单依据、记忆依据和商品标签
前端展示推荐理由和来源
```

验收示例：

```text
商品卡片说明推荐给谁、为什么适合、来源于哪些画像和商品标签。
```

### P5：语义推荐增强

目标：

```text
引入 profile embedding 和 product embedding
语义召回补充商品候选
在安全过滤后参与排序
```

验收示例：

```text
用户描述“适合控脂晚餐的主食”，能召回杂粮饭、燕麦、全谷物类商品。
```

### P6：推荐 Harness

目标：

```text
检查推荐是否符合目标成员
检查 forbidden_product_tags 是否被过滤
检查 expected_product_tags 是否命中
检查推荐理由是否可追溯
```

## 12. 画架构图建议

### 12.1 推荐总体架构图

推荐节点：

```text
User Request / Meal Plan
Recommendation Input Layer
Candidate Generation Layer
Safety Filtering Layer
Ranking Layer
Evidence Layer
Product Cards
User Feedback
Loop Write-back
```

推荐连线：

```text
User Request / Meal Plan → Recommendation Input Layer
Recommendation Input Layer → Candidate Generation Layer
Candidate Generation Layer → Safety Filtering Layer
Safety Filtering Layer → Ranking Layer
Ranking Layer → Evidence Layer
Evidence Layer → Product Cards
Product Cards → User Feedback
User Feedback → Loop Write-back
Loop Write-back → Recommendation Input Layer
```

### 12.2 安全过滤图

推荐节点：

```text
Candidate Pool
Health Profile
Avoid Tags
Allergy Filter
Chronic Disease Constraint
Forbidden Tag Filter
Conflict Detection
Safe Alternative
Safe Candidate Pool
```

推荐连线：

```text
Candidate Pool → Allergy Filter
Health Profile → Avoid Tags
Avoid Tags → Forbidden Tag Filter
Allergy Filter → Chronic Disease Constraint
Chronic Disease Constraint → Forbidden Tag Filter
Forbidden Tag Filter → Conflict Detection
Conflict Detection → Safe Alternative
Safe Alternative → Safe Candidate Pool
```

### 12.3 推荐证据链图

推荐节点：

```text
Target Member
Health Fact Evidence
Meal Plan Evidence
Memory Evidence
Product Tag Evidence
Recommendation Reason
Product Card
```

推荐连线：

```text
Target Member → Recommendation Reason
Health Fact Evidence → Recommendation Reason
Meal Plan Evidence → Recommendation Reason
Memory Evidence → Recommendation Reason
Product Tag Evidence → Recommendation Reason
Recommendation Reason → Product Card
```

## 13. 示例 Demo 用例

### 13.1 爸爸晚餐商品推荐

```json
{
  "case_id": "rec_dad_dinner_001",
  "input": "爸爸今晚吃什么，顺便推荐可以买的",
  "context": {
    "health_facts": ["血脂偏高", "BMI 偏高"],
    "memory": ["爸爸不喜欢鱼", "预算敏感"],
    "meal_goal": ["低钠", "少油", "主食适量"]
  },
  "expected_behavior": [
    "先生成餐单",
    "再推荐商品",
    "过滤高钠和高脂商品",
    "推荐低钠、高纤、低脂方向商品"
  ],
  "expected_product_tags": ["low_sodium", "high_fiber", "low_fat"],
  "forbidden_product_tags": ["high_sodium", "high_fat"]
}
```

### 13.2 全家食用油推荐

```json
{
  "case_id": "rec_family_oil_001",
  "input": "推荐一款适合全家人的油",
  "target_scope": "family",
  "expected_behavior": [
    "直接进入商品推荐",
    "不先调用 meal_plan",
    "候选类目限定为食用油",
    "结合家庭健康画像做安全过滤"
  ],
  "forbidden_tools": ["meal_plan"],
  "expected_product_category": "oil"
}
```

### 13.3 价格反馈后的重排

```json
{
  "case_id": "rec_budget_rerank_001",
  "step_1_input": "这个太贵了，换一个",
  "expected_loop_signal": {
    "type": "marketing_feedback",
    "target": "price",
    "value": "budget_sensitive"
  },
  "step_2_input": "再推荐一款适合爸爸的杂粮主食",
  "expected_behavior": [
    "降低高价商品排序",
    "优先推荐中低价位杂粮主食"
  ]
}
```

### 13.4 偏好冲突安全替代

```json
{
  "case_id": "rec_salty_conflict_001",
  "input": "爸爸喜欢咸口，推荐点下饭的",
  "context": {
    "health_facts": ["血压偏高"],
    "memory": ["喜欢咸口"]
  },
  "expected_behavior": [
    "不能推荐高盐商品",
    "推荐低钠调味替代",
    "推荐理由说明保留口味但降低盐摄入"
  ],
  "forbidden_product_tags": ["high_sodium"],
  "expected_product_tags": ["low_sodium", "healthy_seasoning"]
}
```
