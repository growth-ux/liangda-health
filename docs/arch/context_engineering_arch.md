# Context Engineering 技术架构

日期：2026-06-20

## 1. 架构目标

Context Engineering Layer 负责把家庭健康场景中的多源信息转化为 Agent 可消费的结构化上下文。

它分为两层：

```text
Context Sources：上下文来自哪里
Context Processing：上下文如何被检索、压缩、摘要、排序、裁剪和追踪
```


## 2. 总体分层

```text
Context Engineering Layer
    ├─ Context Sources
    │   ├─ Member Context
    │   ├─ Health Fact Context
    │   ├─ Memory Context
    │   ├─ Product Context
    │   └─ Safety Context
    └─ Context Processing
        ├─ Context Retrieval
        ├─ Context Compression
        ├─ Context Summarization
        ├─ Context Ranking
        ├─ Context Budgeting
        ├─ Context Pruning
        ├─ Context Snapshot
        └─ Context Eval
```

边界：

```text
Context Sources 只定义数据来源、领域语义和可输出字段。
Context Processing 只定义加工策略、选择策略和质量保障。
```

## 3. 架构关系

## 4. Context Sources

### 4.1 Member Context

定位：描述本轮问题对应哪个家庭成员或家庭范围。

子能力：

| 子能力 | 实现 | 作用 |
| --- | --- | --- |
| Member Resolution | 将“爸爸 / 妈妈 / 他 / 她 / 全家”解析为 `member_id` 或 family scope | 确定上下文对象 |
| Member Isolation | 报告、健康事实、记忆、推荐结果按 `member_id` 隔离 | 防止跨成员串用数据 |
| Family Scope Merge | 全家问题合并共同原则，并保留成员差异 | 支持家庭餐单和家庭推荐 |
| Reference Carry-over | 多轮对话中沿用上一轮明确成员指代 | 支持“那他呢”“换一个”等追问 |

输出示例：

```json
{
  "scope": "member",
  "target_member": {
    "member_id": "mem_dad",
    "display_name": "爸爸",
    "relation": "父亲"
  }
}
```

### 4.2 Health Fact Context

定位：提供报告原文证据和结构化健康事实。

子能力：

| 子能力 | 实现 | 作用 |
| --- | --- | --- |
| RAG Context | 报告文本切 chunk、embedding 入库，按成员和问题召回 | 提供原文依据 |
| Structured Health Facts | 从报告抽取异常指标、风险、建议、复查项 | 把报告转为可计算事实 |
| Evidence Grounding | 保留 `document_id`、页码、chunk、证据短句 | 支持证据链和追溯 |
| Trend Context | 后续按时间聚合多份报告事实 | 支持指标趋势问题 |

输出示例：

```json
{
  "health_facts": [
    {
      "name": "血压偏高",
      "status": "warning",
      "source_document_id": "doc_2026_checkup",
      "source_page_no": 3,
      "evidence_text": "收缩压高于参考范围"
    }
  ]
}
```

### 4.3 Memory Context

定位：提供当前会话和跨会话个性化信息。

子能力：

| 子能力 | 实现 | 作用 |
| --- | --- | --- |
| Short-term Session Memory | 保留当前会话目标、约束、刚确认的信息 | 支持连续追问 |
| Long-term User Memory | 使用 mem0 保存偏好、排斥、阶段目标、营销反馈 | 支持跨会话个性化 |
| Memory Scoping | 区分成员级记忆和家庭级记忆 | 避免个人偏好误当全家偏好 |
| Memory Write-back | 用户反馈后写入长期记忆 | 形成反馈闭环 |

输出示例：

```json
{
  "memories": {
    "session": {
      "goal": "为爸爸推荐控脂晚餐",
      "active_constraints": ["不吃鱼", "预算适中"]
    },
    "long_term": {
      "preferences": ["喜欢咸口"],
      "avoidance": ["不喜欢鱼"],
      "goals": ["最近想控脂"],
      "marketing_feedback": ["对高价商品较敏感"]
    }
  }
}
```

### 4.4 Product Context

定位：提供商品候选、商品标签和推荐依据。

子能力：

| 子能力 | 实现 | 作用 |
| --- | --- | --- |
| Product Tagging | 商品维护低钠、低糖、高纤维、高钙等健康标签 | 支持健康匹配 |
| Candidate Pool | 按类目、健康目标、预算形成候选池 | 缩小推荐范围 |
| Recommendation Evidence | 保存商品推荐理由和匹配标签 | 支持推荐证据链 |
| Feedback Context | 点击、跳过、收藏、购买意愿进入后续排序 | 支持营销闭环 |

输出示例：

```json
{
  "product_context": {
    "category_hint": "调味品",
    "candidate_limit": 6,
    "match_tags": ["low_sodium", "healthy_seasoning"]
  }
}
```

### 4.5 Safety Context

定位：提供不可被偏好和营销目标覆盖的健康安全上下文。

子能力：

| 子能力 | 实现 | 作用 |
| --- | --- | --- |
| Hard Constraint Extraction | 从过敏、禁忌、报告异常、健康标签提取硬约束 | 明确不可突破的边界 |
| Safety Priority | 安全约束优先于记忆偏好和营销目标 | 处理上下文优先级 |
| Conflict Resolution | 识别“偏好 vs 健康事实”等冲突 | 给出处理策略 |
| Safe Alternative Generation | 将冲突偏好转成安全替代方案 | 不只拒绝，也能推荐 |

优先级：

```text
过敏 / 禁忌
> 报告事实
> 健康标签
> 近期设备状态
> 当前问题
> 长期记忆偏好
> 营销转化目标
```

输出示例：

```json
{
  "safety_context": {
    "hard_constraints": ["低钠"],
    "avoid_tags": ["咸菜", "腌制品", "重盐调味"],
    "conflict_resolution": [
      "喜欢咸口，但血压偏高，只能推荐低钠替代"
    ]
  }
}
```

## 5. Context Processing

### 5.1 Context Retrieval

定位：从各类 Context Source 中按任务召回相关上下文。

处理对象：

```text
Member Context：解析当前成员或家庭范围
Health Fact Context：召回报告片段和健康事实
Memory Context：召回短期会话状态和长期记忆
Product Context：召回商品候选和标签
Safety Context：召回硬约束和冲突规则
```

输出：

```text
候选上下文集合 candidate_contexts
```

### 5.2 Context Compression

定位：把长文本和复杂对象压缩为结构化字段。

处理规则：

```text
报告原文 → 指标名 / 状态 / 来源 / 证据短句
记忆文本 → 类型 / 归属 / 内容 / 置信度
商品详情 → 商品名 / 标签 / 匹配点 / 风险标签
安全规则 → 硬约束 / 避免项 / 替代策略
```

示例：

```json
{
  "type": "health_fact",
  "name": "总胆固醇",
  "status": "warning",
  "source": "体检报告 p3",
  "evidence": "总胆固醇高于参考范围"
}
```

### 5.3 Context Summarization

定位：为多轮对话维护会话级摘要，避免持续塞入完整历史消息。

输出示例：

```json
{
  "session_goal": "为爸爸推荐控脂晚餐和商品",
  "active_constraints": ["不吃鱼", "预算适中", "少油"],
  "last_decision": "上轮推荐豆腐、燕麦和低钠调味"
}
```

作用：

```text
支持连续追问
减少历史消息 token
保留用户刚确认的约束
```

### 5.4 Context Ranking

定位：对候选上下文排序，决定哪些优先进入模型或工具。

排序原则：

```text
Safety Context
> Member Context
> 当前任务相关 Health Fact Context
> 最新报告和近期设备
> Memory Context
> Product Context
> 表达风格和营销信息
```

作用：

```text
保证关键事实和安全约束优先
避免低价值上下文挤占窗口
```

### 5.5 Context Budgeting

定位：为每类上下文分配预算。

建议预算：

```text
Safety Context：必须保留
Member Context：必须保留
Health Fact Context：最多 8 条结构化事实
RAG 原文片段：最多 3 段
Memory Context：最多 5 条
Product Context：最多 6 个商品
Session Summary：最多 500 字
```

作用：

```text
控制上下文长度
降低调用成本
提升输出稳定性
```

### 5.6 Context Pruning

定位：超出预算时裁剪低价值上下文。

裁剪顺序：

```text
寒暄和重复确认
重复商品描述
低相关记忆
低置信度 RAG 片段
过旧设备状态
```

不可裁剪：

```text
目标成员
过敏 / 禁忌
关键报告异常
当前用户问题
```

### 5.7 Context Snapshot

定位：记录本次 Agent 调用实际使用和丢弃的上下文。

输出示例：

```json
{
  "message_id": "msg_xxx",
  "intent": "meal_product_recommendation",
  "target_member_id": "mem_dad",
  "used_context": {
    "member": "mem_dad",
    "health_facts": ["fact_001"],
    "memories": ["memory_003"],
    "product_tags": ["low_sodium"],
    "safety_rules": ["低钠"]
  },
  "dropped_context": [
    {
      "type": "product",
      "reason": "命中高盐或腌制品"
    }
  ]
}
```

作用：

```text
调试
证据链
竞赛展示
Context Eval
```

### 5.8 Context Eval

定位：评估上下文选择是否正确，不只评估最终回答。

示例：

```json
{
  "case_id": "dad_salty_preference_hypertension",
  "input": "爸爸喜欢咸口，推荐点下饭的",
  "expected": {
    "must_include_context": ["爸爸", "血压偏高", "低钠"],
    "must_not_include_context": ["妈妈记忆"],
    "must_not_recommend": ["咸菜", "腌制品", "重盐调味"]
  }
}
```

## 6. Structured Context

Agent 调用前装配为统一结构：

```json
{
  "intent": "meal_product_recommendation",
  "member_context": {
    "scope": "member",
    "member_id": "mem_dad",
    "display_name": "爸爸"
  },
  "health_fact_context": {
    "facts": ["血压偏高，来源体检报告第 3 页"]
  },
  "memory_context": {
    "session_goal": "推荐控脂晚餐",
    "preferences": ["喜欢咸口"],
    "avoidance": ["不喜欢鱼"]
  },
  "product_context": {
    "category_hint": "调味品",
    "match_tags": ["low_sodium"]
  },
  "safety_context": {
    "hard_constraints": ["低钠"],
    "avoid_tags": ["咸菜", "腌制品"],
    "conflict_resolution": ["咸口偏好通过低钠替代满足"]
  },
  "processing_meta": {
    "compression": true,
    "budget_policy": "default",
    "pruned": true
  }
}
```

## 7. Evidence 与 Snapshot 边界

```text
Evidence：面向用户，解释回答和推荐依据。
Context Snapshot：面向开发和评测，记录上下文选择、裁剪和策略执行过程。
```

Evidence 示例：

```text
报告依据
互动记忆
商品匹配点
```

Snapshot 示例：

```text
用了哪些上下文
丢弃了哪些上下文
为什么丢弃
触发了哪些安全规则
```

## 8. 后续迭代

```text
P1 明确五类 Context Sources 的结构化输出
P2 增加 Context Compression 和 Context Summarization
P3 增加 Context Ranking / Budgeting / Pruning
P4 增加 Context Snapshot
P5 建立 Context Eval 用例
P6 增加 Context Debug 展示页
```
