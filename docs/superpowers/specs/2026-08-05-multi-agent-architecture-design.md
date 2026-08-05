# 多 Agent 架构设计（Supervisor + 专家团）

- 日期：2026-08-05
- 状态：已与用户确认，待实施
- 目标：将现有「单 Agent + 工具」对话链路改造为「Supervisor 调度 + 3 专家 Agent 协作」的多 Agent 架构，作为 AI 决赛演示亮点，同时增量兼容现有 SSE 流式协议与结构化卡片。

## 1. 背景与动机

当前主对话链路是单 Agent：`LangChainAgentRunner` 用 LangChain `create_agent()` 创建唯一 agent，挂 5 个工具（meal_plan / mall_recommend / memory_search / kb_search / respond），工具链顺序（记忆 → 餐单 → 商品 → 收尾）完全靠一份数百行的大 system prompt 硬约束（规则 21~27）。

改造动机：**决赛演示亮点优先**。评委能实时看到「调度 → 分派 → 专家工作 → 汇总」的协作过程；同时拆分后各专家 prompt 聚焦，编排可靠性顺带提升。

明确不做（YAGNI，与 AGENTS.md「最简流程」一致）：

- 不引入 LangGraph 等新框架，纯 LangChain 实现，零新依赖
- 不持久化协作过程（仅流式期间展示）
- 不做配置开关 / 灰度 / 兜底双链路
- 不做并行专家调度

## 2. 总体架构

```
用户消息
   ↓
AgentService（不动，仅依赖 runner 的 run/stream 签名）
   ↓
MultiAgentRunner（新增，替换 LangChainAgentRunner）
   │
   ├─ 🧭 Supervisor Agent（总调度，唯一对外出口）
   │    工具：ask_meal_planner / ask_shopping_guide / ask_report_reader / respond
   │    职责：意图识别 → 按需调度专家（可多个、按序）→ 汇总专家产出 → 调 respond 出结构化卡片
   │
   ├─ 🥗 餐单规划师 Agent（子 Agent，嵌在 ask_meal_planner 工具内）
   │    工具：meal_plan、memory_search
   │    职责：先查偏好记忆，再生成餐单，返回餐单文本
   │
   ├─ 🛒 商品导购师 Agent（嵌在 ask_shopping_guide）
   │    工具：mall_recommend
   │    职责：按餐单文本或商品类目查询推荐商品，返回推荐 JSON
   │
   └─ 📋 报告解读师 Agent（嵌在 ask_report_reader）
        工具：kb_search
        职责：检索指定家人的报告片段并给出解读结论
```

### 2.1 Handoff 机制

- 每个专家是独立的 `create_agent` ReAct 循环，拥有自己聚焦的 system prompt。
- 专家以 handoff 工具形式挂在 Supervisor 上：`ask_xxx(task: str) -> str`。工具 wrapper 内部同步执行专家 Agent（`expert.invoke`），把专家最终文本带回 Supervisor。
- 专家**不直接面对用户**、**不调 respond**；只有 Supervisor 调 `respond` 产出结构化卡片。前端卡片渲染逻辑完全不动。
- 现有 `MealPlanTool` / `MallRecommendTool` / `KbSearchTool` / `MemorySearchTool` 及底层 service 原样复用，只更换挂载对象。
- 典型链路：「今晚全家吃什么」→ Supervisor 调 `ask_meal_planner`（内部 memory_search → meal_plan）→ 拿餐单文本调 `ask_shopping_guide`（task 中携带 meal_plan_text）→ 调 `respond` 出餐单卡片，商品卡自动附加。

### 2.2 Prompt 拆分

- 现 `langchain_agent.py` 中 SYSTEM_PROMPT_TEMPLATE 的规则 21~27（工具链顺序、respond 强制收尾、商品不入文本等）不再由单一 prompt 承载：
  - 编排类规则（何时调哪个专家、餐单后接导购）→ Supervisor prompt
  - 领域类规则（餐单份量表达、推荐 scope 一致性、报告对比需多次检索）→ 各专家 prompt
  - 通用安全规则（不泄露 member_id、不做诊断、respond 格式）→ Supervisor prompt 保留
- 家人列表块（`_build_members_block`）继续注入 Supervisor prompt；专家 prompt 中按需注入 member 映射。

## 3. 流式协作事件与前端可视化

### 3.1 工作线程 + 事件队列

专家在 Supervisor 的工具内部执行，`agent.stream` 迭代器在工具执行期间阻塞，沿用「边迭代边 yield」会让「专家开始工作」事件延迟到专家结束才可见。解法：

```
主线程（stream 生成器）                工作线程
    │                                    │
    │  启动 ──────────────────────────►  for chunk in supervisor.stream():
    │                                       queue.put(("chunk", chunk))
    │  循环：                               │
    │   q.get(timeout) ──► chunk   → yield 对应事件（delta/card/product…）
    │   q.get(timeout) ──► activity → yield ("agent_activity", {...})
    │                                    │
    │              ◄── handoff 工具执行时直接 queue.put(("activity", ...))
    │                  （工具在工作线程里跑，事件立即可见）
```

- 现有 `delta` / `card` / `product_recommendations` 事件的产生逻辑原样搬进主循环，协议不变。
- 新增 SSE 事件 `agent_activity`：

  ```json
  {"agent": "supervisor|meal_planner|shopping_guide|report_reader",
   "action": "start|done",
   "detail": "正在结合家人偏好生成晚餐…"}
  ```

- 事件来源：handoff 工具 wrapper（专家 start/done）；底层工具 wrapper 可选推细粒度动作。
- 结构化数据捕获（嵌套后 ToolMessage 不再出现在 Supervisor 消息流）：
  - `product_recommendations`：导购师内部的 `mall_recommend` 结果由工具 wrapper 解析后直接推入队列，发 `product_recommendations` 事件。
  - 证据链：`AgentEvidenceCollector` 挂在共享工具实例上，机制不变，随 `card` 事件输出。
- 工作线程结束推哨兵；异常推哨兵 + 异常信息，主循环抛出后走现有 `error` SSE 事件。

### 3.2 前端 AgentTeamStrip 协作条

- 位置：流式回复气泡上方的状态条，不影响消息列表结构。
- 形态：4 个角色节点横排 —— 🧭 调度中心 → 🥗 餐单规划师 / 🛒 商品导购师 / 📋 报告解读师。
- 状态机：`idle`（灰）→ `working`（高亮 + 呼吸动画 + detail 文字）→ `done`（打勾）。流式结束后整条淡出。
- `frontend/src/api/agent.ts`：新增 `agent_activity` 事件解析与 `onAgentActivity` 回调。
- `frontend/src/pages/ChatPage.tsx`：维护 `teamState`，流式期间渲染协作条。
- 不持久化：刷新页面后只看到最终卡片，与现有行为一致。

## 4. 错误处理

| 场景 | 处理 |
|---|---|
| 专家内部失败（如 meal_plan 返回 Error） | handoff 工具把 `"Error: ..."` 文本带回 Supervisor；Supervisor prompt 规则：专家报错时温和降级（如"暂时无法推荐商品"），与现有行为一致 |
| Supervisor 未调 respond 就收尾 | 复用现有 `_fallback_evidence_card()`：补一张只挂证据链的空卡 |
| 未配置 API Key | 照旧抛 `LlmConfigError`，AgentService 转 500 |
| 专家 LLM 调用异常 | handoff wrapper 捕获后返回 `"Error: 专家处理失败"`，Supervisor 按降级规则处理；不让整个请求 502 |
| 工作线程异常 | 队列哨兵携带异常，主循环抛出，走现有 `error` SSE 事件 |

## 5. 测试策略

- 新增 `backend/tests/test_multi_agent.py`：
  - Supervisor 注册 3 个 handoff 工具 + respond；各专家注册自己的工具子集
  - handoff 工具同步执行专家并返回文本（Fake 专家 Agent）
  - `stream()` 用 Fake Supervisor 验证：`agent_activity` 事件顺序（start → done）、`product_recommendations` 从队列捕获、`delta` / `card` 协议不变
  - 专家失败时 Supervisor 收到 Error 文本并降级
- 改造 `backend/tests/test_langchain_agent.py`：
  - 依赖旧 system prompt 规则 21~27 的断言按新拆分结构改写（各角色 prompt 分别断言）
  - 流式协议相关测试迁移至 `test_multi_agent.py`
- 回归不动：`test_agent_api.py` / `test_agent_service.py`（AgentService 只依赖 runner 的 run/stream 签名，接口不变）。

## 6. 改动清单

| 文件 | 动作 |
|---|---|
| `backend/app/services/multi_agent.py` | 新增 `MultiAgentRunner`：Supervisor + 3 专家构建、handoff 工具、工作线程 + 队列流式、事件产出 |
| `backend/app/services/langchain_agent.py` | 保留可复用函数（respond 工具定义、`_format_summary_text`、卡片解析、fallback 空卡）；删除旧 SYSTEM_PROMPT_TEMPLATE 与 `LangChainAgentRunner` |
| `backend/app/api/agent.py` | DI 注入 `MultiAgentRunner` 替换 `LangChainAgentRunner` |
| `frontend/src/api/agent.ts` | 新增 `agent_activity` 事件解析 + `onAgentActivity` 回调 |
| `frontend/src/components/chat/AgentTeamStrip.tsx` | 新增协作条组件 |
| `frontend/src/pages/ChatPage.tsx` | 维护 teamState，流式期间渲染协作条 |
| `frontend/src/styles.css` | 协作条样式 |
| `backend/tests/test_multi_agent.py` | 新增 |
| `backend/tests/test_langchain_agent.py` | 按新 prompt 结构改写断言 |

## 7. 验收标准

1. 发起「今晚全家吃什么」对话：前端协作条依次点亮调度中心 → 餐单规划师 → 商品导购师，最终出现餐单卡片 + 商品卡片，流式打字机效果不中断。
2. 发起报告解读问题：协作条点亮报告解读师，证据链 tab 正常展示。
3. 专家失败场景（如断掉商品库）：对话不报错，Supervisor 温和降级说明。
4. 现有回归测试（agent api / service / e2e）全部通过。
