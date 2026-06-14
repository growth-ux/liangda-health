# 知识库严格家人隔离实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现知识库严格按家人隔离——上传时归属、检索时强制 member_id、Agent 智能识别家人，并迁移历史脏数据。

**Architecture:**
- 数据层：`kb_chunks` 新增 `member_id` 字段；向量库（InMemory + Milvus）schema 加 `member_id` 并按其过滤
- API 层：`/api/kb/search` 强制要求 `member_id`；Agent `kb_search` 工具强制要求 `member_id`
- Agent 层：system prompt 注入可用家人列表；LLM 从中识别并显式传 `member_id`；跨家人靠多次调用合成
- 迁移层：单独脚本按 `patient_name` 严格匹配回填历史脏数据，并补齐向量库

**Tech Stack:**
- 后端：Python 3.13 / FastAPI / SQLAlchemy 2.x / PyMySQL / DashScope Embedding / LangChain / Milvus（可选）
- 前端：React / TypeScript / TanStack Query / React Router
- 测试：pytest + FastAPI TestClient + 自定义 FakeDb/FakeVectorStore

**关联文档：**
- 设计：`docs/superpowers/specs/2026-06-14-kb-member-isolation-design.md`

---

## File Structure

### 后端（修改 / 新增）

| 文件 | 责任 |
|---|---|
| `backend/app/models/kb.py` | SQL 模型：`KbChunk.member_id` 新增；`KbDocument.member_id` 改 NOT NULL |
| `backend/app/services/vector_store.py` | `VectorRecord` 加字段；两个 store 类按 `member_id` 过滤 |
| `backend/app/services/kb_service.py` | `upload_pdf` 写入 member_id 到 chunks + vectors |
| `backend/app/repositories/kb_repository.py` | `save_chunks` 带 member_id；新增 `list_documents_by_member`、`get_chunks_by_member` |
| `backend/app/repositories/member_repository.py` | `delete_member` 校验 KB 引用 |
| `backend/app/schemas/kb.py` | `SearchRequest` 加 `member_id` 必填 |
| `backend/app/api/kb.py` | search 路由校验 + 过滤 |
| `backend/app/services/agent_tools.py` | `KbSearchTool` 接受白名单 + 强制 `member_id` |
| `backend/app/services/langchain_agent.py` | 注入成员列表到 system prompt |
| `backend/app/api/agent.py` | 装配 member_provider |
| `backend/scripts/migrate_kb_member_binding.py` | **新建**：历史脏数据迁移脚本 |
| `backend/tests/test_models_kb.py` | **新建**：模型字段测试 |
| `backend/tests/test_vector_store.py` | **新建**：vector store 过滤测试 |
| `backend/tests/test_kb_repository.py` | **新建**：repository 过滤测试 |
| `backend/tests/test_migrate_kb_member_binding.py` | **新建**：迁移脚本测试 |
| `backend/tests/test_api_kb.py` | 修改：search/upload 测试 |
| `backend/tests/test_kb_service.py` | 修改：上传带 member_id |
| `backend/tests/test_agent_tools.py` | 修改：KbSearchTool 强制 member_id |
| `backend/tests/test_langchain_agent.py` | 修改：system prompt 注入成员 |

### 前端（修改）

| 文件 | 责任 |
|---|---|
| `frontend/src/api/kb.ts` | `searchKb` 签名加 `memberId` 必填 |
| `frontend/src/components/KbSearchPanel.tsx` | 接受 `memberId` prop |
| `frontend/src/pages/ReportsPage.tsx` | 挂载 KbSearchPanel（仅在选中单家人时） |
| `frontend/src/pages/ChatPage.tsx` | 上传改成 `UploadReportDialog` |

---

## Task 1: SQL 数据模型升级（kb_chunks.member_id + kb_documents NOT NULL）

**Files:**
- Modify: `backend/app/models/kb.py`
- Test: `backend/tests/test_models_kb.py`

- [ ] **Step 1: 写失败的模型字段测试**

```python
# backend/tests/test_models_kb.py
from sqlalchemy import inspect

from app.db.session import Base
from app.models.kb import KbChunk, KbDocument


def test_kb_document_member_id_is_not_nullable():
    column = inspect(KbDocument).columns["member_id"]
    assert column.nullable is False


def test_kb_chunk_has_member_id_column():
    columns = {col.name for col in inspect(KbChunk).columns}
    assert "member_id" in columns
    column = inspect(KbChunk).columns["member_id"]
    assert column.nullable is False
    assert column.index is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/test_models_kb.py -v`
Expected: FAIL with `sqlalchemy.exc.NoSuchTableError` 或 `KeyError: 'member_id'`（因为 KbChunk 还没有 member_id）

- [ ] **Step 3: 改 KbDocument.member_id 为 NOT NULL**

修改 `backend/app/models/kb.py`：
```python
member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
```
（删掉 `nullable=True`）

- [ ] **Step 4: 给 KbChunk 加 member_id 字段**

在 `backend/app/models/kb.py` 的 `KbChunk` 类内添加（在 `page_no` 之后、`content` 之前）：
```python
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/test_models_kb.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/kb.py backend/tests/test_models_kb.py
git commit -m "feat(kb): kb_chunks.member_id + kb_documents NOT NULL"
```

---

## Task 2: 向量库层 VectorRecord + InMemoryVectorStore 加 member_id 过滤

**Files:**
- Modify: `backend/app/services/vector_store.py`
- Test: `backend/tests/test_vector_store.py`

- [ ] **Step 1: 写失败的过滤测试**

```python
# backend/tests/test_vector_store.py
from app.services.vector_store import InMemoryVectorStore, VectorRecord


def test_in_memory_vector_store_filters_by_member_id():
    store = InMemoryVectorStore()
    store.upsert([
        VectorRecord(chunk_id="c1", document_id="d1", member_id="mem_1", embedding=[1.0, 0.0]),
        VectorRecord(chunk_id="c2", document_id="d2", member_id="mem_2", embedding=[1.0, 0.0]),
    ])

    hits = store.search([1.0, 0.0], top_k=5, member_id="mem_1")

    assert [hit.chunk_id for hit in hits] == ["c1"]


def test_in_memory_vector_store_returns_empty_when_no_match():
    store = InMemoryVectorStore()
    store.upsert([
        VectorRecord(chunk_id="c1", document_id="d1", member_id="mem_1", embedding=[1.0, 0.0]),
    ])

    hits = store.search([1.0, 0.0], top_k=5, member_id="mem_2")

    assert hits == []


def test_vector_record_requires_member_id():
    record = VectorRecord(chunk_id="c1", document_id="d1", member_id="mem_1", embedding=[1.0])
    assert record.member_id == "mem_1"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/test_vector_store.py -v`
Expected: FAIL with `TypeError: __init__() missing 1 required positional argument: 'member_id'`

- [ ] **Step 3: 改 VectorRecord 加 member_id**

修改 `backend/app/services/vector_store.py`：
```python
@dataclass(frozen=True)
class VectorRecord:
    chunk_id: str
    document_id: str
    member_id: str        # NEW
    embedding: list[float]
```

- [ ] **Step 4: 改 InMemoryVectorStore.search 接 member_id**

替换 `InMemoryVectorStore` 的 `search` 方法：
```python
    def search(self, query_embedding: list[float], top_k: int, member_id: str | None = None) -> list[VectorHit]:
        if member_id is None:
            raise ValueError("member_id is required for search")
        hits = [
            VectorHit(chunk_id=record.chunk_id, score=_dot(query_embedding, record.embedding))
            for record in self.records
            if record.member_id == member_id
        ]
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]
```

- [ ] **Step 5: 改 MilvusVectorStore.search 接 member_id**

替换 `MilvusVectorStore.search`：
```python
    def search(self, query_embedding: list[float], top_k: int, member_id: str | None = None) -> list[VectorHit]:
        if member_id is None:
            raise ValueError("member_id is required for search")
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            limit=top_k,
            filter=f'member_id == "{member_id}"',
            output_fields=["chunk_id"],
        )
        hits: list[VectorHit] = []
        for result in results[0]:
            chunk_id = result.get("entity", {}).get("chunk_id") or result.get("id")
            hits.append(VectorHit(chunk_id=chunk_id, score=float(result.get("distance", 0.0))))
        return hits
```

并在 `MilvusVectorStore.__init__` 里 schema 加字段（修改 create_schema 部分）：
```python
        schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("member_id", DataType.VARCHAR, max_length=64)  # NEW
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dimension)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && pytest tests/test_vector_store.py -v`
Expected: PASS

- [ ] **Step 7: 跑全量测试看现有 fake 哪里破了**

Run: `cd backend && pytest -v`
Expected: 大概率 `test_kb_service.py` 和 `test_api_kb.py` 会 fail（因为 VectorRecord 构造、VectorStore.search 调用没传 member_id）。先记录这些 fail，下个 Task 一起修。

- [ ] **Step 8: 提交**

```bash
git add backend/app/services/vector_store.py backend/tests/test_vector_store.py
git commit -m "feat(kb): vector store 按 member_id 过滤"
```

---

## Task 3: KbService.upload_pdf 写入 member_id

**Files:**
- Modify: `backend/app/services/kb_service.py`
- Modify: `backend/app/services/chunker.py`
- Test: `backend/tests/test_kb_service.py`

- [ ] **Step 1: 改 chunker.TextChunk 加 member_id**

修改 `backend/app/services/chunker.py` 的 `TextChunk`：
```python
@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    document_id: str
    member_id: str        # NEW
    page_no: int
    content: str
```

并修改 `chunk_page_text` 签名（加 member_id 参数）+ 函数体里构造 TextChunk 时传入：
```python
def chunk_page_text(
    document_id: str,
    member_id: str,       # NEW
    page_no: int,
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    ...
    chunks.append(
        TextChunk(
            chunk_id=f"chunk_{uuid4().hex}",
            document_id=document_id,
            member_id=member_id,    # NEW
            page_no=page_no,
            content=normalized,
        )
    )
```

- [ ] **Step 2: 改 KbService.upload_pdf 传 member_id 到 chunker 和 vector store**

修改 `backend/app/services/kb_service.py` 的 `upload_pdf`（在 `chunks.extend(chunk_page_text(...))` 和 `vector_store.upsert(...)` 两处）：
```python
            chunks: list[TextChunk] = []
            for page in pages:
                chunks.extend(
                    chunk_page_text(
                        document_id=document_id,
                        member_id=member_id or "",
                        page_no=page.page_no,
                        text=page.text_content,
                    )
                )
            self.repository.save_chunks(chunks)

            embeddings = self.embedding_service.embed_many([chunk.content for chunk in chunks])
            self.vector_store.upsert(
                [
                    VectorRecord(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        member_id=chunk.member_id,    # NEW
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ]
            )
```

- [ ] **Step 3: 跑现有 KbService 测试看哪里破了**

Run: `cd backend && pytest tests/test_kb_service.py -v`
Expected: 会因为 FakeVectorStore 没 member_id、chunker 签名变了而 fail。

- [ ] **Step 4: 修测试 FakeVectorStore（接受新 search 签名 + 接收 member_id）**

在 `backend/tests/test_kb_service.py` 修改 `FakeRepository` 不用动（接口没变）。
但 `InMemoryVectorStore()` 直接用，加 member_id 后 `search` 强制要求 member_id。

修改 `test_upload_pdf_builds_pages_chunks_and_vectors`：
```python
def test_upload_pdf_builds_pages_chunks_and_vectors(tmp_path):
    repository = FakeRepository()
    vector_store = InMemoryVectorStore()
    service = KbService(
        repository=repository,
        pdf_extractor=FakePdfExtractor(),
        ocr_client=FakeOcrClient(),
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        upload_dir=tmp_path,
    )

    result = service.upload_pdf(
        file_name="report.pdf",
        content=b"%PDF-1.4 fake",
        member_id="mem_1",
    )

    assert result.status == "ready"
    assert result.page_count == 1
    assert result.chunk_count == 1
    assert repository.documents[0].file_name == "report.pdf"
    assert (tmp_path / result.document_id / "thumbnail.png").read_bytes() == b"fake png"
    assert repository.pages[0].page_no == 1
    assert "骨密度" in repository.chunks[0].content
    assert repository.chunks[0].member_id == "mem_1"   # NEW
    assert len(vector_store.records) == 1
    assert vector_store.records[0].member_id == "mem_1"  # NEW
```

对另外两个测试 `test_upload_pdf_uses_cloud_ocr_when_pdf_text_is_too_short` 和 `test_upload_pdf_marks_document_failed_when_processing_fails` 同样加上 `member_id="mem_1"` 参数。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/test_kb_service.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/kb_service.py backend/app/services/chunker.py backend/tests/test_kb_service.py
git commit -m "feat(kb): KbService.upload_pdf 写入 member_id 到 chunks/vectors"
```

---

## Task 4: kb_repository.save_chunks 带 member_id + 新增按 member 过滤方法

**Files:**
- Modify: `backend/app/repositories/kb_repository.py`
- Test: `backend/tests/test_kb_repository.py`

- [ ] **Step 1: 写失败的 repository 测试**

```python
# backend/tests/test_kb_repository.py
from datetime import datetime

import pytest

from app.models.kb import KbChunk, KbDocument
from app.models.member import Member
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.services.chunker import TextChunk


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.session import Base
    from app.core.config import settings

    engine = create_engine(settings.test_database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_members(session):
    session.add_all([
        Member(member_id="mem_1", name="张三", relation="本人", created_at=datetime.utcnow()),
        Member(member_id="mem_2", name="李四", relation="父亲", created_at=datetime.utcnow()),
    ])
    session.commit()


def test_save_chunks_writes_member_id(db_session):
    _seed_members(db_session)
    repo = SqlAlchemyKbRepository(db_session)
    repo.create_document(KbDocument(
        document_id="doc_1", file_name="r.pdf", file_path="/tmp/r.pdf",
        file_size=10, member_id="mem_1", status="processing",
    ))
    repo.save_chunks([
        TextChunk(chunk_id="c1", document_id="doc_1", member_id="mem_1", page_no=1, content="text"),
    ])

    db_session.expire_all()
    chunk = db_session.query(KbChunk).filter(KbChunk.chunk_id == "c1").one()
    assert chunk.member_id == "mem_1"


def test_list_documents_by_member_filters_correctly(db_session):
    _seed_members(db_session)
    repo = SqlAlchemyKbRepository(db_session)
    repo.create_document(KbDocument(
        document_id="doc_1", file_name="r1.pdf", file_path="/tmp/r1.pdf",
        file_size=10, member_id="mem_1", status="ready",
    ))
    repo.create_document(KbDocument(
        document_id="doc_2", file_name="r2.pdf", file_path="/tmp/r2.pdf",
        file_size=10, member_id="mem_2", status="ready",
    ))

    docs_mem_1 = repo.list_documents_by_member("mem_1")

    ids = [d.document_id for d in docs_mem_1]
    assert ids == ["doc_1"]


def test_get_chunks_by_member_returns_only_that_member(db_session):
    _seed_members(db_session)
    repo = SqlAlchemyKbRepository(db_session)
    repo.create_document(KbDocument(
        document_id="doc_1", file_name="r1.pdf", file_path="/tmp/r1.pdf",
        file_size=10, member_id="mem_1", status="ready",
    ))
    repo.create_document(KbDocument(
        document_id="doc_2", file_name="r2.pdf", file_path="/tmp/r2.pdf",
        file_size=10, member_id="mem_2", status="ready",
    ))
    repo.save_chunks([
        TextChunk(chunk_id="c1", document_id="doc_1", member_id="mem_1", page_no=1, content="a"),
        TextChunk(chunk_id="c2", document_id="doc_2", member_id="mem_2", page_no=1, content="b"),
    ])

    chunks = repo.get_chunks_by_member("mem_1")

    chunk_ids = [c.chunk_id for c in chunks]
    assert chunk_ids == ["c1"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/test_kb_repository.py -v`
Expected: FAIL with `AttributeError` / `TypeError`（save_chunks 不接 member_id、list_documents_by_member 不存在）

- [ ] **Step 3: 改 save_chunks 写入 member_id**

修改 `backend/app/repositories/kb_repository.py` 的 `save_chunks`：
```python
    def save_chunks(self, chunks) -> None:
        self.db.add_all(
            [
                KbChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    member_id=chunk.member_id,    # NEW
                    page_no=chunk.page_no,
                    content=chunk.content,
                )
                for chunk in chunks
            ]
        )
        self.db.commit()
```

- [ ] **Step 4: 新增 list_documents_by_member**

在 `backend/app/repositories/kb_repository.py` 添加：
```python
    def list_documents_by_member(self, member_id: str) -> list[KbDocument]:
        documents = (
            self.db.query(KbDocument)
            .filter(KbDocument.member_id == member_id)
            .order_by(KbDocument.created_at.desc())
            .all()
        )
        self._attach_member_info(documents)
        return documents
```

- [ ] **Step 5: 新增 get_chunks_by_member**

在 `backend/app/repositories/kb_repository.py` 添加：
```python
    def get_chunks_by_member(self, member_id: str) -> list[KbChunk]:
        return (
            self.db.query(KbChunk)
            .filter(KbChunk.member_id == member_id)
            .order_by(KbChunk.document_id.asc(), KbChunk.page_no.asc(), KbChunk.id.asc())
            .all()
        )
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && pytest tests/test_kb_repository.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/repositories/kb_repository.py backend/tests/test_kb_repository.py
git commit -m "feat(kb): repository 按 member_id 过滤接口"
```

---

## Task 5: SearchRequest 加 member_id 必填 + search 路由校验过滤

**Files:**
- Modify: `backend/app/schemas/kb.py`
- Modify: `backend/app/api/kb.py`
- Modify: `backend/tests/test_api_kb.py`

- [ ] **Step 1: 改 SearchRequest**

修改 `backend/app/schemas/kb.py`：
```python
class SearchRequest(BaseModel):
    query: str
    member_id: str        # NEW, required
    top_k: int = 5
```

- [ ] **Step 2: 改 search 路由校验 + 过滤**

修改 `backend/app/api/kb.py` 的 `search` 函数：
```python
@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    embedding_service: DashScopeEmbeddingService = Depends(get_embedding_service),
    vector_store=Depends(get_vector_store),
):
    member_repository = SqlAlchemyMemberRepository(db)
    if not member_repository.exists_by_member_id(request.member_id):
        raise HTTPException(status_code=400, detail="家人不存在")
    embedding = embedding_service.embed(request.query)
    hits = vector_store.search(embedding, request.top_k, member_id=request.member_id)
    repository = SqlAlchemyKbRepository(db)
    chunks = repository.get_chunks_by_ids([hit.chunk_id for hit in hits])
    score_by_chunk = {hit.chunk_id: hit.score for hit in hits}
    return SearchResponse(
        items=[
            SearchResultItem(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                page_no=chunk.page_no,
                content=chunk.content,
                score=score_by_chunk.get(chunk.chunk_id, 0.0),
            )
            for chunk in chunks
        ]
    )
```

- [ ] **Step 3: 跑现有 API 测试看哪里破了**

Run: `cd backend && pytest tests/test_api_kb.py -v`
Expected: `test_kb_search_endpoint_returns_chunk_content` 会 fail（缺 member_id、FakeVectorStore 接口签名变了）

- [ ] **Step 4: 修测试 FakeVectorStore 和现有测试**

修改 `backend/tests/test_api_kb.py`：
```python
class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k, member_id=None):
        self.calls.append({"member_id": member_id})
        if member_id != "mem_1":
            return []
        return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]


class FakeEmbeddingService:
    def embed(self, text):
        return [1.0, 0.0]


class FakeMemberRepository:
    def __init__(self):
        self.calls = []

    def exists_by_member_id(self, member_id):
        self.calls.append(member_id)
        return member_id == "mem_1"
```

并在 `FakeDb` 里加入 member 概念（用 SQLAlchemy 实测库时不需要；这里因为用 FakeDb 所以注入 MemberRepository）：

`search` 路由现在依赖 `SqlAlchemyMemberRepository`，需要给 `get_db` override 注入带 member repository 的 fake db。简化做法：**直接复用 FakeDb 同时承担 member 查询**。

把 `FakeDb` 增加：
```python
class FakeDb:
    ...
    def __init__(self):
        ...
        self.members = {"mem_1": SimpleNamespace(member_id="mem_1", name="张三", relation="本人")}
        self.deleted = []

    def exists_by_member_id(self, member_id):
        return member_id in self.members
```

但 search 路由直接 new `SqlAlchemyMemberRepository(db)`，不是 `db.exists_by_member_id`。所以需要另一种方式：**新建一个 FakeMemberRepository 类，让搜索路由在测试时直接替换为 FakeMemberRepository**。

最简方案：把 `get_member_repository` 抽成一个 dependency（与 `get_db` 平行），测试时 override。当前路由直接 new `SqlAlchemyMemberRepository(db)`，先按这个做：

实际**最小变更**：保留 `SqlAlchemyMemberRepository(db)` 直接 new，但在 conftest 或测试里**使用真实 db_session fixture 测搜索**。FakeDb 测试只测不需要 member 校验的部分。

新增一个集成测试 `test_kb_search_requires_member_id`，用 db_session fixture 真实测试：

```python
def test_kb_search_requires_member_id(db_session):
    """搜索必须传 member_id（Pydantic 校验）。"""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)

    response = client.post("/api/kb/search", json={"query": "骨密度", "top_k": 5})

    assert response.status_code == 422
```

`test_kb_search_endpoint_returns_chunk_content` 改成调用 `FakeDb`，但因为 FakeDb 没有 member 校验逻辑，**删掉这个测试**，改为在 db_session fixture 下写真实的 happy path 测试：

```python
def test_kb_search_filters_by_member_id(db_session):
    """搜索按 member_id 过滤：传 mem_2 只返回 mem_2 的 chunk。"""
    # 在 db_session 里 seed 一个 member + 两个 documents/chunks（属于不同 member）
    # ... (用真实 SQLAlchemy)
    
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    client = TestClient(app)
    
    response = client.post("/api/kb/search", json={"query": "骨密度", "member_id": "mem_2", "top_k": 5})
    
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0  # mem_2 没有 chunk
```

实现细节：FakeVectorStore 需要感知 member_id 过滤（见上面 FakeVectorStore 新实现）。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/test_api_kb.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量测试看现有 API 测试有没有破**

Run: `cd backend && pytest -v`
Expected: 应全绿

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/kb.py backend/app/api/kb.py backend/tests/test_api_kb.py
git commit -m "feat(kb): search API 强制 member_id + 校验"
```

---

## Task 6: KbSearchTool 强制 member_id + 白名单校验

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试**

修改 `backend/tests/test_agent_tools.py`：
```python
class FakeEmbeddingService:
    def embed(self, text):
        return [1.0]


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(self, query_embedding, top_k, member_id=None):
        self.calls.append(member_id)
        if member_id == "mem_1":
            return [type("Hit", (), {"chunk_id": "chunk_1", "score": 0.9})()]
        return []


def test_kb_search_tool_requires_member_id():
    repository = FakeKbRepository()
    tool = KbSearchTool(repository, FakeEmbeddingService(), FakeVectorStore(), allowed_member_ids=["mem_1"])

    result = tool.search(query="爸爸血糖", member_id="mem_1")

    assert "文档：妈妈体检报告" in result


def test_kb_search_tool_rejects_unknown_member_id():
    tool = KbSearchTool(FakeKbRepository(), FakeEmbeddingService(), FakeVectorStore(), allowed_member_ids=["mem_1"])

    result = tool.search(query="爸爸血糖", member_id="mem_unknown")

    assert "Error" in result
    assert "不在可用家人列表中" in result


def test_kb_search_tool_filters_by_member_id_in_vector_store():
    vector_store = FakeVectorStore()
    tool = KbSearchTool(FakeKbRepository(), FakeEmbeddingService(), vector_store, allowed_member_ids=["mem_1", "mem_2"])

    tool.search(query="爸爸血糖", member_id="mem_2")

    assert vector_store.calls == ["mem_2"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/test_agent_tools.py -v`
Expected: FAIL with `TypeError: __init__() missing 1 required positional argument: 'allowed_member_ids'`

- [ ] **Step 3: 重写 KbSearchTool**

修改 `backend/app/services/agent_tools.py`：
```python
from app.repositories.kb_repository import SqlAlchemyKbRepository


class KbSearchTool:
    def __init__(
        self,
        repository: SqlAlchemyKbRepository,
        embedding_service,
        vector_store,
        allowed_member_ids: list[str],
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.allowed_member_ids = set(allowed_member_ids)

    def search(self, query: str, member_id: str, top_k: int = 5) -> str:
        if not member_id:
            return "Error: 必须传入 member_id"
        if member_id not in self.allowed_member_ids:
            return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        try:
            embedding = self.embedding_service.embed(query)
            hits = self.vector_store.search(embedding, top_k, member_id=member_id)
            chunks = self.repository.get_chunks_by_ids([hit.chunk_id for hit in hits])
        except Exception as exc:
            return f"Error: 检索失败 {exc}"

        parts = []
        for index, chunk in enumerate(chunks, start=1):
            document = self.repository.get_document(chunk.document_id)
            title = document.title or document.file_name if document is not None else chunk.document_id
            parts.append(
                f"[报告片段 {index}]\n"
                f"文档：{title}\n"
                f"页码：{chunk.page_no}\n"
                f"内容：{chunk.content}"
            )
        return "\n\n".join(parts)
```

注意：移除 `should_search` 关键字短路（决策权完全交给 LLM）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat(agent): KbSearchTool 强制 member_id + 白名单"
```

---

## Task 7: LangChainAgentRunner 注入成员列表到 system prompt

**Files:**
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: 改 SYSTEM_PROMPT 让其接收动态成员列表**

修改 `backend/app/services/langchain_agent.py`：
```python
SYSTEM_PROMPT_TEMPLATE = """你是粮达健康的家庭健康 Agent 管家。
你可以基于用户上传的健康报告和用户当前问题提供健康建议。

要求：
1. 用简体中文回答。
2. 不做诊断，不替代医生。
3. 对异常指标给出就医提醒。
4. 如果引用报告内容，说明来自哪份报告或页码。
5. 回答要像管家，简洁、具体、可执行。
6. 当信息不足时，直接说明还缺什么信息。
7. 检索用户报告时必须调用 kb_search 工具，并显式传入 member_id。
   不要在不知道是哪位家人的情况下盲猜。
{members_block}
9. 跨家人对比问题（"全家血脂怎么样"）需要分别对每位家人调用 kb_search，然后合成答案。
"""


def _build_members_block(members: list) -> str:
    if not members:
        return "8. 当前没有可用家人，无法检索报告。\n"
    lines = ["8. 当前可用家人列表："]
    for index, member in enumerate(members, start=1):
        member_id = member.member_id if hasattr(member, "member_id") else member["member_id"]
        name = member.name if hasattr(member, "name") else member["name"]
        relation = member.relation if hasattr(member, "relation") else member.get("relation", "")
        lines.append(f"   {index}. {name}（member_id={member_id}，{relation}）")
    lines.append('   如果用户问"爸爸"对应到相应的家人，以此类推。')
    lines.append('   如果指代不明（如"他/她"无上下文），必须先反问"您说的\'他/她\'是指哪位家人？"，不要主动猜测。')
    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: 改 LangChainAgentRunner 接受 member_provider**

修改 `backend/app/services/langchain_agent.py`：
```python
class LangChainAgentRunner:
    def __init__(self, kb_tool=None, member_provider=None):
        self.kb_tool = kb_tool
        self.member_provider = member_provider or (lambda: [])

    def _system_prompt(self) -> str:
        members = self.member_provider()
        return SYSTEM_PROMPT_TEMPLATE.format(members_block=_build_members_block(members))

    def _ensure_api_key(self) -> None:
        if not settings.llm_api_key:
            raise LlmConfigError("未配置模型 API Key")

    def _append_kb_context(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        ...  # 保留原实现（这一步用于把检索到的片段拼到 user message，已经包含 kb_search 工具返回）
```

- [ ] **Step 3: 改 _agent() 使用动态 system prompt**

修改 `_agent()`：
```python
    def _agent(self):
        from langchain.agents import create_agent

        return create_agent(
            model=self._model(),
            tools=self._tools(),
            system_prompt=self._system_prompt(),
        )
```

（注意：每次 `run` / `stream` 都会重新构造 agent 以拿到最新的成员列表。）

- [ ] **Step 4: 写失败测试**

修改 `backend/tests/test_langchain_agent.py`：
```python
from app.services.langchain_agent import (
    LangChainAgentRunner,
    SYSTEM_PROMPT_TEMPLATE,
    _build_members_block,
)


class FakeMember:
    def __init__(self, member_id, name, relation):
        self.member_id = member_id
        self.name = name
        self.relation = relation


def test_build_members_block_with_members():
    members = [
        FakeMember("mem_1", "张三", "本人"),
        FakeMember("mem_2", "张三爸", "父亲"),
    ]
    block = _build_members_block(members)

    assert "mem_1" in block
    assert "张三" in block
    assert "本人" in block
    assert "mem_2" in block
    assert "父亲" in block


def test_build_members_block_empty():
    block = _build_members_block([])

    assert "当前没有可用家人" in block


def test_runner_system_prompt_includes_member_list():
    runner = LangChainAgentRunner(
        member_provider=lambda: [FakeMember("mem_1", "张三", "本人")],
    )

    prompt = runner._system_prompt()

    assert "张三" in prompt
    assert "mem_1" in prompt
    assert "必须先反问" in prompt


def test_runner_system_prompt_empty_when_no_members():
    runner = LangChainAgentRunner(member_provider=lambda: [])

    prompt = runner._system_prompt()

    assert "当前没有可用家人" in prompt
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/test_langchain_agent.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量测试看 agent_api 是否破**

Run: `cd backend && pytest tests/test_agent_api.py -v`
Expected: 大概率 FAIL（KbSearchTool 构造函数签名变了、新 agent 装配要更新）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "feat(agent): system prompt 动态注入成员列表"
```

---

## Task 8: agent.py 装配 member_provider

**Files:**
- Modify: `backend/app/api/agent.py`
- Modify: `backend/tests/test_agent_api.py`

- [ ] **Step 1: 改 get_agent_runner 注入 member_provider**

修改 `backend/app/api/agent.py` 的 `get_agent_runner`：
```python
from app.repositories.member_repository import SqlAlchemyMemberRepository

def get_agent_runner(
    db: Session = Depends(get_db),
    embedding_service=Depends(get_embedding_service),
    vector_store=Depends(get_vector_store),
):
    member_repository = SqlAlchemyMemberRepository(db)

    def member_provider():
        members = member_repository.list_members()
        return [
            type("M", (), {
                "member_id": m.member_id,
                "name": m.name,
                "relation": m.relation,
            })()
            for m in members
        ]

    return LangChainAgentRunner(
        kb_tool=KbSearchTool(
            repository=SqlAlchemyKbRepository(db),
            embedding_service=embedding_service,
            vector_store=vector_store,
            allowed_member_ids=[m.member_id for m in member_provider()],
        ),
        member_provider=member_provider,
    )
```

- [ ] **Step 2: 修测试**

`test_agent_api.py` 里如果有 KbSearchTool 构造相关测试，需要更新为传 `allowed_member_ids`。检查并修复。

- [ ] **Step 3: 跑测试确认通过**

Run: `cd backend && pytest tests/test_agent_api.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/agent.py backend/tests/test_agent_api.py
git commit -m "feat(agent): api 装配 member_provider + 白名单"
```

---

## Task 9: member_repository.delete_member 校验 KB 引用

**Files:**
- Modify: `backend/app/repositories/member_repository.py`
- Modify: `backend/tests/test_api_members.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_api_members.py` 添加（如果该测试文件不存在则创建）：
```python
def test_delete_member_rejects_when_has_kb_references(db_session):
    """有 KB 引用时拒绝删除。"""
    from app.models.kb import KbDocument
    from app.models.member import Member
    from datetime import datetime

    db_session.add(Member(
        member_id="mem_1", name="张三", relation="本人",
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.add(KbDocument(
        document_id="doc_1", file_name="r.pdf", file_path="/tmp/r.pdf",
        file_size=10, member_id="mem_1", status="ready",
    ))
    db_session.commit()

    from app.repositories.member_repository import SqlAlchemyMemberRepository
    repo = SqlAlchemyMemberRepository(db_session)
    result = repo.delete_member("mem_1")

    assert result is None  # 拒绝删除
    assert db_session.query(Member).filter(Member.member_id == "mem_1").one_or_none() is not None


def test_delete_member_succeeds_when_no_kb_references(db_session):
    from app.models.member import Member
    from datetime import datetime

    db_session.add(Member(
        member_id="mem_1", name="张三", relation="本人",
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    db_session.commit()

    from app.repositories.member_repository import SqlAlchemyMemberRepository
    repo = SqlAlchemyMemberRepository(db_session)
    result = repo.delete_member("mem_1")

    assert result is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/test_api_members.py -v`
Expected: 第二个测试 PASS，第一个 FAIL（目前 delete_member 不检查引用）

- [ ] **Step 3: 改 delete_member 校验引用**

修改 `backend/app/repositories/member_repository.py` 的 `delete_member`：
```python
    def delete_member(self, member_id: str) -> Member | None:
        member = self.get_member(member_id)
        if member is None:
            return None
        referenced = (
            self.db.query(KbDocument)
            .filter(KbDocument.member_id == member_id)
            .first()
        )
        if referenced is not None:
            return None  # 拒绝删除
        self.db.delete(member)
        self.db.commit()
        return member
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && pytest tests/test_api_members.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/repositories/member_repository.py backend/tests/test_api_members.py
git commit -m "feat(member): 删除 member 校验 KB 引用"
```

---

## Task 10: 迁移脚本 migrate_kb_member_binding.py

**Files:**
- Create: `backend/scripts/migrate_kb_member_binding.py`
- Create: `backend/tests/test_migrate_kb_member_binding.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_migrate_kb_member_binding.py
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base
from app.models.kb import KbChunk, KbDocument
from app.models.member import Member
from app.services.chunker import TextChunk


@pytest.fixture
def db_session():
    engine = create_engine(settings.test_database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_member(session, member_id, name):
    session.add(Member(
        member_id=member_id, name=name, relation="本人",
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    ))
    session.commit()


def _seed_document(session, document_id, member_id, patient_name):
    session.add(KbDocument(
        document_id=document_id, file_name="r.pdf", file_path="/tmp/r.pdf",
        file_size=10, member_id=member_id, status="ready",
        patient_name=patient_name, title="t",
    ))
    session.add(KbChunk(
        chunk_id=f"chunk_{document_id}", document_id=document_id,
        member_id=member_id, page_no=1, content="text",
    ))
    session.commit()


def test_migrate_remaps_default_to_matched_member(db_session, tmp_path):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "张三")

    from app.scripts.migrate_kb_member_binding import migrate
    report = migrate(db_session, dry_run=False)

    assert report["matched"] == 1
    assert report["unmatched"] == 0
    db_session.expire_all()
    doc = db_session.query(KbDocument).filter(KbDocument.document_id == "doc_1").one()
    assert doc.member_id == "mem_zhang"
    chunk = db_session.query(KbChunk).filter(KbChunk.chunk_id == "chunk_doc_1").one()
    assert chunk.member_id == "mem_zhang"


def test_migrate_reports_unmatched(db_session, tmp_path):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "钱七")  # 姓名不匹配

    from app.scripts.migrate_kb_member_binding import migrate
    report = migrate(db_session, dry_run=False)

    assert report["matched"] == 0
    assert report["unmatched"] == 1


def test_migrate_is_idempotent(db_session, tmp_path):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "张三")

    from app.scripts.migrate_kb_member_binding import migrate
    migrate(db_session, dry_run=False)
    report = migrate(db_session, dry_run=False)

    assert report["matched"] == 0
    assert report["unmatched"] == 0


def test_migrate_dry_run_does_not_modify(db_session, tmp_path):
    _seed_member(db_session, "mem_zhang", "张三")
    _seed_document(db_session, "doc_1", "default", "张三")

    from app.scripts.migrate_kb_member_binding import migrate
    report = migrate(db_session, dry_run=True)

    assert report["matched"] == 1
    db_session.expire_all()
    doc = db_session.query(KbDocument).filter(KbDocument.document_id == "doc_1").one()
    assert doc.member_id == "default"  # 未修改
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/test_migrate_kb_member_binding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.scripts.migrate_kb_member_binding'`

- [ ] **Step 3: 创建 `backend/app/scripts/__init__.py`**（空文件）

- [ ] **Step 4: 创建 `backend/scripts/migrate_kb_member_binding.py`**

```python
"""将历史脏数据（member_id IS NULL OR member_id = 'default'）按 patient_name 严格匹配回填。

用法：
    python -m backend.scripts.migrate_kb_member_binding            # 实际迁移
    python -m backend.scripts.migrate_kb_member_binding --dry-run  # 只预览不写库
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.models.kb import KbChunk, KbDocument
from app.models.member import Member


@dataclass
class MigrationReport:
    matched: list[tuple[str, str]] = field(default_factory=list)   # (document_id, new_member_id)
    unmatched: list[str] = field(default_factory=list)             # [document_id]
    ambiguous: list[str] = field(default_factory=list)             # [document_id]
    failed: list[tuple[str, str]] = field(default_factory=list)    # (document_id, error_message)

    def to_dict(self) -> dict:
        return {
            "matched": len(self.matched),
            "unmatched": len(self.unmatched),
            "ambiguous": len(self.ambiguous),
            "failed": len(self.failed),
            "details": {
                "matched": self.matched,
                "unmatched": self.unmatched,
                "ambiguous": self.ambiguous,
                "failed": self.failed,
            },
        }


def _ensure_member_id_column(db: Session) -> None:
    """如果 kb_chunks.member_id 列不存在，添加（线上库增量升级用）。"""
    inspector_results = db.execute(text("SHOW COLUMNS FROM kb_chunks")).fetchall()
    column_names = {row[0] for row in inspector_results}
    if "member_id" not in column_names:
        db.execute(text(
            "ALTER TABLE kb_chunks ADD COLUMN member_id VARCHAR(64) NULL, "
            "ADD INDEX idx_kb_chunks_member_id (member_id)"
        ))
        db.commit()


def _find_member_by_name(db: Session, patient_name: str | None) -> list[str]:
    if not patient_name:
        return []
    members = (
        db.query(Member)
        .filter(Member.name == patient_name)
        .all()
    )
    return [m.member_id for m in members]


def migrate(db: Session, dry_run: bool = False) -> dict:
    report = MigrationReport()
    _ensure_member_id_column(db)

    dirty_documents = (
        db.query(KbDocument)
        .filter((KbDocument.member_id.is_(None)) | (KbDocument.member_id == "default"))
        .all()
    )

    for document in dirty_documents:
        try:
            candidates = _find_member_by_name(db, document.patient_name)
            if len(candidates) == 1:
                new_member_id = candidates[0]
                if not dry_run:
                    document.member_id = new_member_id
                    db.query(KbChunk).filter(
                        KbChunk.document_id == document.document_id
                    ).update({KbChunk.member_id: new_member_id})
                    db.commit()
                report.matched.append((document.document_id, new_member_id))
            elif len(candidates) > 1:
                report.ambiguous.append(document.document_id)
            else:
                report.unmatched.append(document.document_id)
        except Exception as exc:
            db.rollback()
            report.failed.append((document.document_id, str(exc)))

    return report.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 KB 历史脏数据")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写库")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = migrate(db, dry_run=args.dry_run)
        print(f"匹配成功: {report['matched']}")
        print(f"未匹配:   {report['unmatched']}")
        print(f"重名歧义: {report['ambiguous']}")
        print(f"失败:     {report['failed']}")
        if report["matched"] or report["unmatched"] or report["ambiguous"] or report["failed"]:
            print()
            print("明细：")
            for category, items in report["details"].items():
                if items:
                    print(f"  [{category}] {items}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/test_migrate_kb_member_binding.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量测试**

Run: `cd backend && pytest -v`
Expected: 应全绿

- [ ] **Step 7: 提交**

```bash
git add backend/scripts/migrate_kb_member_binding.py backend/app/scripts/__init__.py backend/tests/test_migrate_kb_member_binding.py
git commit -m "feat(kb): 历史脏数据按 patient_name 迁移脚本"
```

---

## Task 11: 前端 - kb.ts searchKb 签名变更

**Files:**
- Modify: `frontend/src/api/kb.ts`

- [ ] **Step 1: 改 searchKb 签名**

修改 `frontend/src/api/kb.ts`：
```ts
export async function searchKb(query: string, memberId: string, topK: number): Promise<SearchResult[]> {
  const response = await fetch(`${API_BASE}/api/kb/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, member_id: memberId, top_k: topK })
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? '搜索失败');
  }
  const data = await response.json();
  return data.items;
}
```

- [ ] **Step 2: 跑构建确认无类型错**

Run: `cd frontend && npx tsc --noEmit`
Expected: 会发现 `KbSearchPanel.tsx` 的 `searchKb(query, topK)` 调用不匹配（下一步修）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/kb.ts
git commit -m "feat(frontend): searchKb 签名加 memberId 必填"
```

---

## Task 12: 前端 - KbSearchPanel 接受 memberId prop

**Files:**
- Modify: `frontend/src/components/KbSearchPanel.tsx`

- [ ] **Step 1: 改 KbSearchPanel**

修改 `frontend/src/components/KbSearchPanel.tsx`：
```tsx
import { Search } from 'lucide-react';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { searchKb, type SearchResult } from '../api/kb';

type Props = {
  memberId: string;
};

export function KbSearchPanel({ memberId }: Props) {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const searchMutation = useMutation<SearchResult[], Error>({
    mutationFn: () => searchKb(query, memberId, topK),
    enabled: false
  });

  return (
    <section className="search-panel">
      <div className="search-row">
        <div className="search-input-wrap">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索报告内容，例如：骨密度异常"
          />
        </div>
        <select value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
          <option value={5}>Top 5</option>
          <option value={10}>Top 10</option>
        </select>
        <button className="btn-primary" onClick={() => searchMutation.mutate()} disabled={!query || !memberId || searchMutation.isPending}>
          搜索
        </button>
      </div>

      {searchMutation.isError && <div className="error-box">{searchMutation.error.message}</div>}

      <div className="search-results">
        {searchMutation.data?.map((item) => (
          <article key={item.chunk_id} className="result-card">
            <div className="result-meta">
              第 {item.page_no} 页 · score {item.score.toFixed(2)}
            </div>
            <p>{item.content}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 跑构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: 仍有错误（`ReportsPage.tsx` 没传 memberId），下个 Task 修。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/KbSearchPanel.tsx
git commit -m "feat(frontend): KbSearchPanel 接受 memberId"
```

---

## Task 13: 前端 - ReportsPage 集成 KbSearchPanel

**Files:**
- Modify: `frontend/src/pages/ReportsPage.tsx`

- [ ] **Step 1: 在 ReportsPage 中条件渲染 KbSearchPanel**

修改 `frontend/src/pages/ReportsPage.tsx`，在 `ReportToolbar` 之后添加：
```tsx
import { KbSearchPanel } from '../components/KbSearchPanel';

// ... 在 return 里：
{!documentsQuery.isLoading && family !== 'all' && (
  <KbSearchPanel memberId={family} />
)}
{family === 'all' && (
  <div className="empty-state">选择一位家人后即可搜索报告内容</div>
)}
```

- [ ] **Step 2: 跑构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/ReportsPage.tsx
git commit -m "feat(frontend): ReportsPage 集成 KbSearchPanel"
```

---

## Task 14: 前端 - ChatPage 上传改成 UploadReportDialog

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: 引入 UploadReportDialog**

修改 `frontend/src/pages/ChatPage.tsx`：
```tsx
import { UploadReportDialog } from '../components/UploadReportDialog';

// 在 ChatPage 函数里新增 state：
const [uploadDialogOpen, setUploadDialogOpen] = useState(false);

// 修 uploadMutation：
const uploadMutation = useMutation({
  mutationFn: async ({ file, memberId }: { file: File; memberId: string }) => {
    const result = await uploadPdf({ file, memberId });
    return { file, result };
  },
  onMutate: () => {
    setUploadError(null);
    setSendError(null);
  },
  onError: (error: Error) => setUploadError(error.message),
});

// 修 handleUpload —— 改为只打开 dialog：
function handleUpload(_file: File) {
  setUploadDialogOpen(true);
}

// 在 handleRemoveAttachment / submit 提交时附件仍然能发送（memberId 已绑定到附件 metadata）。
```

- [ ] **Step 2: 修 ChatInput 调用，改为弹 dialog**

检查 `ChatInput` 的 `onUpload` 回调如何接收 file。打开 dialog 后用户选家人+文件 → 回调里调 `uploadPdf({ file, memberId })` → 成功后将附件加入消息输入区。

具体：在 dialog 的 `onUpload` 回调里执行：
```tsx
<UploadReportDialog
  open={uploadDialogOpen}
  uploading={uploadMutation.isPending}
  error={uploadError}
  onClose={() => setUploadDialogOpen(false)}
  onUpload={(payload) => {
    uploadMutation.mutate(payload, {
      onSuccess: (data) => {
        const newAttachment: Attachment = {
          name: data.file.name,
          url: `已上传报告：${data.file.name}`,
          type: 'pdf'
        };
        setAttachments((prev) => [...prev, newAttachment]);
        setUploadDialogOpen(false);
      }
    });
  }}
/>
```

- [ ] **Step 3: 跑构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "fix(frontend): ChatPage 上传用 UploadReportDialog 选家人"
```

---

## Task 15: 端到端回归

**Files:**
- Run: 全部测试 + 前端构建

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && pytest -v`
Expected: 全绿

- [ ] **Step 2: 前端构建**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 全绿

- [ ] **Step 3: 手工跑迁移脚本（dry-run）在测试库**

Run:
```bash
cd backend
python -m scripts.migrate_kb_member_binding --dry-run
```
Expected: 输出 "匹配成功: 0 / 未匹配: 0 / 重名歧义: 0 / 失败: 0"（测试库无脏数据）

- [ ] **Step 4: 写 E2E 集成测试**

新建 `backend/tests/test_e2e_member_isolation.py`：
```python
"""端到端验证：上传 → 检索 → 隔离正确性。"""


def test_search_only_returns_target_member_chunks(db_session):
    """跨家人检索：A 上传的内容不会被 B 的检索召回。"""
    # seed 两个 member
    # 用真实 KbService 上传两份 PDF 到不同 member（mock pdf_extractor/embedding）
    # 用真实 /api/kb/search 搜索 member_2 → 只应返回 member_2 的 chunks
    ...
```

实现时复用 Task 4 / Task 5 的 fixture 模式 + 真实 FastAPI app + mock pdf_extractor。

- [ ] **Step 5: 跑 E2E 测试**

Run: `cd backend && pytest tests/test_e2e_member_isolation.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/tests/test_e2e_member_isolation.py
git commit -m "test(kb): 端到端家人隔离集成测试"
```

---

## Self-Review Notes

**Spec coverage:**
- ✅ §2 数据模型：Task 1, 2
- ✅ §3 API：Task 5
- ✅ §4 Agent 集成：Task 6, 7, 8
- ✅ §5 前端：Task 11, 12, 13, 14
- ✅ §6 迁移脚本：Task 10
- ✅ §7 错误处理 / §8 测试：覆盖在每个 Task 内
- ✅ §9 改动文件清单：所有文件均触达

**Type consistency check:**
- `VectorRecord(chunk_id, document_id, member_id, embedding)` — Task 2 定义，Task 3 使用，Task 6 Agent 不直接用（间接通过 vector store.search）
- `InMemoryVectorStore.search(embedding, top_k, member_id)` — Task 2 定义，Task 5 API 路由、Task 6 agent_tools 都按此签名调用
- `KbSearchTool(repository, embedding_service, vector_store, allowed_member_ids)` — Task 6 定义，Task 8 调用
- `LangChainAgentRunner(kb_tool=None, member_provider=None)` — Task 7 定义，Task 8 调用
- `searchKb(query: string, memberId: string, topK: number)` — Task 11 定义，Task 12 使用
- `KbSearchPanel({ memberId: string })` — Task 12 定义，Task 13 使用

**Potential gaps:**
- Task 5 中用 `FakeDb` 测试 `FakeMemberRepository` 的部分比较曲折，简化为真实 db_session 测试
- Task 8 中 `member_provider` 闭包返回 `type('M', (), ...)` 匿名对象，测试已对齐（FakeMember 模拟同样形态）
- Milvus 升级路径未单独写 Task —— 实际 MilvusVectorStore.search 已改（Task 2 Step 5），schema 升级的运行时路径在 deploy 时按 `add_collection_field` 走；如需自动化，可后续加 Task "Milvus 启动时自动 add_field"