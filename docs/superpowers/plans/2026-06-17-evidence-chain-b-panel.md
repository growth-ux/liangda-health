# Agent 证据链 B 方案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给聊天页接入桌面端三栏证据链面板，让用户可以从 assistant 回复进入“生成链 / 推荐链”，并在后端把真实工具证据写入 `card.evidence`。

**Architecture:** 先做前端三栏和消息级证据交互，占位读取 `message.card.evidence`；再做后端最小证据聚合，不新增表、不新增 SSE 事件，只在本次 agent 运行结束时把 `report_fact / memory / product` 两组证据写进 `card` JSON；移动端不渲染右栏，退化为消息内展开。

**Tech Stack:** React 19 + Vite + TypeScript + Tailwind（已有）、FastAPI + SQLAlchemy + LangChain + Pydantic（已有）、`python -m pytest`、`npm run build`

---

## File Map

### Frontend

- Modify: `frontend/src/schemas/agentResponse.ts`
  - 给 `StructuredCard` 增加顶层 `evidence`
- Modify: `frontend/src/api/agent.ts`
  - 给 `AgentMessage` 补可选证据结构
- Modify: `frontend/src/pages/ChatPage.tsx`
  - 三栏布局、右侧 `EvidencePanel` 状态提升
- Modify: `frontend/src/components/chat/MessageList.tsx`
  - 透传证据交互状态给消息项
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
  - assistant 消息下挂 `EvidenceActions`
- Create: `frontend/src/components/chat/evidence/EvidencePanel.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceEmpty.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceSection.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceItemCard.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceActions.tsx`
- Modify: `frontend/src/styles.css`
  - 三栏布局、右栏、移动端退化样式

### Backend

- Modify: `backend/app/schemas/agent_response.py`
  - 证据 schema 与 `StructuredResponse` 扩展
- Modify: `backend/app/services/agent_tools.py`
  - 4 个工具支持可选 evidence sink
- Modify: `backend/app/services/langchain_agent.py`
  - `run/stream` 装配 evidence sink，结束时把 evidence 写入 `card`
- Modify: `backend/app/services/agent_service.py`
  - 透传带 evidence 的 `card`
- Modify: `backend/app/api/agent.py`
  - 工具依赖装配保持兼容
- Create: `backend/app/services/agent_evidence.py`
  - 最小证据收集器
- Test: `backend/tests/test_agent_response_schema.py`
- Test: `backend/tests/test_langchain_agent.py`
- Test: `backend/tests/test_agent_service.py`
- Test: `backend/tests/test_agent_tools.py`

### Verification

- Frontend 无单测框架，验证以 `cd frontend && npm run build` 为准
- Backend 以 `cd backend && python -m pytest ...` 为准

---

## Task 1: 扩展前后端证据类型定义

**Files:**
- Modify: `frontend/src/schemas/agentResponse.ts`
- Modify: `frontend/src/api/agent.ts`
- Modify: `backend/app/schemas/agent_response.py`
- Test: `backend/tests/test_agent_response_schema.py`

- [ ] **Step 1: 写失败测试，验证 `StructuredResponse` 支持顶层 evidence**

在 `backend/tests/test_agent_response_schema.py` 末尾追加：

```python
def test_structured_response_accepts_top_level_evidence():
    payload = {
        "kind": "qa",
        "summary_text": "建议清淡一点。",
        "payload": {
            "question_topic": "晚餐",
            "answer": "清淡、少油、少盐。",
            "tips": [],
        },
        "evidence": {
            "content_items": [
                {
                    "type": "report_fact",
                    "title": "体检提示血压偏高",
                    "excerpt": "5 月体检报告提示收缩压偏高。",
                    "source_id": "fact_1",
                    "source_label": "5 月体检报告 p3",
                }
            ],
            "product_items": [
                {
                    "type": "product",
                    "title": "低钠酱油匹配控盐方向",
                    "excerpt": "商品标签命中 low_sodium。",
                    "source_id": "prod_1",
                    "source_label": "商城标签匹配",
                }
            ],
        },
    }

    response = StructuredResponse.model_validate(payload)

    assert response.evidence.content_items[0].type == "report_fact"
    assert response.evidence.product_items[0].source_label == "商城标签匹配"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd backend && python -m pytest tests/test_agent_response_schema.py -v -k "top_level_evidence"
```

Expected: FAIL，报 `StructuredResponse` 不接受 `evidence`

- [ ] **Step 3: 扩展后端 schema**

修改 `backend/app/schemas/agent_response.py`：

```python
EvidenceType = Literal["report_fact", "memory", "product"]


class EvidenceItem(BaseModel):
    type: EvidenceType
    title: str = Field(..., min_length=1, max_length=80)
    excerpt: str = Field(..., min_length=1, max_length=200)
    source_id: str = Field(..., min_length=1, max_length=80)
    source_label: str = Field(..., min_length=1, max_length=120)


class MessageEvidence(BaseModel):
    content_items: list[EvidenceItem] = Field(default_factory=list)
    product_items: list[EvidenceItem] = Field(default_factory=list)


class StructuredResponse(BaseModel):
    kind: ResponseKind
    summary_text: str = Field(..., min_length=1, max_length=400)
    payload: (
        MealPlanPayload
        | QaPayload
        | GreetingPayload
        | KbInterpretationPayload
        | GeneralAdvicePayload
    )
    evidence: MessageEvidence | None = None
```

同时把旧的 `KbInterpretationPayload.evidence` 改成复用新的 `EvidenceItem` 字段结构：

```python
class KbInterpretationPayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    evidence: list[EvidenceItem] = Field(..., min_length=1)
    suggestions: list[SuggestionItem] = Field(..., min_length=1)
    red_flags: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: 同步前端类型**

修改 `frontend/src/schemas/agentResponse.ts`：

```ts
export type EvidenceType = 'report_fact' | 'memory' | 'product';

export interface EvidenceItem {
  type: EvidenceType;
  title: string;
  excerpt: string;
  source_id: string;
  source_label: string;
}

export interface MessageEvidence {
  content_items: EvidenceItem[];
  product_items: EvidenceItem[];
}

export interface StructuredResponse<K extends ResponseKind = ResponseKind> {
  kind: K;
  summary_text: string;
  payload: K extends 'meal_plan' ? MealPlanPayload
    : K extends 'qa' ? QaPayload
    : K extends 'greeting' ? GreetingPayload
    : K extends 'kb_interpretation' ? KbInterpretationPayload
    : GeneralAdvicePayload;
  evidence?: MessageEvidence | null;
}
```

并修改 `frontend/src/api/agent.ts`：

```ts
import type { MessageEvidence, StructuredCard } from '../schemas/agentResponse';

export type AgentMessage = {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  status: 'done' | 'failed' | 'sending';
  created_at: string;
  attachments?: Attachment[];
  product_recommendations?: ProductRecommendationItem[];
  card?: StructuredCard & { evidence?: MessageEvidence | null };
};
```

- [ ] **Step 5: 跑 schema 测试**

Run:

```bash
cd backend && python -m pytest tests/test_agent_response_schema.py -v
```

Expected: PASS

- [ ] **Step 6: 前端类型编译**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/agent_response.py backend/tests/test_agent_response_schema.py frontend/src/schemas/agentResponse.ts frontend/src/api/agent.ts
git commit -m "feat(agent): add evidence schema for chat cards"
```

---

## Task 2: 先做右侧证据面板和消息入口组件

**Files:**
- Create: `frontend/src/components/chat/evidence/EvidencePanel.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceEmpty.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceSection.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceItemCard.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceActions.tsx`
- Modify: `frontend/src/api/agent.ts`

- [ ] **Step 1: 创建空状态组件**

Create `frontend/src/components/chat/evidence/EvidenceEmpty.tsx`：

```tsx
export function EvidenceEmpty() {
  return (
    <div className="evidence-empty">
      <div className="evidence-empty-title">证据链</div>
      <div className="evidence-empty-text">
        点聊天里的“生成依据”或“推荐依据”，查看这次回复参考了哪些真实依据。
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 创建单条 evidence 卡片**

Create `frontend/src/components/chat/evidence/EvidenceItemCard.tsx`：

```tsx
import type { EvidenceItem } from '../../../schemas/agentResponse';

type Props = {
  item: EvidenceItem;
};

export function EvidenceItemCard({ item }: Props) {
  return (
    <article className="evidence-item-card">
      <div className="evidence-item-type">{item.type}</div>
      <div className="evidence-item-title">{item.title}</div>
      <div className="evidence-item-excerpt">{item.excerpt}</div>
      <div className="evidence-item-source">{item.source_label}</div>
    </article>
  );
}
```

- [ ] **Step 3: 创建分组组件**

Create `frontend/src/components/chat/evidence/EvidenceSection.tsx`：

```tsx
import type { EvidenceItem } from '../../../schemas/agentResponse';
import { EvidenceItemCard } from './EvidenceItemCard';

type Props = {
  title: string;
  items: EvidenceItem[];
};

export function EvidenceSection({ title, items }: Props) {
  if (items.length === 0) return null;

  return (
    <section className="evidence-section">
      <div className="evidence-section-title">{title}</div>
      <div className="evidence-section-list">
        {items.map((item, index) => (
          <EvidenceItemCard key={`${item.source_id}-${index}`} item={item} />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: 创建消息下入口组件**

Create `frontend/src/components/chat/evidence/EvidenceActions.tsx`：

```tsx
import type { AgentMessage } from '../../../api/agent';

export type EvidencePanelState =
  | {
      messageId: string;
      group: 'content' | 'product';
    }
  | null;

type Props = {
  message: AgentMessage;
  panelState: EvidencePanelState;
  onChange: (next: EvidencePanelState) => void;
  mobile?: boolean;
};

export function EvidenceActions({ message, panelState, onChange, mobile = false }: Props) {
  const evidence = message.card?.evidence;
  const hasContent = (evidence?.content_items?.length ?? 0) > 0;
  const hasProduct = (evidence?.product_items?.length ?? 0) > 0;

  if (!hasContent && !hasProduct) return null;

  return (
    <div className={`evidence-actions-row${mobile ? ' mobile' : ''}`}>
      {hasContent && (
        <button
          type="button"
          className={panelState?.messageId === message.message_id && panelState.group === 'content' ? 'active' : ''}
          onClick={() => onChange({ messageId: message.message_id, group: 'content' })}
        >
          生成依据
        </button>
      )}
      {hasProduct && (
        <button
          type="button"
          className={panelState?.messageId === message.message_id && panelState.group === 'product' ? 'active' : ''}
          onClick={() => onChange({ messageId: message.message_id, group: 'product' })}
        >
          推荐依据
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 创建右栏组件**

Create `frontend/src/components/chat/evidence/EvidencePanel.tsx`：

```tsx
import type { AgentMessage } from '../../../api/agent';
import { EvidenceEmpty } from './EvidenceEmpty';
import { EvidenceSection } from './EvidenceSection';
import type { EvidencePanelState } from './EvidenceActions';

type Props = {
  message: AgentMessage | null;
  panelState: EvidencePanelState;
};

export function EvidencePanel({ message, panelState }: Props) {
  if (!message || !panelState || !message.card?.evidence) {
    return <EvidenceEmpty />;
  }

  const evidence = message.card.evidence;
  const items = panelState.group === 'content' ? evidence.content_items : evidence.product_items;

  if (items.length === 0) {
    return <EvidenceEmpty />;
  }

  return (
    <aside className="chat-evidence-panel">
      <div className="chat-evidence-panel-head">
        <div className="chat-evidence-panel-title">证据链</div>
        <div className="chat-evidence-panel-subtitle">
          {panelState.group === 'content' ? '生成链' : '推荐链'}
        </div>
      </div>
      <div className="chat-evidence-panel-body">
        <EvidenceSection
          title={panelState.group === 'content' ? '本次生成依据' : '本次推荐依据'}
          items={items}
        />
      </div>
    </aside>
  );
}
```

- [ ] **Step 6: 编译检查**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/chat/evidence frontend/src/api/agent.ts
git commit -m "feat(chat): add evidence panel components"
```

---

## Task 3: 接聊天页三栏布局和移动端退化

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 给 `MessageList` 增加证据交互透传**

修改 `frontend/src/components/chat/MessageList.tsx`：

```tsx
import type { EvidencePanelState } from './evidence/EvidenceActions';

type Props = {
  messages: AgentMessage[];
  loading: boolean;
  overview?: HealthAnalysisOverview | null;
  overviewLoading?: boolean;
  overviewError?: boolean;
  panelState: EvidencePanelState;
  onPanelChange: (next: EvidencePanelState) => void;
  mobileEvidenceMode?: boolean;
};

// ...

{messages.map((message) => (
  <MessageBubble
    key={message.message_id}
    message={message}
    panelState={panelState}
    onPanelChange={onPanelChange}
    mobileEvidenceMode={mobileEvidenceMode}
  />
))}
```

- [ ] **Step 2: 在消息项里接 evidence actions**

修改 `frontend/src/components/chat/MessageBubble.tsx`：

```tsx
import { EvidenceActions, type EvidencePanelState } from './evidence/EvidenceActions';

type Props = {
  message: AgentMessage;
  panelState: EvidencePanelState;
  onPanelChange: (next: EvidencePanelState) => void;
  mobileEvidenceMode?: boolean;
};

export function MessageBubble({ message, panelState, onPanelChange, mobileEvidenceMode = false }: Props) {
  // ...
  const isAssistant = message.role === 'assistant';

  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      {/* 现有 bubble */}
      <div className="msg-wrap">
        <div className="msg-bubble">
          {/* 原有 content / product / card */}
        </div>

        {isAssistant && (
          <EvidenceActions
            message={message}
            panelState={panelState}
            onChange={onPanelChange}
            mobile={mobileEvidenceMode}
          />
        )}
        <div className="msg-time">{message.status === 'failed' ? '发送失败' : time}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 在聊天页提升 `panelState` 并引入右栏**

修改 `frontend/src/pages/ChatPage.tsx`：

```tsx
import { EvidencePanel } from '../components/chat/evidence/EvidencePanel';
import type { EvidencePanelState } from '../components/chat/evidence/EvidenceActions';

// state
const [panelState, setPanelState] = useState<EvidencePanelState>(null);

const selectedEvidenceMessage = useMemo(() => {
  if (!panelState) return null;
  return messages.find((item) => item.message_id === panelState.messageId) ?? null;
}, [messages, panelState]);

// layout
<div className="chat-layout chat-layout-with-evidence">
  <SessionList ... />
  <section className="chat-main">
    {/* header + MessageList + ChatInput */}
    <MessageList
      messages={messages}
      loading={messagesQuery.isLoading}
      overview={overviewQuery.data}
      overviewLoading={overviewQuery.isLoading}
      overviewError={overviewQuery.isError}
      panelState={panelState}
      onPanelChange={setPanelState}
      mobileEvidenceMode={false}
    />
    <ChatInput ... />
  </section>
  <EvidencePanel message={selectedEvidenceMessage} panelState={panelState} />
</div>
```

- [ ] **Step 4: 增加移动端退化**

在 `frontend/src/pages/ChatPage.tsx` 的 `MessageList` 处传移动端模式：

```tsx
<MessageList
  // ...
  mobileEvidenceMode={window.innerWidth < 768}
/>
```

并在样式中隐藏右栏：

```css
@media (max-width: 767px) {
  .chat-layout-with-evidence {
    display: block;
  }

  .chat-evidence-panel {
    display: none;
  }
}
```

- [ ] **Step 5: 补样式**

在 `frontend/src/styles.css` 追加：

```css
.chat-layout-with-evidence {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 320px;
}

.chat-evidence-panel {
  background: #ffffff;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-evidence-panel-head {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.chat-evidence-panel-title {
  font-size: 15px;
  font-weight: 600;
}

.chat-evidence-panel-subtitle {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.chat-evidence-panel-body {
  padding: 16px;
  overflow-y: auto;
}

.evidence-actions-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.evidence-actions-row button {
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #4b5563;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.evidence-actions-row button.active {
  background: #ecfdf5;
  border-color: #10b981;
  color: #047857;
}

.evidence-empty {
  padding: 20px 16px;
}

.evidence-empty-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
}

.evidence-empty-text,
.evidence-item-excerpt,
.evidence-item-source {
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
}

.evidence-item-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #ffffff;
}

.evidence-item-card + .evidence-item-card {
  margin-top: 8px;
}

.evidence-item-type {
  font-size: 11px;
  color: #10b981;
  font-weight: 600;
  margin-bottom: 4px;
}

.evidence-item-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #111827;
}
```

- [ ] **Step 6: 前端构建验证**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/pages/ChatPage.tsx frontend/src/components/chat/MessageList.tsx frontend/src/components/chat/MessageBubble.tsx frontend/src/styles.css
git commit -m "feat(chat): add three-column evidence layout"
```

---

## Task 4: 后端增加最小证据收集器

**Files:**
- Create: `backend/app/services/agent_evidence.py`
- Modify: `backend/app/services/agent_tools.py`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试，验证工具支持 evidence sink**

在 `backend/tests/test_agent_tools.py` 末尾追加：

```python
def test_memory_search_tool_pushes_evidence_item():
    from app.services.agent_evidence import AgentEvidenceCollector
    from app.services.agent_tools import MemorySearchTool

    class FakeMemoryService:
        def search_text(self, query, member_id=None, limit=5):
            return "[avoidance] 爸爸不喜欢鱼"

    collector = AgentEvidenceCollector()
    tool = MemorySearchTool(FakeMemoryService(), evidence_collector=collector)

    tool.search(query="爸爸 饮食 排斥", member_id="mem_dad")

    assert collector.content_items[0].type == "memory"
    assert collector.content_items[0].source_label == "互动记忆"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd backend && python -m pytest tests/test_agent_tools.py -v -k "pushes_evidence_item"
```

Expected: FAIL，报 `MemorySearchTool` 不支持 `evidence_collector`

- [ ] **Step 3: 创建最小收集器**

Create `backend/app/services/agent_evidence.py`：

```python
from __future__ import annotations

from app.schemas.agent_response import EvidenceItem, MessageEvidence


class AgentEvidenceCollector:
    def __init__(self) -> None:
        self.content_items: list[EvidenceItem] = []
        self.product_items: list[EvidenceItem] = []

    def add_content(self, item: EvidenceItem) -> None:
        self.content_items.append(item)

    def add_product(self, item: EvidenceItem) -> None:
        self.product_items.append(item)

    def dump(self) -> MessageEvidence | None:
        if not self.content_items and not self.product_items:
            return None
        return MessageEvidence(
            content_items=self.content_items,
            product_items=self.product_items,
        )
```

- [ ] **Step 4: 修改工具接入收集器**

修改 `backend/app/services/agent_tools.py`：

```python
from app.schemas.agent_response import EvidenceItem

class MemorySearchTool:
    def __init__(self, service, evidence_collector=None):
        self.service = service
        self.evidence_collector = evidence_collector

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        # 现有逻辑...
        result = self.service.search_text(query=query, member_id=member_id, limit=limit)
        if self.evidence_collector is not None:
            self.evidence_collector.add_content(
                EvidenceItem(
                    type="memory",
                    title=f"关于「{query}」的互动记忆",
                    excerpt=str(result)[:200],
                    source_id=f"memory:{member_id or 'family'}:{query}",
                    source_label="互动记忆",
                )
            )
        return result
```

同样给 `KbSearchTool` 增加：

```python
if self.evidence_collector is not None and chunks:
    first_chunk = chunks[0]
    document = self.repository.get_document(first_chunk.document_id)
    self.evidence_collector.add_content(
        EvidenceItem(
            type="report_fact",
            title=document.title or document.file_name if document is not None else first_chunk.document_id,
            excerpt=first_chunk.content[:200],
            source_id=first_chunk.chunk_id,
            source_label=f"{document.title or document.file_name} p{first_chunk.page_no}" if document else first_chunk.document_id,
        )
    )
```

以及 `MallRecommendTool`：

```python
class MallRecommendTool:
    def __init__(self, service, allowed_member_ids: list[str], evidence_collector=None):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)
        self.evidence_collector = evidence_collector

    def recommend(...):
        result = self.service.recommend(...)
        if self.evidence_collector is not None:
            for item in result.get("items") or []:
                self.evidence_collector.add_product(
                    EvidenceItem(
                        type="product",
                        title=item["name"],
                        excerpt=item.get("reason", "")[:200],
                        source_id=item["product_id"],
                        source_label="商城标签匹配",
                    )
                )
        payload = json.dumps(result, ensure_ascii=False)
        return payload
```

- [ ] **Step 5: 跑工具测试**

Run:

```bash
cd backend && python -m pytest tests/test_agent_tools.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/agent_evidence.py backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat(agent): collect evidence from tool outputs"
```

---

## Task 5: 把 evidence 写进 `card` 并透传到前端

**Files:**
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/app/api/agent.py`
- Test: `backend/tests/test_langchain_agent.py`
- Test: `backend/tests/test_agent_service.py`

- [ ] **Step 1: 写失败测试，验证 `runner.stream()` 产出的 card 带 evidence**

在 `backend/tests/test_langchain_agent.py` 末尾追加：

```python
def test_langchain_agent_stream_attaches_collected_evidence_to_card(monkeypatch):
    from app.schemas.agent_response import MessageEvidence
    from langchain_core.messages import ToolMessage

    class FakeKbTool:
        def __init__(self):
            self.evidence_collector = None

        def search(self, query, member_id=None, top_k=5):
            if self.evidence_collector is not None:
                from app.schemas.agent_response import EvidenceItem
                self.evidence_collector.add_content(
                    EvidenceItem(
                        type="report_fact",
                        title="体检报告",
                        excerpt="血压偏高",
                        source_id="chunk_1",
                        source_label="体检报告 p3",
                    )
                )
            return "ok"

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield ToolMessage(
                content='{"kind":"qa","summary_text":"你好","payload":{"question_topic":"x","answer":"y","tips":[]}}',
                tool_call_id="call_1",
                name="respond",
            ), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner(kb_tool=FakeKbTool())
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "x"}]))
    card_payloads = [payload for kind, payload in events if kind == "card"]

    assert card_payloads[0]["evidence"]["content_items"][0]["type"] == "report_fact"
```

- [ ] **Step 2: 跑测试确认失败**

Run:

```bash
cd backend && python -m pytest tests/test_langchain_agent.py -v -k "attaches_collected_evidence"
```

Expected: FAIL，`card` 里没有 `evidence`

- [ ] **Step 3: 在 runner 里装配 evidence collector**

修改 `backend/app/services/langchain_agent.py`：

```python
from app.services.agent_evidence import AgentEvidenceCollector

def _attach_evidence_collector(self):
    collector = AgentEvidenceCollector()
    for tool in (self.kb_tool, self.memory_tool, self.mall_recommend_tool):
        if tool is not None:
            tool.evidence_collector = collector
    return collector
```

在 `run()` 和 `stream()` 入口调用：

```python
collector = self._attach_evidence_collector()
```

在解析出 `card` 后挂上 evidence：

```python
evidence = collector.dump()
if evidence is not None:
    card["evidence"] = evidence.model_dump()
```

- [ ] **Step 4: 让 service 原样透传**

修改 `backend/app/services/agent_service.py`，不改事件名，只确保 `card_dict` 原样带 evidence 落库并透传：

```python
elif event_type == "card":
    if isinstance(payload, dict):
        card_dict = payload
        yield self._event("card", {"message_id": assistant_id, "card": payload})
```

并在 `assistant_done` 中继续回填：

```python
yield self._event(
    "assistant_done",
    {
        "message_id": assistant_message.message_id,
        "session_id": assistant_message.session_id,
        "role": assistant_message.role,
        "content": assistant_message.content,
        "product_recommendations": product_recs_items,
        "card": card_dict,
    },
)
```

- [ ] **Step 5: 写 service 透传测试**

在 `backend/tests/test_agent_service.py` 追加：

```python
def test_agent_service_stream_message_emits_card_with_evidence(db_session):
    card_dict = {
        "kind": "qa",
        "summary_text": "你好",
        "payload": {"question_topic": "x", "answer": "y", "tips": []},
        "evidence": {
            "content_items": [
                {
                    "type": "memory",
                    "title": "互动记忆",
                    "excerpt": "爸爸不喜欢鱼",
                    "source_id": "memory:1",
                    "source_label": "互动记忆",
                }
            ],
            "product_items": [],
        },
    }

    class FakeRunner:
        def stream(self, messages):
            yield ("delta", "先回")
            yield ("card", card_dict)

    service = AgentService(SqlAlchemyAgentRepository(db_session), FakeRunner())
    session = service.create_session("新对话")

    events = "".join(service.stream_message(session.session_id, "x"))

    assert '"evidence"' in events
    assert '"title": "互动记忆"' in events
```

- [ ] **Step 6: 跑后端测试**

Run:

```bash
cd backend && python -m pytest tests/test_langchain_agent.py tests/test_agent_service.py tests/test_agent_tools.py -v
```

Expected: PASS

- [ ] **Step 7: 全量验证**

Run:

```bash
cd backend && python -m pytest tests/test_agent_response_schema.py tests/test_langchain_agent.py tests/test_agent_service.py tests/test_agent_tools.py -v
cd ../frontend && npm run build
```

Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add backend/app/services/langchain_agent.py backend/app/services/agent_service.py backend/app/api/agent.py backend/tests/test_langchain_agent.py backend/tests/test_agent_service.py
git commit -m "feat(agent): attach evidence to assistant cards"
```

---

## Task 6: 把移动端消息内展开补齐

**Files:**
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/evidence/EvidenceActions.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 给移动端增加内联 evidence 区**

修改 `frontend/src/components/chat/MessageBubble.tsx`：

```tsx
import { EvidenceSection } from './evidence/EvidenceSection';

const isInlineEvidenceOpen = mobileEvidenceMode
  && panelState?.messageId === message.message_id
  && !!message.card?.evidence;

// 在 EvidenceActions 后追加
{isInlineEvidenceOpen && (
  <div className="msg-inline-evidence">
    {panelState?.group === 'content' && (
      <EvidenceSection title="本次生成依据" items={message.card?.evidence?.content_items ?? []} />
    )}
    {panelState?.group === 'product' && (
      <EvidenceSection title="本次推荐依据" items={message.card?.evidence?.product_items ?? []} />
    )}
  </div>
)}
```

- [ ] **Step 2: 给移动端入口加类名**

修改 `frontend/src/components/chat/evidence/EvidenceActions.tsx`：

```tsx
return (
  <div className={`evidence-actions-row${mobile ? ' mobile' : ''}`}>
    {/* buttons */}
  </div>
);
```

- [ ] **Step 3: 补移动端样式**

在 `frontend/src/styles.css` 追加：

```css
.msg-inline-evidence {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

@media (max-width: 767px) {
  .evidence-actions-row.mobile {
    flex-wrap: wrap;
  }

  .msg-inline-evidence .evidence-item-card {
    background: #f9fafb;
  }
}
```

- [ ] **Step 4: 前端构建验证**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/chat/MessageBubble.tsx frontend/src/components/chat/evidence/EvidenceActions.tsx frontend/src/styles.css
git commit -m "feat(chat): add mobile inline evidence fallback"
```

---

## Self-Review

- Spec coverage:
  - 三栏布局：Task 3
  - 右栏跟随当前消息：Task 2 + Task 3
  - `report_fact / memory / product`：Task 1 + Task 4 + Task 5
  - 移动端消息内展开：Task 6
  - 不新增表 / 不新增 SSE：Task 5 明确保持原事件链
- Placeholder scan:
  - 无 `TODO/TBD`
  - 每个测试步骤都带具体命令
- Type consistency:
  - `MessageEvidence` / `EvidenceItem` / `EvidencePanelState` 在前后任务命名一致

