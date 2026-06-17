# Agent 生成与推荐证据链设计

日期：2026-06-17

## 1. 背景与目标

项目原型 `@.superpowers/brainstorm/14240-1781663378/content/evidence-chain-chat.html` 已经把证据链的视觉方向定下来了：右栏展示生成依据（4 类）和推荐依据（每商品 1 项），与 prototype 信条——"工具产生结构化依据，不让模型自由编来源；Agent 只负责把依据组织成用户能读懂的话；前端把依据收进可展开区域，默认不打断聊天"。

本设计把这个原型落成可实现的代码，连接到现有 `LangChainAgentRunner` 的工具链和 SSE 流。

目标：

- 后端：5 种 assistant 回复 kind 全部支持 `evidence`；工具调用时维护 evidence 候选池；`respond` 工具 schema 加可选 `evidence_refs`；SSE 增加 `evidence` / `evidence_final` 事件
- 前端：右栏 `EvidencePanel`、切钮行 `EvidenceActions`、静态 `EvidenceItemCard`；流式阶段实时更新右栏；空状态按需展示
- 移动端：< 768px 不显示切钮，不渲染右栏（不做适配，避免范围蔓延）

不在范围：

- debug 视图（`?debug=1` 那种内部调试 UI）
- 会话级 evidence 概览
- "安全过滤" pipeline 描述作为 evidence 项
- 点击 evidence 跳转到报告/记忆/商品详情页
- 商品详情弹窗 / 抽屉
- 多语言

## 2. 约束

- 后端：FastAPI + SQLAlchemy + LangChain（已有）
- 前端：React + Vite + TypeScript + Tailwind + TanStack Query（已有）
- 不引入新依赖
- 不引入回退层 / 并行实现（遵循项目 "no over-design or fallback layers" 原则）
- 视觉风格沿用 prototype HTML（绿 = 生成链，橙 = 推荐链，浅色背景高亮）
- `meal_plan` / `memory_search` / `kb_search` / `mall_recommend` 工具的内部逻辑不重写，只在完成钩子里加 `EvidencePool.push`

## 3. 核心原则

1. **证据来源铁板钉钉**。`EvidenceItem.source_id` 必须指向一个真实存在的后端数据（HealthFact.id / Memory.id / Product.id 等）。LLM 不能自己编来源。
2. **LLM 选主次**。`respond` 工具接受 `evidence_refs`（ref_id + sort），LLM 表达"这条建议主要靠 X"；后端不做主次排序逻辑。
3. **不降级**：JSON 解析失败 / `ref_id` 不存在 / 候选池为空 → 静默跳过对应项；消息本身继续走，不抛错。
4. **按需展示**：右栏默认空；切钮出现条件是消息有 evidence；用户不点切钮，右栏保持空状态文案。
5. **静态 evidence**：右栏里的 evidence 项不可点击。摘要 + 来源标签就够回答"为什么"。

## 4. 整体架构

```text
用户消息
   ↓
[前端] POST /api/agent/sessions/{id}/messages:stream
   ↓
[后端] LangChainAgentRunner.stream()
   ├─ 创建 EvidencePool（绑本次 run 上下文，in-memory，不落库）
   ├─ tools = [kb_search, memory_search, meal_plan, mall_recommend, respond]
   ├─ respond 工具的 description 动态注入 EvidencePool.snapshot()
   └─ Agent 内部工具链：
        ├─ kb_search 完成 → push report_fact → emit("evidence", ...)
        ├─ memory_search 完成 → push memory → emit("evidence", ...)
        ├─ meal_plan 完成 → push profile → emit("evidence", ...)
        ├─ mall_recommend 完成 → push product → emit("evidence", ...)
        └─ respond(StructuredResponse{evidence_refs}) 完成
              ↓ resolve(ref_ids) → EvidenceItem[]
              ↓ emit("evidence_final", items)
              ↓ 入库 assistant_message.evidence = json.dumps(items)
   ↓
[前端] 累积 message.evidence_stream + message.evidence_final
   ↓
EvidenceActions（紧贴主消息下面）渲染切钮
EvidencePanel（右栏）默认 EvidenceEmpty，点切钮切换到对应 group
```

## 5. Schemas

### 5.1 后端 Pydantic

新增到 `backend/app/schemas/agent_response.py`：

```python
class EvidenceItem(BaseModel):
    type: Literal["report_fact", "profile", "device", "memory", "product"]
    title: str                  # "体检报告提示血压相关风险"
    excerpt: str                # 一句自然语言摘要（用户视图文案）
    source_id: str              # 后端真实 ID
    source_label: str           # "5月体检报告 p3" / "健康画像聚合" 等

class RespondEvidenceRef(BaseModel):
    ref_id: str                 # EvidencePool 里的候选 ID
    sort: int = 0               # 0-based，0 = 最主要

class EvidenceStreamEvent(BaseModel):
    message_id: str             # 占位 ID（assistant_start 时已分配）
    ref_id: str
    type: Literal["report_fact", "profile", "device", "memory", "product"]
    title: str
    excerpt: str
    source_label: str
    sort_hint: int              # 候选池 push 顺序

class EvidenceFinalEvent(BaseModel):
    message_id: str
    items: list[EvidenceItem]
```

`StructuredResponse` 加字段：

```python
class StructuredResponse(BaseModel):
    kind: Literal["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]
    summary_text: str = Field(..., max_length=400)
    payload: "PayloadUnion"
    evidence_refs: list[RespondEvidenceRef] = []   # 可空
```

5 种 kind 的 payload 统一加 `evidence: list[EvidenceItem] | None = None`。`kb_interpretation` 已有 `evidence: list[EvidenceItem]`（kb_interpretation payload 内的 evidence）—— 现有实现是 LLM 直接在 payload 里填，新设计统一改成"后端从 `evidence_refs` resolve 后覆盖写入"，让所有 kind 走同一条规则。

**存储**：evidence 嵌入到 `assistant_messages.card` 列的 JSON 里（沿用现有 `card` 列存储模式），**不**新增 `evidence` 列、不写迁移脚本。

### 5.2 前端 TypeScript

`frontend/src/schemas/agentResponse.ts`（手写同步）：

```ts
export type EvidenceType = "report_fact" | "profile" | "device" | "memory" | "product";

export interface EvidenceItem {
  type: EvidenceType;
  title: string;
  excerpt: string;
  source_id: string;
  source_label: string;
}

export interface EvidenceStreamItem extends EvidenceItem {
  ref_id: string;
  sort_hint: number;
}

export interface EvidencePanelState {
  messageId: string;
  group: "content" | "product";
  focusRefId?: string;
} | null;
```

## 6. Evidence 候选池

`backend/app/services/evidence_pool.py`（新增文件）：

```python
from dataclasses import dataclass, field
from threading import Lock

@dataclass
class EvidenceCandidate:
    ref_id: str
    type: str
    title: str
    excerpt: str
    source_label: str
    source_id: str
    raw: dict = field(default_factory=dict)

class EvidencePool:
    def __init__(self):
        self._candidates: dict[str, EvidenceCandidate] = {}
        self._counter: int = 0
        self._lock = Lock()

    def push(self, type_: str, title: str, excerpt: str,
             source_id: str, source_label: str, raw: dict | None = None) -> str:
        with self._lock:
            self._counter += 1
            ref_id = f"ref_{self._counter:03d}"
            self._candidates[ref_id] = EvidenceCandidate(
                ref_id=ref_id, type=type_, title=title, excerpt=excerpt,
                source_id=source_id, source_label=source_label, raw=raw or {},
            )
            return ref_id

    def snapshot(self) -> list[EvidenceCandidate]:
        # 按 push 顺序返回，给 LLM 看的清单
        with self._lock:
            return list(self._candidates.values())

    def resolve(self, ref_ids: list[str]) -> list[EvidenceItem]:
        # 静默跳过不存在的 ref_id
        with self._lock:
            return [
                EvidenceItem(
                    type=c.type, title=c.title, excerpt=c.excerpt,
                    source_id=c.source_id, source_label=c.source_label,
                )
                for c in (self._candidates.get(rid) for rid in ref_ids)
                if c is not None
            ]
```

`EvidencePool` **不落库**，绑在 `LangChainAgentRunner.stream()` 入口的局部变量上，`assistant_message` 入库后即销毁。

### 6.1 工具完成钩子

各工具 `_arun` 完成后调用 `EvidencePool.push`（伪代码）：

```python
# KbSearchTool
for fact in result.facts:
    pool.push(
        type_="report_fact",
        title=fact.name,
        excerpt=fact.evidence_text,
        source_id=fact.id,
        source_label=f"{fact.source_document_id} p{fact.source_page_no}",
        raw={"page": fact.source_page_no, "doc_id": fact.source_document_id},
    )

# MemorySearchTool
for mem in result.memories:
    pool.push(type_="memory", title=..., excerpt=mem.text,
              source_id=mem.id, source_label="互动记忆", raw={...})

# MealPlanTool
profile = result.profile
if profile.evidence_notes:
    for note in profile.evidence_notes:
        pool.push(type_="profile", title="健康画像", excerpt=note,
                  source_id=profile.id, source_label="健康画像聚合")

# MallRecommendTool
for item in result["items"]:
    pool.push(type_="product", title=item["name"],
              excerpt=item["reason"], source_id=item["product_id"],
              source_label=f"商城 · {item['name']}",
              raw={"score": item["score"], "tags": item.get("matched_tags", [])})
```

设备状态由 `member_provider` 提供入口时 push（具体方法名以项目现有 API 为准，参考 `MemberProvider` 已有的 device 暴露方法；如果项目没有现成方法，按"在工具 description 注入前从 `MemberContext` 拿一次 device state"的最简实现）：

```python
# in LangChainAgentRunner.stream() 入口（不假设具体方法名）
device_state = self._member_provider.get_member_context(member_id).device_state
if device_state:
    pool.push(type_="device", title="近 7 天手环状态",
              excerpt=f"平均睡眠 {device_state.avg_sleep_hours}h，深度睡眠占比 {device_state.deep_sleep_ratio}",
              source_id=device_state.id, source_label="手环 · 7d",
              raw={"window": "7d"})
```

> 具体 API 以实施时 `MemberProvider` 实际暴露的方法为准；如果完全没有现成方法，则**省略** `device` 类型——本设计不要求新增 device 状态采集能力，只接已经有的。

### 6.2 `pool.snapshot()` 注入 `respond` 工具 description 的格式

`LangChainAgentRunner` 在每次调 `respond` 工具前，动态拼一段 Markdown 注入到工具 description 末尾：

```text
## 当前可引用的 evidence（respond 时通过 evidence_refs 引用）

- ref_001 [report_fact] 体检报告提示血压相关风险 — 5月体检报告 p3
- ref_002 [memory] 妈妈晚上没胃口 — 互动记忆
- ref_003 [profile] 妈妈饮食原则：低钠、少油 — 健康画像聚合
- ref_004 [device] 近 7 天睡眠偏短 — 手环 · 7d
- ref_005 [product] 薄盐生抽：命中 low_sodium — 商城 · 薄盐生抽

## 规则

- 只允许引用上述 ref_id；其他 ID 视为非法，respond 时跳过
- 0 = 这条建议最主要依据，1 = 次要，以此类推
- evidence_refs 可空（不传时后端取前 3 条）
```

LLM 看到 description 后自然在 `respond` 工具调用里填 `evidence_refs`。**不修改 system prompt**——只在工具 description 末尾动态追加。

## 7. SSE 事件扩展

`backend/app/services/agent_service.py` 处理新事件。

事件序列（一次 assistant 回复）：

```text
assistant_start
  ├─ tool_call: kb_search
  ├─ evidence   {ref_id, type, title, excerpt, source_label, sort_hint}
  ├─ tool_call: memory_search
  ├─ evidence   ...
  ├─ tool_call: meal_plan
  ├─ evidence   ...
  ├─ tool_call: mall_recommend
  ├─ evidence   ...
  ├─ delta      (summary_text 流式)
  ├─ product_recommendations  (商品流)
  ├─ card       (StructuredResponse 解析结果，payload.evidence 已填充)
  ├─ evidence_final   {message_id, items: EvidenceItem[]}
  └─ assistant_done {message_id}
```

**关键不变量**：

- `evidence` 事件在工具完成时**立即推**，不等 `respond`
- `evidence_final` 事件只触发一次，在 `card` 事件之后、`assistant_done` 之前
- `assistant_message` 入库时 `card` 列的 JSON 里 `payload.evidence` 已包含 `evidence_final.items`（在 `_extract_card` 时由后端覆盖写入）
- `assistant_done` 事件**不带** evidence 字段——前端从 `card.evidence` 读，避免双轨存储

## 8. 切钮 & 右栏规则

### 8.1 切钮渲染规则

- `message.card?.payload?.evidence` 长度 > 0 → "**生成依据**" 切钮
- `message.product_recommendations` 长度 > 0 → "**推荐依据**" 切钮
- 推荐链额外有子切钮 "**{p.name} 依据**"（每个商品 1 个，触发时 `focusRefId = product_ref_id`）
- 切钮都为空 → 整行不渲染

### 8.2 右栏状态机

```text
IDLE (默认空状态) ─用户点切钮→ STREAMING (流式累积) ─assistant_done→ COMPLETE
```

- **IDLE**：`EvidenceEmpty` 渲染 "提出问题后，点聊天区里的「生成依据」或「推荐依据」查看 AI 参考依据"
- **STREAMING**：用 `message.evidence_stream` 渲染（按 `sort_hint` 升序）；无对应 group 的流式项时回到 `EvidenceEmpty`
- **COMPLETE**：用 `message.card.payload.evidence` 渲染（按 LLM 传的 `sort` 升序）；同时 `message.evidence_final` 前端 state 留作备份（不展示给用户）
- **未选中**：`EvidenceEmpty` 渲染（不出现但已选中的旧切钮点击会重新激活）

### 8.3 选中态

当前 `evidencePanelState` 匹配切钮 → 切钮边框 + 背景变浅绿/浅橙。右栏对应 evidence 项同样高亮。

## 9. 前端组件

新增 `frontend/src/components/chat/evidence/`：

```
evidence/
  EvidencePanel.tsx
  EvidenceEmpty.tsx
  EvidenceList.tsx
  EvidenceItemCard.tsx
  EvidenceActions.tsx
  types.ts
  __tests__/
    EvidenceEmpty.test.tsx
    EvidenceActions.test.tsx
    EvidenceItemCard.test.tsx
```

### EvidencePanel

```tsx
interface Props {
  state: EvidencePanelState;
  message: ChatMessage | null;  // 切到未生成消息时为 null
}

export function EvidencePanel({ state, message }: Props) {
  if (!state || !message) return <EvidenceEmpty />;
  if (isMobile()) return null;  // 移动端不渲染

  const items = state.group === "content"
    ? getContentEvidence(message)
    : getProductEvidence(message, state.focusRefId);

  if (items.length === 0) return <EvidenceEmpty />;
  return <EvidenceList items={items} focusRefId={state.focusRefId} />;
}
```

### EvidenceActions

```tsx
interface Props {
  message: ChatMessage;
  onActivate: (state: EvidencePanelState) => void;
  currentState: EvidencePanelState;
}

export function EvidenceActions({ message, onActivate, currentState }: Props) {
  if (isMobile()) return null;
  const hasContent = (message.evidence_final?.length ?? 0) > 0;
  const hasProducts = (message.product_recommendations?.length ?? 0) > 0;
  if (!hasContent && !hasProducts) return null;

  return (
    <div className="evidence-actions-row">
      {hasContent && (
        <button
          className={isActive("content", currentState, message.id) ? "active" : ""}
          onClick={() => onActivate({ messageId: message.id, group: "content" })}
        >生成依据</button>
      )}
      {hasProducts && (
        <button
          className={isActive("product", currentState, message.id) ? "active" : ""}
          onClick={() => onActivate({ messageId: message.id, group: "product" })}
        >推荐依据</button>
      )}
      {hasProducts && message.product_recommendations.map(p => (
        <button
          className={isActive("product", currentState, message.id, p.ref_id) ? "active" : ""}
          onClick={() => onActivate({ messageId: message.id, group: "product", focusRefId: p.ref_id })}
        >{p.name} 依据</button>
      ))}
    </div>
  );
}
```

### EvidenceItemCard

```tsx
interface Props {
  item: EvidenceItem | EvidenceStreamItem;
  isHighlight: boolean;
}

export function EvidenceItemCard({ item, isHighlight }: Props) {
  return (
    <article className={`evidence ${isHighlight ? "highlight" : ""}`}>
      <div>
        <h3>{item.title}</h3>
        <p>{item.excerpt}</p>
      </div>
      <span className="ev-type">{TYPE_LABEL[item.type]}</span>
    </article>
  );
}
```

### MessageBubble 集成

```tsx
function MessageBubble({ message }: { message: ChatMessage }) {
  return (
    <div className="message-bubble">
      {message.card ? <StructuredCard ... /> : <TextBubble ... />}
      {message.product_recommendations && <ProductRecommendationCards ... />}

      {!isMobile() && <EvidenceActions
        message={message}
        onActivate={setPanelState}
        currentState={panelState}
      />}
    </div>
  );
}
```

## 10. 错误处理（无回退层）

| 场景 | 行为 |
|---|---|
| 工具调用抛异常 | 该工具的 `EvidenceCandidate` 不入池（`try/except` 包裹 push），`evidence` 事件不发 |
| LLM 没传 `evidence_refs` | 从 `EvidencePool.snapshot()` 按 push 顺序取前 3 条（**不是回退，是默认排序**） |
| LLM 传了不存在的 `ref_id` | 静默跳过；`EvidenceItem` 列表里没有它 |
| 候选池为空 | `card.payload.evidence = null`；前端切钮不渲染；右栏对应 group 显示 `EvidenceEmpty` |
| 入库失败（`card` JSON 写不进去） | `assistant_message` 入库本身失败时整条消息回滚（不引入新回退路径） |
| 前端收到 `evidence` 事件但 ref_id 在最终 `evidence_final` 里没有 | 流式阶段显示过的项在 `assistant_done` 时从前端 state 移除（**不**保留为"曾经有过的证据"） |

## 11. 文件改动清单

### 后端

| 文件 | 改动 |
|---|---|
| `backend/app/schemas/agent_response.py` | 新增 `EvidenceItem` / `RespondEvidenceRef` / `EvidenceStreamEvent` / `EvidenceFinalEvent`；5 种 payload 都加 `evidence: list[EvidenceItem] \| None`；`StructuredResponse` 加 `evidence_refs` |
| `backend/app/services/evidence_pool.py` | **新增**：`EvidenceCandidate` dataclass + `EvidencePool` class |
| `backend/app/services/langchain_agent.py` | `stream()` 入口创建 `EvidencePool`；`respond` 工具 description 动态注入 `pool.snapshot()`；`_extract_card` 在解析 `StructuredResponse` 后用 `pool.resolve(evidence_refs)` 覆盖写入 `payload.evidence`；SSE yield 新增 `evidence` / `evidence_final` 事件；`member_provider` push `device` 候选（如有） |
| `backend/app/services/agent_tools.py` | 4 个工具的 `_arun` 完成钩子 `try/except` 包裹 `pool.push` |
| `backend/app/services/agent_service.py` | `stream_message` 处理新事件类型 |
| `backend/tests/test_evidence_pool.py` | **新增**：单元测试 |
| `backend/tests/test_respond_evidence_refs.py` | **新增**：5 种 kind roundtrip |
| `backend/tests/test_evidence_fallback.py` | **新增**：LLM 不传 ref_ids → 前 3 条 |
| `backend/tests/test_agent_evidence_stream.py` | **新增**：端到端 SSE 事件序列断言 |

**不新增表 / 不写迁移**——evidence 嵌入 `assistant_messages.card` JSON 字符串里，沿用 `card` 列存储。

### 前端

| 文件 | 改动 |
|---|---|
| `frontend/src/schemas/agentResponse.ts` | 新增 `EvidenceItem` / `EvidenceStreamItem` / `EvidencePanelState` TS 类型 |
| `frontend/src/components/chat/evidence/EvidencePanel.tsx` | **新增** |
| `frontend/src/components/chat/evidence/EvidenceEmpty.tsx` | **新增** |
| `frontend/src/components/chat/evidence/EvidenceList.tsx` | **新增** |
| `frontend/src/components/chat/evidence/EvidenceItemCard.tsx` | **新增** |
| `frontend/src/components/chat/evidence/EvidenceActions.tsx` | **新增** |
| `frontend/src/components/chat/evidence/types.ts` | **新增** |
| `frontend/src/components/chat/MessageBubble.tsx` | 集成 `EvidenceActions` + 移动端判断 |
| `frontend/src/components/chat/MessageList.tsx` | 维护 `evidencePanelState` state + 接收 `onEvidence` / `onEvidenceFinal` 回调 |
| `frontend/src/api/agent.ts` | `sendAgentMessageStream` 加 `onEvidence` / `onEvidenceFinal` 回调 |
| `frontend/src/components/chat/ChatPage.tsx` | 桌面端三栏布局增加 `EvidencePanel`（移动端不渲染） |
| `frontend/src/components/chat/evidence/__tests__/EvidenceEmpty.test.tsx` | **新增** |
| `frontend/src/components/chat/evidence/__tests__/EvidenceActions.test.tsx` | **新增** |
| `frontend/src/components/chat/evidence/__tests__/EvidenceItemCard.test.tsx` | **新增** |

## 12. 测试

### 单元测试

- `test_evidence_pool.py` — push 顺序、ref_id 唯一、snapshot 不重复、resolve 跳过未知 ref_id
- `test_respond_evidence_refs.py` — 5 种 kind 的 `StructuredResponse` roundtrip
- `test_evidence_fallback.py` — 候选池 push 3 条 + LLM 不传 ref_ids → resolve 出前 3 条

### 集成测试

- `test_kb_search_evidence.py` — 跑 kb_search → EvidencePool 收到 `report_fact`
- `test_product_evidence.py` — 跑 mall_recommend → EvidencePool 收到 `product` × N
- `test_agent_evidence_stream.py` — 端到端跑 meal_plan + mall_recommend 工具链，断言 SSE 事件序列：`assistant_start` → `evidence` × N → `card` → `evidence_final` × 1 → `assistant_done` × 1

### 前端测试

- `EvidenceEmpty.test.tsx` — 默认空状态渲染
- `EvidenceActions.test.tsx` — 切钮显示规则（有/无 content evidence、有/无 product evidence）
- `EvidenceItemCard.test.tsx` — 静态展示 + 高亮态
- `MessageList.test.tsx` — 切钮点击 → `evidencePanelState` 更新；流式事件 → `evidence_stream` 累积

### 手工 E2E

- 跑一次真实 meal_plan 工具链 + mall_recommend，观察前端：消息生成中右栏实时出现 evidence；完成后切到稳定态
- 移动端尺寸（< 768px）确认切钮和右栏都不渲染
- 故意构造 LLM 不传 `evidence_refs` 的场景，确认候选池前 3 条兜底

## 13. 实施分步

1. **后端 schema + EvidencePool** — `evidence_pool.py` + `agent_response.py` 改造 + 迁移脚本
2. **工具钩子 + 候选池填充** — 4 个工具的 `_arun` 完成钩子加 `try/except pool.push`
3. **`respond` 工具改造** — schema 加 `evidence_refs`、description 动态注入、resolve → `EvidenceItem`
4. **SSE 事件** — `agent_service.py` yield `evidence` / `evidence_final`
5. **后端测试** — 单元 + 集成测试
6. **前端 TS 类型 + 组件** — `types.ts` + 5 个组件
7. **集成到 MessageBubble + ChatPage** — 三栏布局 + 状态管理 + 移动端判断
8. **前端测试**
9. **手工 E2E 验证** — 跑真实 meal_plan + mall_recommend 链路

## 14. 风险 & 决策记录

- **决策**：移动端不做证据链 → **理由**：避免范围蔓延；桌面端已经覆盖核心 demo 场景
- **决策**：debug 视图不做 → **理由**：证据字段后端已经存好 raw 数据，需要时通过 DB 查询即可
- **决策**：evidence 不可点击 → **理由**：摘要 + 来源标签足够回答"为什么"；增加详情会引入弹窗/抽屉复杂度
- **决策**：流式阶段 evidence 实时推、`evidence_final` 单独推 → **理由**：实时反馈给用户"AI 在工作"；最终一致性靠 `assistant_done` 覆盖
- **决策**：候选池不落库 → **理由**：候选池是中间态，最终 `EvidenceItem` 才入库；不增加复杂度
- **风险**：LLM 不遵守 `evidence_refs` schema 约束（传未知 ref_id）→ **缓解**：resolve 静默跳过，不抛错
- **风险**：前端流式累积的 evidence 在 `evidence_final` 后顺序错乱 → **缓解**：`evidence_final` 覆盖 `evidence_stream`，不合并
