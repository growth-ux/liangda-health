# Chat Evidence Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前聊天页的桌面端证据展示从固定 `EvidencePanel` 三栏改成中心 `EvidenceModal`，同时保留移动端消息内展开。

**Architecture:** 继续沿用 `ChatPage -> MessageList -> MessageBubble -> evidence/*` 这套前端边界，只替换证据状态模型、页面挂载点和样式实现，不改后端数据结构。桌面端用页面级 modal 渲染当前选中消息的证据，移动端继续复用消息内展开逻辑。

**Tech Stack:** React 19、TypeScript、Vite、TanStack Query、现有全局 `styles.css`

---

## File Structure

- Modify: `frontend/src/pages/ChatPage.tsx`
  - 去掉三栏布局和 `EvidencePanel` 挂载，改为页面级 `EvidenceModal` 挂载
  - 把证据状态从 `EvidencePanelState` 收口为 `EvidenceModalState`
- Modify: `frontend/src/components/chat/MessageList.tsx`
  - 类型改为新的 modal 状态类型
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
  - 保留移动端消息内展开逻辑，但状态类型改为 modal 状态
- Modify: `frontend/src/components/chat/evidence/EvidenceActions.tsx`
  - 导出 `EvidenceModalState`
  - 按桌面端/移动端统一驱动打开状态
- Create: `frontend/src/components/chat/evidence/EvidenceModal.tsx`
  - 中心弹窗组件，负责遮罩、关闭、组别标题和证据内容
- Delete: `frontend/src/components/chat/evidence/EvidencePanel.tsx`
  - 固定右栏组件不再使用
- Modify: `frontend/src/styles.css`
  - 去掉三栏布局和右栏样式
  - 新增 modal 遮罩、居中容器、关闭按钮、滚动区域样式
- Verify: `prd/prototype/evidence-chain-comparison.html`
  - 仅作为人工对照，不需要改实现代码，但开发时要按它核对视觉和交互

### Task 1: 收口页面状态和组件边界

**Files:**
- Modify: `frontend/src/components/chat/evidence/EvidenceActions.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: 先把证据状态类型改成 modal 语义**

```ts
export type EvidenceModalState =
  | {
      open: true;
      messageId: string;
      group: 'content' | 'product';
    }
  | {
      open: false;
      messageId: null;
      group: null;
    };
```

- [ ] **Step 2: 在 `EvidenceActions.tsx` 里用新状态替换旧状态**

```tsx
type Props = {
  message: AgentMessage;
  modalState: EvidenceModalState;
  onChange: (next: EvidenceModalState) => void;
  mobile?: boolean;
};

onClick={() =>
  onChange({
    open: true,
    messageId: message.message_id,
    group: 'content'
  })
}
```

- [ ] **Step 3: 在 `MessageList.tsx` 和 `MessageBubble.tsx` 中同步改 prop 名称**

```tsx
type Props = {
  modalState: EvidenceModalState;
  onModalChange: (next: EvidenceModalState) => void;
};

<MessageBubble
  key={message.message_id}
  message={message}
  modalState={modalState}
  onModalChange={onModalChange}
  mobileEvidenceMode={mobileEvidenceMode}
/>
```

- [ ] **Step 4: 在 `MessageBubble.tsx` 里保留移动端 inline 展开判断，但改成看 `open`**

```tsx
const isInlineEvidenceOpen =
  mobileEvidenceMode &&
  modalState.open &&
  modalState.messageId === message.message_id &&
  !!message.card?.evidence;
```

- [ ] **Step 5: 在 `ChatPage.tsx` 里把初始状态改成明确的关闭态**

```ts
const CLOSED_EVIDENCE_MODAL: EvidenceModalState = {
  open: false,
  messageId: null,
  group: null
};

const [modalState, setModalState] = useState<EvidenceModalState>(CLOSED_EVIDENCE_MODAL);
```

- [ ] **Step 6: 更新 `selectedEvidenceMessage` 的选择逻辑**

```ts
const selectedEvidenceMessage = useMemo(() => {
  if (!modalState.open) return null;
  return messages.find((item) => item.message_id === modalState.messageId) ?? null;
}, [messages, modalState]);
```

- [ ] **Step 7: 运行前端构建，确认纯类型改动没有引入报错**

Run: `npm --prefix frontend run build`  
Expected: `vite build` 成功结束，没有 `EvidencePanelState` 残留类型错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/chat/evidence/EvidenceActions.tsx frontend/src/components/chat/MessageList.tsx frontend/src/components/chat/MessageBubble.tsx frontend/src/pages/ChatPage.tsx
git commit -m "refactor: rename chat evidence state to modal"
```

### Task 2: 用中心弹窗替换固定右栏

**Files:**
- Create: `frontend/src/components/chat/evidence/EvidenceModal.tsx`
- Delete: `frontend/src/components/chat/evidence/EvidencePanel.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: 新建 `EvidenceModal.tsx`，定义最小可用弹窗**

```tsx
import type { AgentMessage } from '../../../api/agent';
import { EvidenceEmpty } from './EvidenceEmpty';
import { EvidenceSection } from './EvidenceSection';
import type { EvidenceModalState } from './EvidenceActions';

type Props = {
  message: AgentMessage | null;
  modalState: EvidenceModalState;
  onClose: () => void;
};
```

- [ ] **Step 2: 在 `EvidenceModal.tsx` 中实现关闭态直接不渲染**

```tsx
if (!modalState.open) {
  return null;
}
```

- [ ] **Step 3: 在 `EvidenceModal.tsx` 中实现内容选择和空态**

```tsx
const evidence = message?.card?.evidence;
const items =
  modalState.group === 'content'
    ? evidence?.content_items ?? []
    : evidence?.product_items ?? [];

const title = modalState.group === 'content' ? '本次生成依据' : '本次推荐依据';
```

- [ ] **Step 4: 写出弹窗主体 JSX，包括遮罩、关闭按钮和证据列表**

```tsx
return (
  <div className="chat-evidence-modal-backdrop" onClick={onClose}>
    <div className="chat-evidence-modal" onClick={(event) => event.stopPropagation()}>
      <div className="chat-evidence-modal-head">
        <div>
          <div className="chat-evidence-modal-title">证据链</div>
          <div className="chat-evidence-modal-subtitle">
            {modalState.group === 'content' ? '生成链' : '推荐链'}
          </div>
        </div>
        <button type="button" className="chat-evidence-modal-close" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="chat-evidence-modal-body">
        {items.length === 0 ? <EvidenceEmpty /> : <EvidenceSection title={title} items={items} />}
      </div>
    </div>
  </div>
);
```

- [ ] **Step 5: 在 `ChatPage.tsx` 里替换组件挂载**

```tsx
import { EvidenceModal } from '../components/chat/evidence/EvidenceModal';

<MessageList
  messages={messages}
  loading={messagesQuery.isLoading}
  overview={overviewQuery.data}
  overviewLoading={overviewQuery.isLoading}
  overviewError={overviewQuery.isError}
  modalState={modalState}
  onModalChange={setModalState}
  mobileEvidenceMode={isMobileViewport()}
/>
<EvidenceModal
  message={selectedEvidenceMessage}
  modalState={modalState}
  onClose={() => setModalState(CLOSED_EVIDENCE_MODAL)}
/>
```

- [ ] **Step 6: 删除 `EvidencePanel.tsx` 并移除相关 import**

```bash
rm frontend/src/components/chat/evidence/EvidencePanel.tsx
```

- [ ] **Step 7: 运行前端构建，确认组件替换无编译错误**

Run: `npm --prefix frontend run build`  
Expected: 构建通过，`Cannot find module './EvidencePanel'` 之类错误清零

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx frontend/src/components/chat/evidence/EvidenceModal.tsx frontend/src/components/chat/evidence
git commit -m "feat: replace fixed evidence panel with modal"
```

### Task 3: 清理三栏样式并补齐 modal 视觉

**Files:**
- Modify: `frontend/src/styles.css`
- Verify: `prd/prototype/evidence-chain-comparison.html`

- [ ] **Step 1: 去掉三栏布局依赖，让聊天页回到两栏**

```css
.chat-layout {
  display: flex;
  height: calc(100vh - 60px);
  margin: -28px -32px;
}

.chat-layout-with-evidence {
  display: flex;
}
```

- [ ] **Step 2: 删除固定右栏样式并新增 modal 样式**

```css
.chat-evidence-modal-backdrop {
  position: fixed;
  inset: 60px 0 0 0;
  background: rgba(15, 23, 42, 0.24);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 40;
}

.chat-evidence-modal {
  width: min(640px, calc(100vw - 48px));
  max-height: calc(100vh - 120px);
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
```

- [ ] **Step 3: 补齐 modal 头部、关闭按钮和滚动区域样式**

```css
.chat-evidence-modal-head {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.chat-evidence-modal-title {
  font-size: 15px;
  font-weight: 600;
}

.chat-evidence-modal-subtitle {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.chat-evidence-modal-close {
  width: 28px;
  height: 28px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #ffffff;
  cursor: pointer;
}

.chat-evidence-modal-body {
  padding: 16px;
  overflow-y: auto;
}
```

- [ ] **Step 4: 保留移动端消息内展开样式，不再隐藏不存在的右栏**

```css
@media (max-width: 767px) {
  .chat-layout-with-evidence {
    display: block;
  }

  .chat-evidence-modal-backdrop {
    display: none;
  }

  .evidence-actions-row.mobile {
    flex-wrap: wrap;
  }
}
```

- [ ] **Step 5: 跑构建，确认 CSS 和 TS 一起通过**

Run: `npm --prefix frontend run build`  
Expected: 构建通过，CSS 中不再依赖 `.chat-evidence-panel`

- [ ] **Step 6: 启动本地前端并人工核对桌面端 modal、移动端 inline**

Run: `npm --prefix frontend run dev -- --host 0.0.0.0`  
Expected: Vite 输出本地访问地址，例如 `http://127.0.0.1:5173/`

- [ ] **Step 7: 对照原型完成人工验收**

Run: 打开 `http://127.0.0.1:5173/`，手工验证以下行为  
Expected:
- 桌面端点击 `生成依据` 出现中心弹窗
- 点击 `推荐依据` 展示推荐链
- 点击遮罩或关闭按钮可以关闭
- 关闭后聊天滚动位置不丢
- 移动端宽度下不出现 modal，只在消息内展开证据

- [ ] **Step 8: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style: update chat evidence presentation to modal"
```

### Task 4: 最终回归和交付检查

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/components/chat/evidence/EvidenceModal.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 搜索并清理遗留的 `EvidencePanel` / `EvidencePanelState` / 三栏类名**

Run: `rg -n "EvidencePanel|EvidencePanelState|chat-evidence-panel|grid-template-columns: 240px minmax\\(0, 1fr\\) 320px" frontend/src -S`  
Expected: 无结果

- [ ] **Step 2: 最终构建校验**

Run: `npm --prefix frontend run build`  
Expected: `tsc -b && vite build` 全量通过

- [ ] **Step 3: 最终 git 检查**

Run: `git status --short`  
Expected: 只包含这次 modal 改造相关文件，没有误改其它模块

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx frontend/src/components/chat frontend/src/styles.css
git commit -m "feat: switch chat evidence UX to centered modal"
```
