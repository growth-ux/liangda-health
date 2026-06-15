# P0 产品定位统一实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/liangda-health-iteration-roadmap.md` 的 P0，只把项目主定位统一为“家庭健康智能营销 Agent”，不改现有功能模块命名和边界。

**Architecture:** 本次只做最小文案统一：README、浏览器标题、Agent 页面入口、Agent prompt 和快捷问题。保留“知识库”“上传报告”“商城”“健康分析”等现有页面和模块表达，因为这些是当前系统真实能力，不需要为了定位升级而整体改名。

**Tech Stack:** React 19、TypeScript、Vite、FastAPI、LangChain Agent、pytest、npm build。

---

## Scope

对应 roadmap：

```text
P0：统一定位和页面文案
目标：
- 将项目主线统一为“家庭健康智能营销 Agent”
- 避免页面和文档继续强化“报告问答工具”的单一印象
```

本次执行原则：

- 保留现有模块名：`知识库`、`上传报告`、`健康分析`、`商城` 都不强行改名。
- 只改主定位和 Agent 主入口，让用户知道系统不是单纯报告问答。
- 不新增数据库表。
- 不新增 mem0。
- 不改 Agent 工具编排。
- 不改商品推荐逻辑。
- 不做 UI 重设计。

## Files

- Modify: `README.md`
  - 补充项目定位和 demo 主线。
- Modify: `frontend/index.html`
  - 浏览器标题从“报告知识库”调整为产品总定位。
- Modify: `frontend/src/pages/ChatPage.tsx`
  - Agent 页面标题和状态文案体现“报告 + 画像 + 餐单 + 推荐”主线。
- Modify: `frontend/src/components/chat/ChatInput.tsx`
  - 输入框 placeholder 覆盖饮食、报告依据和商品推荐。
- Modify: `backend/app/services/langchain_agent.py`
  - system prompt 从“单纯一日三餐膳食推荐 Agent”调整为“家庭健康智能营销 Agent”，但保留现有 `meal_plan`、`kb_search` 工具边界。
- Modify: `backend/tests/test_langchain_agent.py`
  - 更新 prompt 定位断言。
- Modify: `backend/app/api/agent.py`
  - 快捷问题调整为 4 个，覆盖餐单、生活习惯建议和商品推荐。

---

### Task 1: README 写清项目主定位

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 替换 README 内容**

将 `README.md` 内容从：

```markdown
# liangda-health
```

替换为：

```markdown
# 粮达健康

粮达健康当前定位为：基于健康报告理解、家庭健康画像、手环近期状态和 Agent 对话的家庭健康智能营销系统。

当前 demo 主线：

1. 上传健康报告，解析并保留报告依据。
2. 建立家庭成员档案和健康画像。
3. 结合手环近期状态生成饮食建议。
4. 通过 Agent 生成餐单，并自然转化为健康商品推荐。
5. 在商品和 Agent 回复中展示推荐理由。

当前阶段只统一产品定位和关键入口文案；健康事实库、记忆系统、工具路由和推荐证据链按 `docs/liangda-health-iteration-roadmap.md` 后续 P1-P6 迭代。
```

- [ ] **Step 2: 检查 README**

Run:

```bash
sed -n '1,120p' README.md
```

Expected: 能看到“家庭健康智能营销系统”和 demo 主线。

---

### Task 2: 浏览器标题改成产品总定位

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 修改标题**

将：

```html
<title>粮达健康 · 报告知识库</title>
```

改为：

```html
<title>粮达健康 · 家庭健康智能营销 Agent</title>
```

- [ ] **Step 2: 前端构建验证**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS。

---

### Task 3: Agent 聊天入口表达主线

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/components/chat/ChatInput.tsx`

- [ ] **Step 1: 修改 Chat 页面标题和状态**

在 `frontend/src/pages/ChatPage.tsx` 中，将：

```tsx
<AppShell title="与管家对话" activeId="chat">
```

改为：

```tsx
<AppShell title="家庭健康 Agent" activeId="chat">
```

将：

```tsx
<div className="chat-agent-status">在线 · 已连接家庭健康档案</div>
```

改为：

```tsx
<div className="chat-agent-status">在线 · 已连接家庭健康档案、报告和商城推荐</div>
```

说明：`Agent 管家` 名称保留，不改成长文案，避免界面显得重。

- [ ] **Step 2: 修改输入框提示**

在 `frontend/src/components/chat/ChatInput.tsx` 中，将：

```tsx
placeholder="问问管家..."
```

改为：

```tsx
placeholder="问饮食、报告依据或适合家人的商品..."
```

- [ ] **Step 3: 前端构建验证**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS。

---

### Task 4: Agent prompt 从膳食单点升级为营销主线

**Files:**
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: 先改测试**

在 `backend/tests/test_langchain_agent.py` 中，将：

```python
assert "一日三餐膳食推荐 Agent" in prompt
```

改为：

```python
assert "家庭健康智能营销 Agent" in prompt
assert "餐单建议" in prompt
assert "商品推荐" in prompt
```

- [ ] **Step 2: 修改 prompt 开头，不改工具规则**

在 `backend/app/services/langchain_agent.py` 中，只替换 `SYSTEM_PROMPT_TEMPLATE` 的前两行：

```python
SYSTEM_PROMPT_TEMPLATE = """你是粮达健康的一日三餐膳食推荐 Agent。
你的首要任务是根据家人的健康状态、过敏忌口、年龄、BMI 和最近手环状态，给出早餐、午餐、晚餐建议。
```

替换为：

```python
SYSTEM_PROMPT_TEMPLATE = """你是粮达健康的家庭健康智能营销 Agent。
你的任务是结合家人的健康档案、报告依据和近期状态，生成餐单建议，并在合适时提示可选的健康商品方向。
```

其他规则保持不变，尤其保留：

```text
推荐餐单时必须调用 meal_plan 工具
只有用户明确要求基于报告、体检结果、某份报告时，才调用 kb_search 工具
```

- [ ] **Step 3: 后端测试验证**

Run:

```bash
cd backend
pytest tests/test_langchain_agent.py -q
```

Expected: PASS。

---

### Task 5: 快捷问题调整为 4 个主题问法

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 替换 4 个快捷问题**

在 `backend/app/api/agent.py` 的 `list_quick_actions()` 中，将返回值从：

```python
return [
    QuickActionItem(label="给全家安排今天一日三餐", action="meal_plan_family_day"),
    QuickActionItem(label="妈妈高血压今天怎么吃", action="meal_plan_hypertension"),
    QuickActionItem(label="爸爸控糖早餐吃什么", action="meal_plan_diabetes_breakfast"),
    QuickActionItem(label="今晚做什么适合全家", action="meal_plan_family_dinner"),
]
```

替换为：

```python
return [
    QuickActionItem(label="给全家安排今天一日三餐", action="meal_plan_family_day"),
    QuickActionItem(label="给爸爸出点生活习惯建议", action="father_lifestyle_advice"),
    QuickActionItem(label="推荐一款适合全家人的油", action="family_oil_recommendation"),
    QuickActionItem(label="今晚做什么适合全家", action="meal_plan_family_dinner"),
]
```

这 4 个问题分别覆盖：

- 全家一日三餐。
- 爸爸生活习惯建议。
- 适合全家的商品推荐。
- 全家晚餐建议。

- [ ] **Step 2: 接口测试验证**

Run:

```bash
cd backend
pytest tests/test_agent_api.py -q
```

Expected: PASS。

---

### Task 6: P0 最终验证

**Files:**
- Verify only.

- [ ] **Step 1: 后端关键测试**

Run:

```bash
cd backend
pytest tests/test_langchain_agent.py tests/test_agent_api.py -q
```

Expected: PASS。

- [ ] **Step 2: 前端构建**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS。

- [ ] **Step 3: 文案范围检查**

Run:

```bash
rg -n "报告知识库|一日三餐膳食推荐 Agent|报告问答工具" README.md frontend/index.html frontend/src/pages/ChatPage.tsx frontend/src/components/chat/ChatInput.tsx backend/app/services/langchain_agent.py
```

Expected:

- `一日三餐膳食推荐 Agent` 不再出现。
- `报告问答工具` 不出现。
- `报告知识库` 不应出现在浏览器标题或 README 主定位里。

注意：不要全局删除“知识库”。知识库是现有报告检索模块，不属于本次 P0 要移除或重命名的内容。

---

## Self-Review

Spec coverage:

- 覆盖 P0 的“家庭健康智能营销 Agent”主定位。
- 避免把项目主入口表达成单纯报告问答。
- 保留知识库作为局部能力，没有过度改名。

Placeholder scan:

- 没有 TBD、TODO、implement later。
- 每个修改点都有明确替换内容。

Type consistency:

- 前端只改文案字符串，不改组件接口。
- 后端只改 prompt 文案和一个 quick action label/action，不改 API schema。
