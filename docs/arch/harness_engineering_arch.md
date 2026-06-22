# Harness Engineering 技术架构

日期：2026-06-21

## 1. 架构目标

Harness Engineering Layer 负责把粮达健康 Agent 的核心能力变成可测试、可回归、可定位问题的工程体系。

它不直接面向普通用户输出内容，而是在模型、prompt、工具、RAG、推荐规则或商品标签调整后，自动验证 Agent 是否仍然满足业务边界和健康安全要求。

核心目标：

```text
验证 Agent 是否正确理解用户意图
验证 Agent 是否调用正确工具
验证 Agent 是否使用正确家庭成员上下文
验证 Agent 是否引用真实报告证据
验证 Agent 是否遵守健康安全约束
验证商品推荐是否和画像、记忆、商品标签一致
验证用户反馈是否能正确沉淀为记忆或营销信号
```

Harness Engineering 可以作为系统工程亮点：

```text
粮达健康不是靠人工试聊调 prompt，而是通过固定评测集、工具调用追踪、证据命中检查和安全规则回归，持续约束和优化 Agent。
```

## 2. 总体分层

```text
Harness Engineering Layer
    ├─ Eval Case Layer
    │   ├─ Scenario Case Set
    │   ├─ Expected Tool Calls
    │   ├─ Expected Contexts
    │   ├─ Required Evidence
    │   ├─ Forbidden Rules
    │   └─ Expected Output Shape
    ├─ Execution Layer
    │   ├─ Test Data Loader
    │   ├─ Agent Runner
    │   ├─ Tool Call Recorder
    │   ├─ Context Snapshot Recorder
    │   ├─ Response Capture
    │   └─ Feedback Simulator
    ├─ Evaluation Layer
    │   ├─ Intent Check
    │   ├─ Member Isolation Check
    │   ├─ Tool Call Check
    │   ├─ Evidence Hit Check
    │   ├─ Safety Rule Check
    │   ├─ Recommendation Quality Check
    │   └─ Response Schema Check
    ├─ Diagnosis Layer
    │   ├─ Failure Classification
    │   ├─ Root Cause Hint
    │   ├─ Regression Diff
    │   └─ Fix Suggestion
    └─ Reporting Layer
        ├─ Case Result Report
        ├─ Regression Summary
        ├─ Quality Metrics
        ├─ Failed Case Replay
        └─ Harness Dashboard
```

边界：

```text
Eval Case Layer 定义测什么。
Execution Layer 负责跑 Agent 并记录过程。
Evaluation Layer 负责判断对错。
Diagnosis Layer 负责解释失败原因。
Reporting Layer 负责输出报告和可视化结果。
```

## 3. 架构关系

```text
Eval Case Set
    ↓
Test Data Loader
    ↓
Agent Runner
    ├─ Tool Call Recorder
    ├─ Context Snapshot Recorder
    ├─ Response Capture
    └─ Feedback Simulator
    ↓
Evaluation Layer
    ├─ Intent Check
    ├─ Member Isolation Check
    ├─ Tool Call Check
    ├─ Evidence Hit Check
    ├─ Safety Rule Check
    ├─ Recommendation Quality Check
    └─ Response Schema Check
    ↓
Diagnosis Layer
    ↓
Regression Report / Dashboard
```

Harness 和线上 Agent 的关系：

```text
线上 Agent：服务真实用户，要求低延迟和稳定输出。
Harness：服务研发和展示，要求可追踪、可复现、可定位。
```

Harness 运行时机：

```text
修改系统 prompt 后
修改 Agent 工具边界后
修改 RAG 检索策略后
修改健康事实抽取逻辑后
修改商品推荐规则后
新增商品标签后
切换大模型后
演示前做全量回归
```

## 4. Eval Case Layer

### 4.1 Scenario Case Set

定位：沉淀固定业务场景，覆盖粮达健康的核心 Agent 能力。

用例类型：

| 类型 | 示例问题 | 评测重点 |
| --- | --- | --- |
| 报告问答 | “爸爸报告里血脂怎么样？” | 是否调用报告检索、是否引用正确证据 |
| 成员识别 | “妈妈适合吃什么？” | 是否解析正确成员 |
| 跨成员隔离 | “爸爸和妈妈报告有什么不同？” | 是否分别查两个人的报告 |
| 餐单生成 | “爸爸今晚吃什么？” | 是否调用餐单工具 |
| 商品推荐 | “推荐一款适合全家的油” | 是否直接调用商品推荐 |
| 证据追问 | “为什么推荐这个？” | 是否展示健康事实和商品标签依据 |
| 偏好记忆 | “爸爸是不是不喜欢鱼？” | 是否调用记忆检索 |
| 禁忌冲突 | “爸爸喜欢咸口，推荐点下饭的” | 是否避免高盐商品 |
| 反馈闭环 | “这个太贵了，换一个” | 是否写入营销反馈 |

### 4.2 Case Schema

定位：用结构化字段描述每个测试用例。

示例：

```json
{
  "case_id": "dad_dinner_product_001",
  "title": "爸爸晚餐和商品推荐",
  "input": "爸爸今晚吃什么，顺便推荐可以买的",
  "history": [
    {
      "role": "user",
      "content": "爸爸不喜欢鱼，预算别太高"
    }
  ],
  "target_scope": "member",
  "target_member": "爸爸",
  "expected_intent": "meal_plan_with_product_recommendation",
  "expected_tools": ["meal_plan", "mall_recommend", "respond"],
  "forbidden_tools": ["kb_search"],
  "required_contexts": ["member", "health_fact", "memory", "product", "safety"],
  "required_evidence": ["血脂偏高"],
  "forbidden_product_tags": ["high_sodium", "high_fat"],
  "expected_product_tags": ["low_sodium", "high_fiber"],
  "must_not_show": ["member_id", "诊断性结论"],
  "expected_response_kind": "meal_plan"
}
```

字段说明：

| 字段 | 作用 |
| --- | --- |
| `case_id` | 唯一用例 ID |
| `input` | 当前用户问题 |
| `history` | 多轮上下文 |
| `target_scope` | member 或 family |
| `target_member` | 期望识别出的家庭成员 |
| `expected_intent` | 期望意图 |
| `expected_tools` | 必须调用的工具 |
| `forbidden_tools` | 不应调用的工具 |
| `required_contexts` | 必须使用的上下文类型 |
| `required_evidence` | 必须命中的证据 |
| `forbidden_product_tags` | 禁止推荐的商品标签 |
| `expected_product_tags` | 期望推荐方向 |
| `must_not_show` | 用户可见文本中禁止出现的内容 |
| `expected_response_kind` | 结构化回复类型 |

### 4.3 Case Categories

定位：按能力域组织测试集，方便按模块回归。

推荐目录：

```text
harness/cases/
    ├─ intent_routing.jsonl
    ├─ member_isolation.jsonl
    ├─ report_evidence.jsonl
    ├─ meal_plan.jsonl
    ├─ product_recommendation.jsonl
    ├─ memory_feedback.jsonl
    ├─ safety_rules.jsonl
    └─ response_schema.jsonl
```

## 5. Execution Layer

### 5.1 Test Data Loader

定位：为每个测试用例准备稳定数据。

加载对象：

```text
家庭成员
健康报告
报告 chunk
健康事实
设备数据
长期记忆
商品目录
商品标签
历史对话
```

要求：

```text
测试数据可复现
成员 ID 固定
报告证据固定
商品标签固定
记忆内容固定
不依赖线上真实用户数据
```

### 5.2 Agent Runner

定位：用固定输入执行当前版本 Agent。

输入：

```text
case input
history messages
test member data
test health facts
test memories
test product catalog
current prompt / model / tool config
```

输出：

```text
final response
tool call trace
context snapshot
evidence list
product recommendations
token usage
latency
error stack
```

### 5.3 Tool Call Recorder

定位：记录 Agent 实际调用了哪些工具，以及调用顺序和参数。

记录示例：

```json
[
  {
    "step": 1,
    "tool": "meal_plan",
    "args": {
      "scope": "member",
      "member_id": "mem_dad",
      "meal_type": "dinner"
    }
  },
  {
    "step": 2,
    "tool": "mall_recommend",
    "args": {
      "scope": "member",
      "member_id": "mem_dad",
      "limit": 5
    }
  },
  {
    "step": 3,
    "tool": "respond",
    "args": {
      "kind": "meal_plan"
    }
  }
]
```

### 5.4 Context Snapshot Recorder

定位：记录 Agent 本轮使用了哪些上下文。

输出示例：

```json
{
  "case_id": "dad_dinner_product_001",
  "scope": "member",
  "target_member": "爸爸",
  "contexts": {
    "member": ["爸爸"],
    "health_fact": ["血脂偏高", "BMI 偏高"],
    "device": ["最近 7 天步数偏低"],
    "memory": ["不喜欢鱼", "预算别太高"],
    "product": ["低钠", "高纤", "低脂"],
    "safety": ["避免高盐", "避免高油"]
  }
}
```

### 5.5 Feedback Simulator

定位：模拟用户反馈，验证记忆写入和推荐重排。

反馈示例：

```text
这个太贵了，换一个
爸爸不喜欢鱼
妈妈最近想控糖
这个可以，加入购物车
不要推荐甜的
```

验证目标：

```text
是否抽取正确反馈类型
是否写入正确成员或家庭范围
是否影响下一轮推荐
是否没有覆盖健康事实和安全约束
```

## 6. Evaluation Layer

### 6.1 Intent Check

定位：检查 Agent 是否把问题路由到正确任务。

规则示例：

```text
“吃什么 / 早餐 / 午餐 / 晚餐 / 一日三餐” → meal_plan
“推荐一款油 / 米 / 调料 / 坚果” → product_recommendation
“报告里 / 体检 / 指标 / 页码” → report_qa
“为什么推荐 / 依据是什么” → evidence_explanation
“他是不是不喜欢 / 记得吗” → memory_query
```

失败示例：

```text
用户问“推荐一款适合全家的油”，Agent 先调用 meal_plan。
```

### 6.2 Member Isolation Check

定位：检查家庭成员上下文是否被错误串用。

检查项：

```text
用户指定爸爸时，工具参数是否使用爸爸的 member_id
用户指定妈妈时，是否没有召回爸爸报告
用户问全家时，是否进入 family scope
跨成员对比时，是否分别检索每位成员
记忆是否写入正确成员范围
```

失败示例：

```text
用户问爸爸血脂，系统引用了妈妈报告。
用户说爸爸不喜欢鱼，系统写成家庭级偏好。
```

### 6.3 Tool Call Check

定位：检查工具调用是否符合业务链路。

规则示例：

```text
餐单问题必须调用 meal_plan
餐单后如需要商品推荐，必须调用 mall_recommend
报告依据问题必须调用 kb_search
偏好记忆问题必须调用 memory_search
最终必须调用 respond
商品类目问题不能误先调用 meal_plan
```

输出示例：

```json
{
  "passed": false,
  "reason": "expected tool mall_recommend was not called",
  "actual_tools": ["meal_plan", "respond"],
  "expected_tools": ["meal_plan", "mall_recommend", "respond"]
}
```

### 6.4 Evidence Hit Check

定位：检查健康判断和报告解释是否有真实依据。

检查项：

```text
是否命中 required_evidence
是否引用目标成员报告
是否引用正确页码或 chunk
是否把记忆当成报告事实
是否凭空声称“报告显示”
```

输出示例：

```json
{
  "passed": true,
  "required_evidence": ["血脂偏高"],
  "hit_evidence": [
    {
      "type": "health_fact",
      "source": "2026 体检报告 p3",
      "text": "总胆固醇高于参考范围"
    }
  ]
}
```

### 6.5 Safety Rule Check

定位：检查回复和推荐是否突破健康安全约束。

规则优先级：

```text
过敏 / 禁忌
> 报告事实
> 健康标签
> 近期设备状态
> 当前问题
> 长期记忆偏好
> 营销转化目标
```

规则示例：

```text
血压偏高 → 禁止推荐高钠商品
血脂偏高 → 避免高油、高脂商品
控糖目标 → 避免高糖零食
骨密度偏低 → 可优先推荐高钙食品
不喜欢鱼 → 餐单不应主推鱼类
过敏食物 → 必须过滤相关商品
```

失败示例：

```text
爸爸喜欢咸口，但血压偏高，系统推荐咸菜、腌制品或高盐调味。
```

### 6.6 Recommendation Quality Check

定位：检查商品推荐是否同时满足健康匹配、个性化和营销合理性。

指标：

| 指标 | 含义 |
| --- | --- |
| Health Match | 商品标签是否匹配健康画像 |
| Preference Match | 是否考虑用户偏好和排斥 |
| Safety Pass | 是否通过禁忌和慢病约束 |
| Evidence Completeness | 推荐理由是否可追溯 |
| Category Fit | 商品类目是否符合用户问题 |
| Budget Fit | 是否考虑价格敏感反馈 |

输出示例：

```json
{
  "score": 0.86,
  "passed": true,
  "matched_tags": ["low_sodium", "high_fiber"],
  "missing": ["budget_fit"]
}
```

### 6.7 Response Schema Check

定位：检查 Agent 输出是否符合前端结构化渲染要求。

检查项：

```text
是否调用 respond
respond.kind 是否符合预期
payload 是否包含必需字段
summary_text 是否过长
用户可见文本是否泄漏内部 ID
商品卡片是否通过结构化字段返回
```

## 7. Diagnosis Layer

### 7.1 Failure Classification

定位：把失败用例分类，方便定位问题归属。

失败类型：

```text
intent_error：意图识别错误
member_error：成员识别或隔离错误
tool_error：工具调用错误
retrieval_error：报告证据召回错误
evidence_error：证据引用错误
safety_error：健康安全冲突
recommendation_error：商品推荐不合理
schema_error：结构化输出不合规
memory_error：记忆检索或写入错误
```

### 7.2 Root Cause Hint

定位：根据失败类型给出可能原因。

示例：

| 失败类型 | 可能原因 | 修复方向 |
| --- | --- | --- |
| `intent_error` | prompt 路由规则不清 | 收紧意图规则，增加 few-shot |
| `member_error` | 成员解析缺少历史指代 | 增加 reference carry-over |
| `tool_error` | 工具边界描述不清 | 拆分工具职责或增强系统 prompt |
| `retrieval_error` | query 表达和报告指标不匹配 | 增加 query rewrite / keyword search |
| `safety_error` | 商品标签缺少禁忌映射 | 补充安全规则和黑名单标签 |
| `schema_error` | 模型未调用 respond | 强化 respond 强制规则 |

### 7.3 Regression Diff

定位：比较当前版本和上一个稳定版本的结果变化。

对比项：

```text
通过率变化
失败用例新增数量
工具调用顺序变化
证据命中变化
商品推荐变化
安全规则变化
输出结构变化
```

输出示例：

```text
本次回归：48 / 52 通过
上次回归：50 / 52 通过

新增失败：
- product_oil_family_002：商品类目问题误调用 meal_plan
- dad_salty_food_001：推荐结果包含 high_sodium 标签

修复成功：
- memory_dad_fish_001：已正确调用 memory_search
```

## 8. Reporting Layer

### 8.1 Case Result Report

定位：记录每个用例的完整结果。

内容：

```text
case_id
输入问题
期望结果
实际工具调用
实际上下文
实际证据
实际推荐商品
最终回复
检查项结果
失败原因
修复建议
```

### 8.2 Regression Summary

定位：输出一次回归测试的整体质量。

示例：

```text
总用例数：52
通过：48
失败：4

通过率：
- 意图识别：96%
- 成员隔离：100%
- 工具调用：92%
- 证据命中：88%
- 安全规则：96%
- 推荐质量：90%
- 输出结构：98%

主要风险：
- 商品类目问题偶尔误走餐单链路
- 血脂相关报告证据召回不足
```

### 8.3 Harness Dashboard

定位：把 Harness 结果可视化，便于展示。

建议模块：

```text
总体通过率
能力维度通过率
最近失败用例
工具调用轨迹
证据命中结果
安全规则检查结果
推荐质量评分
版本对比趋势
```

## 9. 和现有系统的关系

Harness Engineering 复用现有系统能力，不替代线上业务模块。

对应关系：

| 现有模块 | Harness 检查内容 |
| --- | --- |
| `LangChainAgentRunner` | 工具调用、respond 输出、token 和错误 |
| `KbSearchTool` | 报告召回、成员隔离、证据命中 |
| `MealPlanTool` | 餐单工具是否被正确调用 |
| `MallRecommendTool` | 商品标签、安全规则、推荐证据 |
| `MemorySearchTool` | 偏好和反馈是否正确检索 |
| `HealthProfileService` | 健康画像是否参与推荐 |
| `AgentEvidenceCollector` | 证据链是否完整 |
| 前端结构化卡片 | response schema 是否满足渲染 |

与 `Context Engineering Layer` 的关系：

```text
Context Engineering 负责构造 Agent 使用的上下文。
Harness Engineering 负责验证这些上下文是否被正确选择、压缩、使用和追踪。
```

与推荐证据链的关系：

```text
推荐证据链负责向用户解释“为什么推荐”。
Harness Engineering 负责验证这个“为什么”是否真实、完整、没有冲突。
```

## 10. 推荐迭代路径

### P1：最小 Harness

目标：

```text
建立 10-20 个核心 eval case
记录 Agent 工具调用
检查 expected_tools / forbidden_tools
检查是否调用 respond
输出命令行回归报告
```

适合先覆盖：

```text
餐单问题
商品类目问题
报告问答
偏好记忆问题
```

### P2：证据和成员隔离检查

目标：

```text
记录 Context Snapshot
检查目标成员是否正确
检查报告证据是否来自正确成员
检查 required_evidence 是否命中
```

适合覆盖：

```text
爸爸报告问答
妈妈报告问答
爸爸妈妈对比
全家推荐
```

### P3：安全规则和推荐质量检查

目标：

```text
检查禁忌标签
检查健康画像和商品标签匹配
检查推荐是否违反慢病、过敏、偏好边界
```

适合覆盖：

```text
高血压低钠
血脂偏高少油
控糖低糖
不喜欢鱼替代
预算敏感降价推荐
```

### P4：反馈闭环 Harness

目标：

```text
模拟用户反馈
检查记忆写入
检查下一轮推荐是否受反馈影响
检查反馈没有覆盖健康安全规则
```

适合覆盖：

```text
太贵了
不喜欢某类食物
加入购物车
换一个
以后别推荐甜的
```

### P5：Dashboard 和展示

目标：

```text
展示总体通过率
展示工具调用轨迹
展示上下文快照
展示证据命中
展示失败用例和修复建议
```

```text
粮达健康通过 Harness Engineering 建立了 Agent 质量保障体系，让健康推荐不只会生成，还能被测试、被追溯、被持续优化。
```

## 11. 画架构图建议

### 11.1 Harness 总体架构图

推荐节点：

```text
Eval Case Set
Test Data Loader
Agent Runner
Tool Call Recorder
Context Snapshot Recorder
Response Capture
Evaluation Layer
Diagnosis Layer
Regression Report
Harness Dashboard
```

推荐连线：

```text
Eval Case Set → Test Data Loader
Test Data Loader → Agent Runner
Agent Runner → Tool Call Recorder
Agent Runner → Context Snapshot Recorder
Agent Runner → Response Capture
Tool Call Recorder → Evaluation Layer
Context Snapshot Recorder → Evaluation Layer
Response Capture → Evaluation Layer
Evaluation Layer → Diagnosis Layer
Diagnosis Layer → Regression Report
Regression Report → Harness Dashboard
```

### 11.2 Evaluation Layer 架构图

推荐节点：

```text
Tool Call Trace
Context Snapshot
Evidence Items
Product Recommendations
Final Response
Intent Check
Member Isolation Check
Tool Call Check
Evidence Hit Check
Safety Rule Check
Recommendation Quality Check
Response Schema Check
Case Result
```

推荐连线：

```text
Tool Call Trace → Tool Call Check
Context Snapshot → Intent Check
Context Snapshot → Member Isolation Check
Evidence Items → Evidence Hit Check
Product Recommendations → Safety Rule Check
Product Recommendations → Recommendation Quality Check
Final Response → Response Schema Check
所有 Check → Case Result
```

### 11.3 Harness 闭环图

推荐节点：

```text
Prompt / Tool / RAG / Rule Change
Harness Regression
Failed Case
Failure Classification
Root Cause Hint
Fix Suggestion
Prompt / Rule / Tool Boundary Update
Stable Agent Version
```

推荐连线：

```text
Prompt / Tool / RAG / Rule Change → Harness Regression
Harness Regression → Failed Case
Failed Case → Failure Classification
Failure Classification → Root Cause Hint
Root Cause Hint → Fix Suggestion
Fix Suggestion → Prompt / Rule / Tool Boundary Update
Prompt / Rule / Tool Boundary Update → Harness Regression
Harness Regression → Stable Agent Version
```

## 12. 示例 Demo 用例

### 12.1 餐单到商品推荐

```json
{
  "case_id": "demo_dad_dinner_001",
  "input": "爸爸今晚吃什么，顺便推荐可以买的",
  "history": [
    {
      "role": "user",
      "content": "爸爸不喜欢鱼，预算别太高"
    }
  ],
  "target_member": "爸爸",
  "expected_tools": ["meal_plan", "mall_recommend", "respond"],
  "required_contexts": ["health_fact", "memory", "product", "safety"],
  "required_evidence": ["血脂偏高"],
  "forbidden_product_tags": ["high_sodium", "high_fat"],
  "expected_product_tags": ["low_sodium", "high_fiber"],
  "expected_response_kind": "meal_plan"
}
```

### 12.2 商品类目直推

```json
{
  "case_id": "demo_family_oil_001",
  "input": "推荐一款适合全家人的油",
  "target_scope": "family",
  "expected_intent": "product_recommendation",
  "expected_tools": ["mall_recommend", "respond"],
  "forbidden_tools": ["meal_plan"],
  "expected_product_category": "oil"
}
```

### 12.3 报告证据追溯

```json
{
  "case_id": "demo_dad_lipid_report_001",
  "input": "爸爸报告里血脂怎么样？",
  "target_member": "爸爸",
  "expected_intent": "report_qa",
  "expected_tools": ["kb_search", "respond"],
  "required_evidence": ["总胆固醇", "血脂偏高"],
  "forbidden_member_sources": ["妈妈", "孩子"],
  "expected_response_kind": "kb_interpretation"
}
```

### 12.4 偏好记忆检索

```json
{
  "case_id": "demo_dad_memory_fish_001",
  "input": "爸爸是不是不喜欢鱼？",
  "target_member": "爸爸",
  "expected_intent": "memory_query",
  "expected_tools": ["memory_search", "respond"],
  "required_memory": ["不喜欢鱼"],
  "expected_response_kind": "qa"
}
```
