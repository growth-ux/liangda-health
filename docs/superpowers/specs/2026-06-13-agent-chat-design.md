# Agent 聊天功能设计

## 背景

粮达健康当前已经实现 PDF 报告知识库的基础能力，包括上传、解析、OCR、切片、embedding、向量检索和报告列表展示。下一阶段需要实现 `prd/prototype/chat.html` 对应的 Agent 聊天功能，让用户可以围绕健康报告和健康建议进行连续对话。

本设计按“完整产品版”推进：前后端都实现真实主链路，后端接入阿里云百炼 OpenAI 兼容 Chat Completions，前端还原原型中的会话列表、消息流、快捷指令和输入区。

## 范围

本阶段实现：

- 会话列表、新建会话、消息列表
- 用户发送消息并保存
- 后端调用阿里云百炼模型生成回复
- SSE 流式输出 Agent 回复
- 使用 LangChain 管理模型调用和工具编排
- 基于现有 PDF 知识库做报告 RAG 检索
- 前端聊天页，视觉和 `prd/prototype/chat.html` 保持一致
- 基础错误展示和重试入口
- 后端单元测试与 API 测试

本阶段不实现：

- 复杂 Agent 框架
- 异步任务队列
- 复杂状态机
- 多租户权限
- 逻辑删除
- 设备真实数据接入
- 商城、商品数据和商品推荐
- 家人模块和家庭成员档案表
- 医疗诊断能力

## 设计选择

推荐方案是“完整主链路 + 最简业务数据”。

后端使用 LangChain 负责模型调用和工具编排。`AgentService` 只作为应用层入口，负责会话落库、消息落库、调用 LangChain Agent 和返回 API 响应。这样本期可以接入报告知识库工具，后续商城模块完成后，可以继续添加“查商品”“创建订单”“查询订单”等工具，不需要重写聊天主链路。

LangChain 只用于 Agent 编排，不引入复杂工作流平台。数据库、知识库检索仍然保持项目内的显式服务和 repository，避免把业务状态藏在框架里。

模型接入使用 OpenAI 兼容协议，先实现阿里云百炼。阿里云百炼北京区域 OpenAI 兼容 `base_url` 为：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

Chat Completions 完整接口为：

```text
POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

默认模型使用：

```text
qwen-plus
```

API Key 只允许通过环境变量配置，不写入代码、文档示例或测试 fixture。

## 后端架构

新增模块：

```text
backend/app/api/agent.py
backend/app/models/agent.py
backend/app/schemas/agent.py
backend/app/repositories/agent_repository.py
backend/app/services/agent_service.py
backend/app/services/langchain_agent.py
backend/app/services/agent_tools.py
```

`backend/app/main.py` 注册：

```python
from app.api.agent import router as agent_router

app.include_router(agent_router)
```

服务关系：

```text
agent API
  -> AgentService
     -> AgentRepository
     -> LangChainAgentRunner
        -> init_chat_model(model_provider="openai", base_url=百炼 OpenAI 兼容地址)
        -> KbSearchTool
        -> Future tools
```

### 配置

在 `backend/app/core/config.py` 的 `Settings` 增加：

```python
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
llm_api_key: str | None = None
llm_model: str = "qwen-plus"
llm_timeout_seconds: int = 60
llm_temperature: float = 0.3
```

对应环境变量：

```text
HEALTH_AGENT_LLM_BASE_URL
HEALTH_AGENT_LLM_API_KEY
HEALTH_AGENT_LLM_MODEL
HEALTH_AGENT_LLM_TIMEOUT_SECONDS
HEALTH_AGENT_LLM_TEMPERATURE
```

### 数据模型

#### agent_sessions

保存聊天会话。

```sql
CREATE TABLE agent_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

`status` 只用于展示是否活跃，暂不做复杂归档流程。

#### agent_messages

保存用户和 Agent 消息。

```sql
CREATE TABLE agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'done',
    token_prompt INTEGER NULL,
    token_completion INTEGER NULL,
    model_name VARCHAR(100) NULL,
    created_at DATETIME NOT NULL
);
```

`role` 取值：

```text
user
assistant
system
```

## API 设计

### 获取会话列表

```text
GET /agent/sessions
```

响应：

```json
[
  {
    "session_id": "sess_health_20260613",
    "title": "健康报告咨询",
    "preview": "建议结合最近报告观察血压变化。",
    "updated_at": "2026-06-13T10:00:00"
  }
]
```

### 新建会话

```text
POST /agent/sessions
```

请求：

```json
{
  "title": "新对话"
}
```

响应：

```json
{
  "session_id": "sess_health_20260613",
  "title": "新对话",
  "created_at": "2026-06-13T10:00:00"
}
```

### 获取消息列表

```text
GET /agent/sessions/{session_id}/messages
```

响应：

```json
{
  "items": [
    {
      "message_id": "msg_welcome_20260613",
      "session_id": "sess_health_20260613",
      "role": "assistant",
      "content": "早上好，小李，今天可以继续问我健康报告相关问题。",
      "status": "done",
      "created_at": "2026-06-13T10:00:00"
    }
  ]
}
```

### 发送消息

```text
POST /agent/sessions/{session_id}/messages:send
```

请求：

```json
{
  "content": "最近老说没胃口，睡眠也不太好，有什么建议？"
}
```

响应：

```json
{
  "user_message": {
    "message_id": "msg_user",
    "role": "user",
    "content": "最近老说没胃口，睡眠也不太好，有什么建议？"
  },
  "assistant_message": {
    "message_id": "msg_assistant",
    "role": "assistant",
    "content": "结合已上传报告和你的描述，建议先从饮食和睡眠节律调整。"
  }
}
```

该接口保留为非流式调试和测试入口。前端正式聊天使用 SSE 流式接口。

### 流式发送消息

```text
POST /agent/sessions/{session_id}/messages:stream
```

请求：

```json
{
  "content": "最近老说没胃口，睡眠也不太好，有什么建议？"
}
```

响应类型：

```text
text/event-stream
```

SSE 事件：

```text
event: user_message
data: {"message_id":"msg_user","role":"user","content":"最近老说没胃口，睡眠也不太好，有什么建议？"}

event: assistant_start
data: {"message_id":"msg_assistant","role":"assistant"}

event: delta
data: {"content":"结合"}

event: delta
data: {"content":"已上传报告"}

event: assistant_done
data: {"message_id":"msg_assistant","role":"assistant","content":"结合已上传报告和你的描述，建议先从饮食和睡眠节律调整。"}

event: done
data: {}
```

错误事件：

```text
event: error
data: {"message":"模型调用失败"}
```

### 获取快捷指令

```text
GET /agent/quick-actions
```

响应：

```json
[
  { "label": "/ 查看报表", "action": "open_reports" },
  { "label": "/ 上传报告", "action": "open_upload" }
]
```

## Agent 处理流程

发送消息主流程：

```text
1. 校验 session_id 存在
2. 保存 user message
3. 读取最近 8 条会话消息
4. 构建 LangChain messages，包含 system prompt 和 history
5. 将报告知识库检索注册为 LangChain tool
6. 调用 LangChain Agent 流式接口，由模型决定是否使用报告知识库工具
7. 通过 SSE 持续推送 assistant token delta
8. 模型输出结束后，拼接完整 assistant 内容并保存 assistant message
9. 更新会话 title 和 updated_at
10. 推送 assistant_done 和 done 事件
```

本期只注册一个工具：

```text
kb_search(query: string, top_k: integer = 5)
用途：当用户询问报告、体检、指标、血压、血糖、骨密度、检验或异常时，检索已上传 PDF 报告片段。
```

知识库检索复用现有能力：

```text
embedding_service.embed(query)
vector_store.search(embedding, top_k)
repository.get_chunks_by_ids(hit_chunk_ids)
```

不通过 HTTP 调 `/kb/search`，而是在服务层复用同一套依赖，避免后端内部再走网络。

## 提示词设计

System prompt：

```text
你是粮达健康的家庭健康 Agent 管家。
你可以基于用户上传的健康报告和用户当前问题提供健康建议。

要求：
1. 用简体中文回答。
2. 不做诊断，不替代医生。
3. 对异常指标给出就医提醒。
4. 如果引用报告内容，说明来自哪份报告或页码。
5. 回答要像管家，简洁、具体、可执行。
6. 当信息不足时，直接说明还缺什么信息。
```

报告上下文格式：

```text
[报告片段 1]
文档：{title_or_file_name}
页码：{page_no}
内容：{content}
```

## LangChain 与百炼调用

后端使用 LangChain 的 `init_chat_model` 初始化聊天模型，通过 `model_provider="openai"` 和百炼 OpenAI 兼容配置连接 qwen 模型。Agent 编排使用 LangChain 的 `create_agent`，把模型和工具统一传入。

配置：

```python
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

model = init_chat_model(
    model=settings.llm_model,
    model_provider="openai",
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    temperature=settings.llm_temperature,
    timeout=settings.llm_timeout_seconds,
)

agent = create_agent(
    model=model,
    tools=[kb_search],
    system_prompt=SYSTEM_PROMPT,
)
```

LangChain messages：

```python
[
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content="最近老说没胃口，睡眠也不太好，有什么建议？"),
]
```

返回解析：

```text
AIMessage.content -> assistant content
response_metadata.token_usage.prompt_tokens -> token_prompt
response_metadata.token_usage.completion_tokens -> token_completion
response_metadata.model_name -> model_name
```

如果 `HEALTH_AGENT_LLM_API_KEY` 为空，发送接口返回 500，并给出“未配置模型 API Key”的错误信息。前端显示为发送失败，不自动生成假回答。

## 前端设计

新增文件：

```text
frontend/src/pages/ChatPage.tsx
frontend/src/api/agent.ts
frontend/src/components/chat/SessionList.tsx
frontend/src/components/chat/MessageList.tsx
frontend/src/components/chat/MessageBubble.tsx
frontend/src/components/chat/ChatInput.tsx
```

路由新增：

```tsx
<Route path="/chat" element={<ChatPage />} />
```

`AppShell` 导航更新：

```text
Agent -> /chat
```

页面结构：

```text
AppShell title="与管家对话" activeId="chat"
  chat-layout
    chat-sessions
      chat-sessions-header
      session-list
    chat-main
      chat-header
      chat-messages
      chat-input-area
```

样式以 `prd/prototype/chat.html` 为准，移植原型中的 class 到 `frontend/src/styles.css`：

```text
chat-layout
chat-sessions
session-item
chat-main
chat-header
message-row
msg-avatar
msg-bubble
chat-input-area
quick-actions
chat-input
chat-send-btn
```

状态管理：

```text
useQuery(['agent-sessions'], listAgentSessions)
useQuery(['agent-messages', sessionId], listAgentMessages)
useMutation(sendAgentMessageStream)
```

发送交互：

```text
1. 用户输入非空后点击发送
2. 本地追加 user 消息
3. 本地追加空的 assistant 消息，展示生成中状态
4. 请求 /agent/sessions/{session_id}/messages:stream
5. 收到 `delta` 事件时追加到 assistant 消息内容
6. 收到 `assistant_done` 后标记消息完成，并刷新会话列表
7. 收到 `error` 后标记消息失败，显示错误条和重试按钮
```

因为流式接口使用 `POST`，前端不使用浏览器原生 `EventSource`。`agent.ts` 使用 `fetch` 发起请求，读取 `response.body.getReader()` 返回的 `ReadableStream`，按 SSE 格式解析 `event:` 和 `data:`。

快捷指令：

```text
/ 查看报表 -> 跳转 /reports
/ 上传报告 -> 跳转 /reports 并打开上传弹窗，若当前页面暂不支持跨页打开弹窗，则先跳转 /reports
```

## 错误处理

只做必要错误处理：

- 会话不存在：404
- 消息内容为空：400
- 未配置模型 API Key：500
- 百炼接口失败：502
- 知识库检索失败：不中断聊天，记录为空上下文
- SSE 连接中断：前端保留已生成文本，并提示可重新发送

前端展示：

- 页面加载失败：显示错误提示
- 发送失败：输入区上方显示错误条
- 正在生成：禁用发送按钮，assistant 气泡展示生成中状态

## 测试

后端测试：

```text
backend/tests/test_agent_api.py
backend/tests/test_agent_service.py
backend/tests/test_langchain_agent.py
```

覆盖：

- 创建会话
- 获取会话列表
- 获取消息列表
- 非流式发送保存 user 和 assistant
- SSE 流式发送按顺序输出 user_message、assistant_start、delta、assistant_done、done
- SSE 结束后保存完整 assistant message
- mock 百炼返回内容、模型名和 token
- 健康关键词触发知识库检索
- 未配置 API Key 返回清晰错误

前端验证：

```text
npm run build
```

后端验证：

```text
uv run pytest
```

集成验证：

```text
1. 配置 HEALTH_AGENT_LLM_API_KEY
2. 启动后端
3. 启动前端
4. 上传一份 PDF 报告
5. 打开 /chat
6. 询问“我妈这份报告有什么异常？”
7. 页面流式展示 Agent 回复
```

## 实施顺序

1. 增加后端配置和 LangChain 依赖
2. 增加 Agent 数据模型、schema、repository
3. 实现 `agent_tools.py` 中的 `kb_search` 工具
4. 实现 `LangChainAgentRunner`
5. 实现 `AgentService`
6. 实现 `/agent` API 和 SSE 流式接口
7. 增加后端测试
8. 增加前端 `agent.ts`
9. 增加 `ChatPage` 和聊天组件
10. 移植原型聊天样式
11. 更新路由和侧边栏导航
12. 执行后端测试和前端构建

## 后续扩展

确认主链路可用后再考虑：

- LangChain 工具：查商品、创建订单、查询订单
- 真实设备数据接入
- 家人模块和家庭成员档案表
- 商城、商品详情页和商品推荐联动
- 健康摘要定时生成
- 引用来源展开查看
