# Agent 回复结构化卡片化设计

日期：2026-06-16

## 1. 背景与目标

当前 Agent 回复是纯文本，餐单、健康解读、一般问答都按段落输出，信息密度均匀地糊在一起，用户阅读体验差。本设计把 Agent 的所有用户可见回复改造成**结构化 JSON 卡片**，前端按场景路由到不同卡片组件渲染。

目标：

- 所有 Agent 回复走结构化 schema（餐单 / 健康解读 / 一般问答 / 寒暄 / 一般建议）
- `summary_text` 承载口语化总结，沿用现有流式输出
- 卡片 payload 在 `respond` 工具返回后一次性插入
- 餐单回复使用时间线 + 标签云的视觉风格（用户在 mockup 中确认）
- LLM 必须输出合法 JSON，解析失败让响应失败——不降级到纯文本
- 不引入新框架；不写"并行实现"或"兜底 Markdown 路径"

不在范围：

- 改造用户消息（保持纯文本输入）
- 重做聊天页布局
- 改造 `mall_recommend`（商品推荐卡片保留现有结构化事件通道）
- 多语言
- 历史消息迁移

## 2. 约束

- 后端：FastAPI + SQLAlchemy + LangChain（已有）
- 前端：React + Vite + TypeScript（已有）
- 不引入新依赖
- 视觉风格参照用户在浏览器伴侣中选定的方向 C（时间线 + 标签云）
- 改动可控可回滚：`meal_plan` 工具的内部实现不动；LLM 自主决定如何消费工具结果再调 `respond`

## 3. 核心原则

1. **LLM 不直接对用户说话**。所有用户可见文本必须经 `respond` 工具的 `summary_text` 字段。
2. **判别式渲染**：所有 payload 通过 `kind` 字段路由到对应卡片组件。
3. **不降级**：JSON 解析失败 / 缺字段 / kind 未知 → 抛错，前端标记 `status='failed'`，显示"生成失败，请重试"。不写"如果 JSON 不行就回退到 markdown 文本"。
4. **流式分层**：`summary_text` 继续按现有 SSE 方式流式；卡片 payload 在 `respond` 工具返回后整体插入。
5. **不绕过工具**：如果 LLM 在 `respond` 之后又发普通 AIMessageChunk 文字，丢弃并日志告警。

## 4. 整体架构

```text
用户消息
   ↓
[前端] POST /api/agent/messages
   ↓
[后端] LangChainAgentRunner.run_stream()
   ├─ 创建 Agent：tools = [meal_plan, mall_recommend, memory_search, kb_search, respond]
   ├─ respond 工具的参数 schema = StructuredResponse Pydantic 模型的 JSON schema
   └─ Agent 内部工具调用 → 再调 respond(StructuredResponse)
        ↓
   stream 模式
   ├─ respond 工具调用的 tool_call_chunk 中属于 summary_text 字段的 token
   │     → emit("delta", text)
   └─ respond 工具的 ToolMessage → 解析 args → Pydantic 校验 → emit("card", StructuredCard)
        ↓
[前端] 累积 message.content (summary_text) + message.card (StructuredCard)
   ↓
MessageBubble：先显 summary_text，再显 <StructuredCard>
```

## 5. Schemas

新增文件：

- `backend/app/schemas/agent_response.py`（Pydantic）
- `frontend/src/schemas/agentResponse.ts`（TypeScript，手写同步）

### 5.1 顶层 Envelope

```python
class StructuredResponse(BaseModel):
    kind: Literal["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]
    summary_text: str = Field(..., max_length=400)
    payload: "PayloadUnion"
```

### 5.2 Payload 联合

| kind | 关键字段 |
|------|----------|
| `meal_plan` | `scope: "family" \| "member"`、`target_member_name`、`meal_items[]`（slot/title/summary）、`member_adjustments[]`（member_name/note/tags）、`avoid_tags[]`、`extra_note` |
| `qa` | `question_topic`、`answer`、`tips[]` |
| `greeting` | `message`、`suggested_topics[]` |
| `kb_interpretation` | `topic`、`evidence[]`（source/excerpt）、`suggestions[]`（text/priority）、`red_flags[]` |
| `general_advice` | `topic`、`advice`、`cautions[]` |

### 5.3 判别字段

所有 Payload 共享 `kind`，前端 `StructuredCard` 组件按它 `switch` 路由到 5 个子组件。

## 6. 后端改动

### 6.1 新增 schema

`backend/app/schemas/agent_response.py`：定义上面 §5 全部 Pydantic 模型 + 联合类型。

### 6.2 `langchain_agent.py` 改动

- 新增 `respond` 工具到 `_tools()`：
  - 工具参数 schema 来自 `StructuredResponse.model_json_schema()`
  - 实现简单返回 `"ok"`（payload 实际在 tool call 的 args 里）
- `stream()` 路由：
  - respond 工具调用的 `tool_call_chunk` 中属于 `summary_text` 字段的 token → 走现有 `delta` 路径
  - `respond` 工具的 ToolMessage → `StructuredResponse.model_validate(args)` 校验 → emit `("card", payload)`
  - 其他 AIMessageChunk（content 字段非空且不是 respond tool call 关联）→ 丢弃 + warn 日志（视为 LLM 绕过工具直接说话）
- `run()` 同步：把 `card` 加到 result 字典

### 6.3 `meal_plan_service.py` 改动

无。`meal_plan` 工具仍返回 Markdown 文本；LLM 自行抽取信息塞进 `respond` 的 `meal_plan` payload。

### 6.4 system prompt 调整

在 `SYSTEM_PROMPT_TEMPLATE`（`langchain_agent.py`）增加：

- 强调"必须调用 `respond` 工具才算完成回复"
- 列出 5 种 kind 的选择规则（用户问餐单 → meal_plan；用户问"为什么/要不要紧" 且有报告 → kb_interpretation；简单问答 → qa；首问 → greeting；其他 → general_advice）
- 提示每种 kind 对应的 payload 字段
- 保留现有"口语化、100-200 字"等要求于 `summary_text` 字段

## 7. 前端改动

### 7.1 新增/改动文件

| 文件 | 改动 |
|------|------|
| `frontend/src/api/agent.ts` | `AgentMessage` 加 `card?: StructuredCard` |
| `frontend/src/schemas/agentResponse.ts` | 新建，TypeScript 类型镜像 §5 |
| `frontend/src/components/chat/StructuredCard.tsx` | 新建，按 `kind` 路由 |
| `frontend/src/components/chat/cards/MealPlanCard.tsx` | 新建，时间线 + 标签云 |
| `frontend/src/components/chat/cards/QaCard.tsx` | 新建 |
| `frontend/src/components/chat/cards/GreetingCard.tsx` | 新建 |
| `frontend/src/components/chat/cards/KbInterpretationCard.tsx` | 新建 |
| `frontend/src/components/chat/cards/GeneralAdviceCard.tsx` | 新建 |
| `frontend/src/components/chat/MessageBubble.tsx` | summary_text 走现有 `MarkdownContent`；如 `message.card` 存在，在其下方渲染 `<StructuredCard>` |
| `frontend/src/components/chat/markdown.tsx` | 不动 |

### 7.2 渲染顺序

```text
[Avatar]  ┌─ summary_text（MarkdownContent，流式）──────┐
          │  ...                                          │
          │  ┌─ StructuredCard（payload 整体插入）──────┐ │
          │  │ MealPlanCard / QaCard / ...               │ │
          │  └────────────────────────────────────────────┘ │
          └──────────────────────────────────────────────────┘
          16:23
```

### 7.3 MealPlanCard 视觉（对应用户在 mockup 中选的方向 C）

```text
🍽️ 全家 · 今日三餐
┌──────┐ ┌──────┐ ┌──────┐
│早餐  │ │午餐  │ │晚餐  │   ← 三栏时间线，顶部色条
│xxx   │ │xxx   │ │xxx   │
└──────┘ └──────┘ └──────┘

👨‍👩‍👧 成员调整
[爸爸: 控脂] [女儿: +蛋] [奶奶: 低钠]   ← 标签云

⚠️ 避免：[油炸] [肥肉] [咸菜] [浓汤] ...

💡 女儿可额外加一个水煮蛋           ← extra_note
```

色板沿用项目现有 chat 组件色板（参考 `MessageBubble.tsx` / `ProductRecommendationCards.tsx` 已用色），不引入新 design token。

### 7.4 `meal_type=single`（单餐请求）

`meal_items` 只渲染对应 slot 的卡片；其他位置不显示。

## 8. 错误处理

| 场景 | 行为 | 前端展示 |
|------|------|----------|
| LLM 没调 `respond` | 抛 `ResponseSchemaError` | 消息 `status='failed'`，显示"生成失败，请重试" |
| `respond` 参数 Pydantic 校验失败 | 同上 | 同上 |
| `summary_text` 为空 / 超 400 字 | 校验失败 → 同上 | 同上 |
| `payload.kind` 不在白名单 | 校验失败 → 同上 | 同上 |
| LLM 调 `respond` 后又发普通 AIMessage 文字 | `stream` 检测丢弃 + warn 日志 | 用户无感 |
| `mall_recommend` 工具返回 Error | 保持现有行为 | `summary_text` 末尾 agent 加"暂时无法推荐商品" |

不写"JSON 解析失败时回退到 Markdown 文本"的兜底实现。

## 9. 测试

后端：

- `tests/test_agent_response_schema.py`：每个 kind 至少 1 个有效样例 + 2-3 个无效样例（kind 未知 / 字段缺失 / summary_text 超长）
- `tests/test_langchain_agent.py`：mock LLM 模拟三种失败路径
  - LLM 没调 `respond`
  - LLM 调了 `respond` 但参数不合法
  - LLM 在 `respond` 之后又发绕过文本

前端：

- `StructuredCard` 路由单测（5 个 kind 各一个用例）
- `MealPlanCard` 渲染快照（含 scope=family / scope=member / 单餐请求三种）
- `MessageBubble` 单测：summary_text + card 渲染顺序

不写 E2E（项目目前没这套），手测走实际 LLM 调用看：
- 问"妈妈今天一日三餐怎么吃"→ 餐单卡片 + summary_text
- 问"爸爸血脂偏高要紧吗"→ health_interpretation 卡片
- 问"早餐吃什么好"→ qa 卡片
- 打开聊天页（无历史）→ greeting 卡片

## 10. 验收标准

满足以下条件即认为完成：

1. 所有 Agent 用户可见回复经 `respond` 工具输出；`summary_text` 流式产出；`payload` 整体插入
2. 餐单回复渲染为时间线 + 标签云卡片
3. 健康解读、一般问答、寒暄、一般建议分别渲染为对应卡片
4. Pydantic 校验失败时消息标记 `failed`，无任何降级展示
5. `meal_plan` 工具仍正常调用，`mall_recommend` 仍正常触发商品卡片
6. 现有 SSE 流式通道不变；前端 `MarkdownContent` 仍负责 `summary_text` 渲染
7. 无新增依赖；无"并行实现"或"兜底 Markdown 路径"代码

## 11. 后续扩展（不在本阶段）

- 餐单/报告导出为 PDF
- 多日食谱
- 用户对卡片"换一换"交互
- 卡片 A/B 测试埋点
