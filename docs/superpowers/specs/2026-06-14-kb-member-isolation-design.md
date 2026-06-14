# 知识库严格家人隔离设计

- 日期：2026-06-14
- 状态：已通过 brainstorming，待编写实现计划
- 范围：知识库（KB）模块的家人隔离改造 + 历史脏数据迁移

## 1. 背景与目标

### 现状问题

体检 PDF 上传后会切分、向量化、入库。当前实现：

- 上传时确实有 `member_id` 必填校验（`backend/app/api/kb.py:60-65`）
- 数据库 `kb_documents.member_id` 字段已存在
- **但**：
  - 向量库 schema 没有 `member_id` 字段，无法在向量层做家人隔离
  - `POST /api/kb/search` 不接收 `member_id` 参数，搜索时不隔离
  - Agent 工具 `kb_search` 也不接收 `member_id`，管家对话全家报告混在一起召回
  - `ChatPage.tsx:137` 上传时硬编码 `memberId: 'default'`，聊天场景的报告根本未归属

### 目标

实现知识库的**严格家人隔离**：上传时归属、检索时强制按家人过滤、Agent 智能识别家人意图。

### 不在范围（明确排除）

- 报告去重、OCR 优化（独立话题）
- 商城推荐接入（独立模块）
- 跨家人对比的额外 UI（用户用自然对话即可，不新增组件）

## 2. 数据模型变更

### SQL 层

#### `kb_documents.member_id`
已存在。当前为可空（`String(64), nullable=True`）。改造后：

- **必填**：`nullable=False`
- 迁移时先跑迁移脚本回填脏数据（NULL / `'default'`），再施加 NOT NULL 约束

#### `kb_chunks.member_id`（新增）
冗余存储以避免每次召回都 join `kb_documents`：

```python
class KbChunk(Base):
    __tablename__ = "kb_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # NEW
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
```

### 向量库层

#### `VectorRecord`（`backend/app/services/vector_store.py`）
新增 `member_id` 字段：

```python
@dataclass(frozen=True)
class VectorRecord:
    chunk_id: str
    document_id: str
    member_id: str        # NEW
    embedding: list[float]
```

#### `MilvusVectorStore`
- schema 新增 `member_id` 字段（`DataType.VARCHAR, max_length=64`）
- 在 `member_id` 上建标量索引
- 搜索时通过 `expr='member_id == "xxx"'` 过滤

#### `InMemoryVectorStore`
- 内部用 `dict[str, dict[str, VectorRecord]]`（外层 key 是 member_id）
- `search(query_embedding, member_id, top_k)` 先按 member_id 取桶，再做点积

### 迁移策略（向量库）

- **InMemory**：进程重启即丢，启动后从 SQL 懒加载，无需特殊处理
- **Milvus**：用 `MilvusClient.add_collection_field` 加字段；如版本不支持，fallback 到 drop+recreate

## 3. API 契约变更

### `POST /api/kb/upload`
**不变**（`member_id` 已经是必填）。但写入 `kb_chunks` 时也写入 `member_id`。

### `POST /api/kb/search`
请求体变更：

```python
class SearchRequest(BaseModel):
    query: str
    member_id: str           # NEW, required
    top_k: int = 5
```

- 后端先校验 `member_id` 在 `members` 表中存在（否则 400）
- 向量库搜索时强制带 `member_id` 过滤
- 响应结构不变

### `POST /api/agent/sessions/{id}/messages:send` / `:stream`
请求体不变。内部变化：system prompt 拼接成员列表；`kb_search` 工具强制 `member_id`。

## 4. Agent 集成（核心）

### System Prompt（每次调用前注入）

```
你是粮达健康的家庭健康 Agent 管家。
你可以基于用户上传的健康报告和用户当前问题提供健康建议。

要求：
1. 用简体中文回答。
2. 不做诊断，不替代医生。
3. 对异常指标给出就医提醒。
4. 如果引用报告内容，说明来自哪份报告或页码。
5. 回答要像管家，简洁、具体、可执行。
6. 当信息不足时，直接说明还缺什么信息。
7. 【新增】检索用户报告时必须调用 kb_search 工具，并显式传入 member_id。
   不要在不知道是哪位家人的情况下盲猜。
8. 【新增】当前可用家人列表：
   - 张三（member_id=mem_xxx1，本人）
   - 张三爸（member_id=mem_xxx2，父亲）
   - 张三妈（member_id=mem_xxx3，母亲）
   如果用户问"爸爸"对应到"张三爸"，以此类推。
   如果指代不明（如"他/她"无上下文），必须先反问"您说的'他/她'是指哪位家人？"，不要主动猜测。
9. 【新增】跨家人对比问题（"全家血脂怎么样"）需要分别对每位家人调用 kb_search，然后合成答案。
```

`LangChainAgentRunner` 改造：
- 接受 `member_provider` 依赖（提供 `list_members()` 接口）
- 在 `_append_kb_context` 或 `_build_messages` 之前调用 `member_provider.list_members()`，格式化后拼接到 `SYSTEM_PROMPT`
- 成员列表为空时，跳过第 7-9 条规则，但仍保留 kb_search 工具（LLM 会拿到空列表自然无法调用）

### 工具定义

```python
@tool
def kb_search(query: str, member_id: str, top_k: int = 5) -> str:
    """检索指定家人的健康报告片段。
    必须传入 member_id（来自 system prompt 的可用家人列表）。
    返回最多 top_k 条相关片段，包含文档名/页码/内容。
    """
    # 1. 校验 member_id 在白名单（system prompt 里给的列表）
    # 2. 向量库按 member_id 过滤搜 top_k
    # 3. 拿 chunk 原文组装成文本返回
    # 4. 异常时返回错误字符串（让 LLM 看到错误并重试或追问）
```

`KbSearchTool`（`backend/app/services/agent_tools.py`）改造：
- 构造函数新增 `allowed_member_ids: list[str]`（白名单，从 member_provider 传入）
- `search(query, member_id, top_k=5)` 必填 member_id
- 校验 `member_id in allowed_member_ids`，否则返回 `Error: member_id=xxx 不在可用家人列表中`
- 移除 `should_search` 关键字短路逻辑（不再基于关键词触发，统一交给 LLM 决策）

### 端到端流程

```
用户发消息（chat session）
  ↓
AgentService.send_message(content)
  ↓
1. member_provider.list_members() → 成员列表
2. 拼到 system prompt（替换/扩展 SYSTEM_PROMPT）
3. 构造 LangChain agent（带 kb_search 工具 + 新 system prompt）
4. agent.invoke(messages)
5. LLM 决定：
   a) 直接回答（不涉及报告）
   b) 调用 kb_search(query, member_id) → 报告片段 → 生成回答
   c) 多次 kb_search（跨家人）→ 合成回答
   d) 反问（指代不明）
6. 流式返回给前端
```

## 5. 前端变更

### ChatPage（关键修复）
**位置**：`frontend/src/pages/ChatPage.tsx`

变更点：
- `ChatPage.tsx:137` 去掉硬编码 `memberId: 'default'`
- 复用 `UploadReportDialog`（已有家人选择器）
- `handleUpload`：弹出 dialog → 用户选家人 + 选文件 → 上传 → 成功后将附件加入消息输入区

不需要新增"当前家人"上下文状态（用户已选 LLM 智能识别方案，前端无需传 member context）。

### ReportsPage
**位置**：`frontend/src/pages/ReportsPage.tsx`

`family` 过滤下拉已经存在，复用即可。但顶部新增一个**搜索框**调用 `/api/kb/search` 时也要传当前 family filter 的 member_id（family == 'all' 时禁用搜索，或要求用户先选一个家人）。

### MemberDetailPage
**不变**（已正确传 `memberId`，且只查该成员的文档）。

### API 客户端
**位置**：`frontend/src/api/kb.ts`

`searchKb` 签名变更：
```ts
searchKb(query: string, memberId: string, topK: number): Promise<SearchResult[]>
// memberId 从可选改为必填
```

## 6. 迁移脚本

**路径**：`backend/scripts/migrate_kb_member_binding.py`

### 步骤

```
1. 从 DB 查所有 kb_documents WHERE member_id IS NULL OR member_id = 'default'
2. 对每条脏记录：
   a. 读 patient_name（已存）
   b. SELECT * FROM members WHERE name = :patient_name
   c. 唯一匹配 → UPDATE kb_documents SET member_id = :matched_member_id
   d. 无匹配 → 写入 reports/unmatched_documents.csv
   e. 多匹配（重名） → 写入 reports/ambiguous_documents.csv 待人工处理
3. 同步更新 kb_chunks.member_id（同样的批量 UPDATE）
4. 重新 embed 所有 chunk 并写向量库：
   - InMemory：进程重启即丢，无需主动操作（启动时会懒加载）
   - Milvus：按 document_id 批量查 chunk → embed → upsert
5. 输出汇总：
   - 成功 N 条
   - 未匹配 M 条 → reports/unmatched_documents.csv
   - 多匹配 K 条 → reports/ambiguous_documents.csv
   - 失败 L 条（含异常）
```

### 可重入

脚本幂等。WHERE 条件已限定脏数据范围，跑过一次的不会再处理。可重复执行直到输出全为 0。

### dry-run 模式

支持 `--dry-run` 参数，只输出匹配结果不写库，方便人工预览。

## 7. 错误处理与边界

| 场景 | 处理 |
|---|---|
| LLM 传了不存在的 `member_id` | 工具返回 `Error: member_id=xxx 不在可用家人列表中`，LLM 重试 |
| LLM 指代不明不追问直接猜 | system prompt 强制要求追问；接受 LLM 偶发失误，无强校验 |
| 用户只有一位家人 | 列表只有 1 项，LLM 无歧义 |
| 用户没上传过报告 | 工具返回空，LLM 答"目前还没有 XX 的报告，无法回答" |
| 成员被删除 | `member_repository.delete` 时检查 `kb_documents.member_id` 引用：若有引用则拒绝删除并提示用户先删除报告 |
| 迁移时部分失败 | 报告里列出失败原因；脚本可重入 |
| ChatPage 上传附件但不选家人 | `UploadReportDialog` 已有"请选择家人"校验，不允许提交 |
| Search API 不传 member_id | Pydantic 校验直接 422 |
| Search API 传不存在的 member_id | 后端 400 "家人不存在" |

## 8. 测试策略

### 单元测试

| 模块 | 重点 |
|---|---|
| `KbSearchTool.search` | 按 `member_id` 过滤正确性；不存在的 `member_id` 返回错误；跨家人拒绝 |
| `InMemoryVectorStore` | 加字段后 search 按 member_id 正确过滤 |
| `MilvusVectorStore` | `expr` 过滤正确性（集成测试） |
| SystemPromptBuilder | 成员列表正确注入；空列表时不崩溃 |
| `kb_repository.list_documents_by_member` | 按成员过滤正确 |

### 集成测试

- `POST /api/kb/search` 不带 `member_id` → 422
- `POST /api/kb/search` 带不存在 `member_id` → 400
- `POST /api/kb/search` 带正确 `member_id` → 只返回该成员的 chunk
- 上传时 `kb_chunks.member_id` 写入正确
- 删除 member（有引用）→ 拒绝
- 删除 member（无引用）→ 成功

### Agent 测试

mock LLM，验证：
- 工具签名接受 `member_id` 必填
- LLM 调用 `kb_search` 时不传 `member_id` 应触发工具报错
- 跨家人查询 LLM 多次调用

### 前端测试

- ChatPage 上传流程：弹出 dialog → 选家人 → 上传成功 → 附件加入消息区
- ReportsPage 搜索：选家人 → 搜索 → 只显示该成员结果
- 不选家人时搜索被禁用

### 迁移脚本测试

测试库造一批脏数据：
- `member_id = NULL` + `patient_name` 匹配某成员 → 应被回填
- `member_id = 'default'` + `patient_name` 不匹配 → 应进入 unmatched 报告
- `member_id = 'default'` + `patient_name` 重名 → 应进入 ambiguous 报告
- 重复执行 → 全部为 0 处理

## 9. 改动文件清单（待实现）

### 后端

- `backend/app/models/kb.py` — `kb_chunks.member_id` 新增；`kb_documents.member_id` 改 NOT NULL
- `backend/app/services/vector_store.py` — `VectorRecord` 加字段；两个 store 类加 member_id 过滤
- `backend/app/services/kb_service.py` — 写入时带 member_id；upsert 时带 member_id
- `backend/app/services/agent_tools.py` — `KbSearchTool` 接受白名单；强制 member_id
- `backend/app/services/langchain_agent.py` — system prompt 注入成员列表
- `backend/app/repositories/kb_repository.py` — 新增 `list_documents_by_member`、`get_chunks_by_member`、`save_chunks` 带 member_id
- `backend/app/repositories/member_repository.py` — 删除前检查 kb 引用
- `backend/app/api/kb.py` — `SearchRequest` 加 member_id；搜索路由校验 + 过滤
- `backend/app/api/agent.py` — 注入 member_provider
- `backend/scripts/migrate_kb_member_binding.py` — 新增迁移脚本

### 前端

- `frontend/src/api/kb.ts` — `searchKb` 签名变更
- `frontend/src/pages/ChatPage.tsx` — 去掉硬编码，集成 UploadReportDialog

### 测试

- `backend/tests/test_api_kb.py` — 搜索接口新场景
- `backend/tests/test_kb_service.py` — 上传带 member_id
- `backend/tests/test_agent_tools.py` — KbSearchTool 新场景
- `backend/tests/test_langchain_agent.py` — system prompt 注入成员
- `backend/tests/test_vector_store.py`（如不存在则新增）— member_id 过滤
- `backend/tests/test_migrate_kb_member_binding.py`（新增）— 迁移脚本

## 10. 实施顺序建议

1. **数据模型 + 迁移脚本**（前置，无依赖）：先改 `models/kb.py`、写迁移脚本、加 `kb_chunks.member_id`
2. **向量库 + KbService**：`VectorRecord`、两个 store、`kb_service.upload_pdf` 带 member_id
3. **API 层**：`SearchRequest`、`/api/kb/search` 强制 member_id
4. **kb_repository**：新增按 member 过滤的接口
5. **Agent 集成**：`KbSearchTool`、`LangChainAgentRunner`、member_provider
6. **前端**：ChatPage、kb.ts、ReportsPage 搜索框
7. **回归测试 + 迁移跑一次**