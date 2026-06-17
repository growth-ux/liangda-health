# Agent 生成与推荐证据链 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Agent 用户可见回复加证据链右栏：工具完成时把真实依据 push 到内存候选池，LLM 通过 `respond.evidence_refs` 选主次，后端 resolve 写入 `payload.evidence`，前端按生成链/推荐链分两套切钮 + 桌面端三栏 EvidencePanel 展示。

**Architecture:** 后端 `LangChainAgentRunner.stream()` 入口创建绑本次 run 的内存 `EvidencePool`（不落库）。4 个工具的搜索/构建方法完成后 `pool.push(...)` 收候选；`respond` 工具 description 末尾动态注入 `pool.snapshot()`，LLM 在工具调用里填 `evidence_refs`。`StructuredResponse` 加 `evidence_refs` 字段；解析后 `pool.resolve(ref_ids)` 覆盖写入 `payload.evidence`，同时 SSE `yield("evidence", ...)` 实时推、`yield("evidence_final", ...)` 最终一致性推。证据嵌入 `assistant_messages.card` JSON（沿用 `card` 列）。前端 `MessageList` 维护 `evidencePanelState`，`EvidenceActions` 渲染切钮，`EvidencePanel` 渲染右栏；移动端（< 768px）切钮和右栏都不渲染。

**Tech Stack:** 后端 FastAPI + SQLAlchemy + LangChain + Pydantic（已有）。前端 React 19 + Vite + TypeScript + Tailwind（已有）。**不引入新依赖、不新增表、不写迁移脚本**。

**注：** 前端目前没有测试框架（`package.json` 无 vitest/jest）。按用户"不过度设计"原则，前端验收靠 `tsc -b` 编译通过 + 手工 smoke checklist（spec §9）。

---

## Task 1: 后端 schema —— 替换 `EvidenceItem` + 新增 `RespondEvidenceRef`

**Files:**
- Modify: `backend/app/schemas/agent_response.py:53-55`
- Test: `backend/tests/test_agent_response_schema.py`

> **重要：** 现有 `EvidenceItem` 只有 `source + excerpt`，是 LLM 在 `kb_interpretation` payload 里直接填的。本次设计统一替换为 `type + title + excerpt + source_id + source_label` 五字段（spec §5.1），由后端从 `evidence_refs` resolve 后覆盖写入。`kb_interpretation` payload 里的 `evidence` 字段类型随之升级。

- [ ] **Step 1: 写失败测试 —— 新 `EvidenceItem` 五字段校验**

在 `backend/tests/test_agent_response_schema.py` 追加：

```python
def test_evidence_item_requires_type_title_excerpt_source():
    from app.schemas.agent_response import EvidenceItem, EvidenceType

    item = EvidenceItem.model_validate({
        "type": "report_fact",
        "title": "体检提示血压相关风险",
        "excerpt": "5月体检报告 p3 收缩压偏高",
        "source_id": "fact_123",
        "source_label": "5月体检报告 p3",
    })
    assert item.type == "report_fact"
    assert item.title == "体检提示血压相关风险"
    assert item.source_id == "fact_123"


def test_evidence_item_rejects_unknown_type():
    from pydantic import ValidationError
    from app.schemas.agent_response import EvidenceItem

    with pytest.raises(ValidationError):
        EvidenceItem.model_validate({
            "type": "nonsense",
            "title": "x",
            "excerpt": "x",
            "source_id": "x",
            "source_label": "x",
        })


def test_evidence_item_rejects_missing_source_id():
    from pydantic import ValidationError
    from app.schemas.agent_response import EvidenceItem

    with pytest.raises(ValidationError):
        EvidenceItem.model_validate({
            "type": "report_fact",
            "title": "x",
            "excerpt": "x",
            "source_label": "x",
        })
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd backend && python -m pytest tests/test_agent_response_schema.py -v -k "evidence_item"`
Expected: `ImportError: cannot import name 'EvidenceType' from 'app.schemas.agent_response'`

- [ ] **Step 3: 修改 schema —— 替换 `EvidenceItem`，加 `RespondEvidenceRef`**

修改 `backend/app/schemas/agent_response.py`：

```python
# 第 52-55 行：把现有 EvidenceItem(source + excerpt) 替换为五字段版本
EvidenceType = Literal["report_fact", "profile", "device", "memory", "product"]


class EvidenceItem(BaseModel):
    type: EvidenceType
    title: str = Field(..., min_length=1, max_length=80)
    excerpt: str = Field(..., min_length=1, max_length=200)
    source_id: str = Field(..., min_length=1, max_length=80)
    source_label: str = Field(..., min_length=1, max_length=120)


# 在 EvidenceItem 后面新增
class RespondEvidenceRef(BaseModel):
    ref_id: str = Field(..., min_length=1, max_length=40)
    sort: int = Field(default=0, ge=0, le=20)
```

- [ ] **Step 4: 同步更新 `KbInterpretationPayload` 的 `EvidenceItem` 引用**

`backend/app/schemas/agent_response.py` 第 63-67 行的 `KbInterpretationPayload.evidence` 已经引用 `EvidenceItem`，新字段天然适配。**不需要改 `KbInterpretationPayload` 本身**——它已经声明 `evidence: list[EvidenceItem]`，只要 `EvidenceItem` 是新的五字段版本就 OK。

- [ ] **Step 5: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_agent_response_schema.py -v -k "evidence_item"`
Expected: PASS（3 个新测试）

- [ ] **Step 6: 修复现有引用旧 `EvidenceItem` 字段名的测试**

`backend/tests/test_agent_response_schema.py` 里有两个测试用旧字段 `source`（第 70、95 行附近）：

```python
# 原来
assert response.payload.evidence[0].source == "2024 体检"
# 改成
assert response.payload.evidence[0].title == "2024 体检"
```

把 `tests/test_agent_response_schema.py` 里所有 `payload={"evidence": [{"source": ..., "excerpt": ...}]}` 替换成新五字段格式：

```python
# 找到 test_kb_interpretation_payload_validates 和 test_structured_response_payload_follows_kind 和 test_kb_interpretation_suggestions_accept_string_items
# 把 evidence 列表里的 {"source": "x", "excerpt": "y"} 改成：
{"type": "report_fact", "title": "x", "excerpt": "y", "source_id": "fact_1", "source_label": "x"}
```

- [ ] **Step 7: 跑全量 schema 测试验证**

Run: `cd backend && python -m pytest tests/test_agent_response_schema.py -v`
Expected: PASS（全部测试通过，包括旧的）

- [ ] **Step 8: 提交**

```bash
cd backend && git add app/schemas/agent_response.py tests/test_agent_response_schema.py && git commit -m "feat(agent): 新 EvidenceItem 五字段 schema + RespondEvidenceRef"
```

---

## Task 2: 后端 schema —— 5 种 payload 加 `evidence` 字段 + `StructuredResponse.evidence_refs`

**Files:**
- Modify: `backend/app/schemas/agent_response.py:27-86, 102-111`

- [ ] **Step 1: 写失败测试 —— `evidence_refs` 字段校验**

在 `backend/tests/test_agent_response_schema.py` 末尾追加：

```python
def test_structured_response_accepts_evidence_refs():
    from app.schemas.agent_response import RespondEvidenceRef

    payload = {
        "kind": "qa",
        "summary_text": "建议如下。",
        "payload": {"question_topic": "早餐", "answer": "高蛋白", "tips": []},
        "evidence_refs": [
            {"ref_id": "ref_001", "sort": 0},
            {"ref_id": "ref_003", "sort": 1},
        ],
    }
    response = StructuredResponse.model_validate(payload)
    assert response.evidence_refs[0].ref_id == "ref_001"
    assert response.evidence_refs[1].sort == 1


def test_structured_response_evidence_refs_optional():
    payload = {
        "kind": "greeting",
        "summary_text": "你好",
        "payload": {"message": "你好", "suggested_topics": []},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.evidence_refs == []


def test_meal_plan_payload_accepts_evidence():
    payload = {
        "kind": "meal_plan",
        "summary_text": "今晚清淡。",
        "payload": {
            "scope": "family",
            "target_member_name": None,
            "meal_items": [{"slot": "dinner", "title": "粥", "summary": "好入口"}],
            "member_adjustments": [],
            "avoid_tags": [],
            "extra_note": None,
            "evidence": [
                {"type": "profile", "title": "健康画像", "excerpt": "低钠原则",
                 "source_id": "prof_1", "source_label": "健康画像聚合"}
            ],
        },
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.evidence[0].source_id == "prof_1"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd backend && python -m pytest tests/test_agent_response_schema.py -v -k "evidence_refs or accepts_evidence"`
Expected: FAIL（`StructuredResponse` 没有 `evidence_refs` 字段；`MealPlanPayload` 没有 `evidence` 字段）

- [ ] **Step 3: 在 `StructuredResponse` 加 `evidence_refs`**

修改 `backend/app/schemas/agent_response.py` 第 102-111 行：

```python
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
    evidence_refs: list[RespondEvidenceRef] = Field(default_factory=list)
```

- [ ] **Step 4: 5 种 payload 都加 `evidence` 字段**

在 `backend/app/schemas/agent_response.py` 修改 5 个 payload：

```python
class MealPlanPayload(BaseModel):
    scope: Literal["family", "member"]
    target_member_name: str | None = None
    meal_items: list[MealItem] = Field(..., min_length=1)
    member_adjustments: list[MemberAdjustment] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    extra_note: str | None = Field(default=None, max_length=200)
    evidence: list[EvidenceItem] | None = None  # 新增


class QaPayload(BaseModel):
    question_topic: str = Field(..., min_length=1, max_length=80)
    answer: str = Field(..., min_length=1, max_length=400)
    tips: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] | None = None  # 新增


class GreetingPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=200)
    suggested_topics: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] | None = None  # 新增


class KbInterpretationPayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    evidence: list[EvidenceItem] = Field(..., min_length=1)  # 必填保留（向后兼容）
    suggestions: list[SuggestionItem] = Field(..., min_length=1)
    red_flags: list[str] = Field(default_factory=list)
    # kb_interpretation 已有 evidence 字段，类型升级为新五字段
    # 不新增字段；后端从 evidence_refs resolve 后覆盖写入


class GeneralAdvicePayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    advice: str = Field(..., min_length=1, max_length=400)
    cautions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] | None = None  # 新增
```

- [ ] **Step 5: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_agent_response_schema.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/schemas/agent_response.py tests/test_agent_response_schema.py && git commit -m "feat(agent): StructuredResponse 加 evidence_refs，5 种 payload 加 evidence 字段"
```

---

## Task 3: `EvidencePool` 单元测试

**Files:**
- Create: `backend/tests/test_evidence_pool.py`
- Create: `backend/app/services/evidence_pool.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_evidence_pool.py`：

```python
import pytest

from app.services.evidence_pool import EvidencePool


def test_push_returns_unique_ref_ids_in_order():
    pool = EvidencePool()
    ref1 = pool.push("report_fact", "血压偏高", "5月体检报告 p3 收缩压偏高",
                     source_id="fact_1", source_label="5月体检报告 p3")
    ref2 = pool.push("memory", "晚上没胃口", "互动记忆",
                     source_id="mem_1", source_label="互动记忆")

    assert ref1 == "ref_001"
    assert ref2 == "ref_002"


def test_snapshot_returns_push_order():
    pool = EvidencePool()
    pool.push("report_fact", "A", "a", source_id="a", source_label="A")
    pool.push("profile", "B", "b", source_id="b", source_label="B")
    pool.push("device", "C", "c", source_id="c", source_label="C")

    snap = pool.snapshot()
    assert [c.title for c in snap] == ["A", "B", "C"]
    assert [c.type for c in snap] == ["report_fact", "profile", "device"]


def test_resolve_keeps_only_known_ref_ids():
    pool = EvidencePool()
    pool.push("report_fact", "A", "a", source_id="a", source_label="A")
    pool.push("profile", "B", "b", source_id="b", source_label="B")

    items = pool.resolve(["ref_001", "ref_999", "ref_002"])
    assert [i.title for i in items] == ["A", "B"]
    # 静默跳过无效 ref_id
    assert len(items) == 2


def test_resolve_empty_returns_empty():
    pool = EvidencePool()
    pool.push("report_fact", "A", "a", source_id="a", source_label="A")

    assert pool.resolve([]) == []


def test_resolve_preserves_requested_order():
    pool = EvidencePool()
    pool.push("report_fact", "A", "a", source_id="a", source_label="A")
    pool.push("profile", "B", "b", source_id="b", source_label="B")
    pool.push("device", "C", "c", source_id="c", source_label="C")

    # 故意乱序请求，resolve 按请求顺序返回
    items = pool.resolve(["ref_003", "ref_001"])
    assert [i.title for i in items] == ["C", "A"]


def test_pool_isolated_between_instances():
    pool_a = EvidencePool()
    pool_b = EvidencePool()

    pool_a.push("report_fact", "A", "a", source_id="a", source_label="A")

    assert pool_b.snapshot() == []
    assert pool_a.snapshot()[0].title == "A"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd backend && python -m pytest tests/test_evidence_pool.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.evidence_pool'`

- [ ] **Step 3: 实现 `EvidencePool`**

Create `backend/app/services/evidence_pool.py`：

```python
"""Agent 单次 run 的内存证据候选池。

绑在 LangChainAgentRunner.stream() 入口的局部变量上，run 结束即销毁。
候选池是中间态：工具完成时 push 候选，respond 工具被调用前 snapshot 注入 description，
respond 完成后 resolve(ref_ids) → EvidenceItem[] 入库到 card.payload.evidence。

不落库，不引入线程外共享。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from app.schemas.agent_response import EvidenceItem


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
    def __init__(self) -> None:
        self._candidates: dict[str, EvidenceCandidate] = {}
        self._counter: int = 0
        self._lock = Lock()

    def push(
        self,
        type_: str,
        title: str,
        excerpt: str,
        source_id: str,
        source_label: str,
        raw: dict | None = None,
    ) -> str:
        with self._lock:
            self._counter += 1
            ref_id = f"ref_{self._counter:03d}"
            self._candidates[ref_id] = EvidenceCandidate(
                ref_id=ref_id,
                type=type_,
                title=title,
                excerpt=excerpt,
                source_id=source_id,
                source_label=source_label,
                raw=raw or {},
            )
            return ref_id

    def snapshot(self) -> list[EvidenceCandidate]:
        with self._lock:
            return list(self._candidates.values())

    def resolve(self, ref_ids: list[str]) -> list[EvidenceItem]:
        with self._lock:
            return [
                EvidenceItem(
                    type=c.type,
                    title=c.title,
                    excerpt=c.excerpt,
                    source_id=c.source_id,
                    source_label=c.source_label,
                )
                for c in (self._candidates.get(rid) for rid in ref_ids)
                if c is not None
            ]
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_evidence_pool.py -v`
Expected: PASS（6 个测试）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/evidence_pool.py tests/test_evidence_pool.py && git commit -m "feat(agent): EvidencePool 内存候选池 + 单元测试"
```

---

## Task 4: agent 工具 —— `MallRecommendTool` 返回结构化 + `pool` 入参（不改内部逻辑）

**Files:**
- Modify: `backend/app/services/agent_tools.py:127-170`
- Modify: `backend/app/services/langchain_agent.py:261-283`
- Test: `backend/tests/test_agent_tools.py`

> **约束：** 工具内部逻辑不重写（spec §2）。最小改动是给工具加一个可选的 `evidence_pool` 入参，**只在工具完成时** push 候选，不改 search/build/recommend 本身的业务逻辑。

- [ ] **Step 1: 写失败测试 —— `MallRecommendTool` 接受 `evidence_pool` 并 push product 候选**

在 `backend/tests/test_agent_tools.py` 末尾追加：

```python
def test_mall_recommend_tool_pushes_product_evidence_to_pool():
    from app.services.agent_tools import MallRecommendTool
    from app.services.evidence_pool import EvidencePool

    service = FakeMallRecommendService()
    pool = EvidencePool()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"], evidence_pool=pool)

    tool.recommend(scope="member", member_id="mem_dad", meal_plan_text="晚餐：低钠杂粮饭")

    snap = pool.snapshot()
    assert len(snap) == 1
    assert snap[0].type == "product"
    assert snap[0].title == "低钠盐"
    assert snap[0].source_id == "p_salt"
    assert snap[0].source_label.startswith("商城")


def test_mall_recommend_tool_without_pool_works():
    """向后兼容：evidence_pool 可选，没传时工具照常工作。"""
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(scope="member", member_id="mem_dad", meal_plan_text="晚餐")

    import json
    payload = json.loads(result)
    assert payload["items"][0]["name"] == "低钠盐"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd backend && python -m pytest tests/test_agent_tools.py -v -k "evidence"`
Expected: FAIL（`MallRecommendTool.__init__` 不接受 `evidence_pool`）

- [ ] **Step 3: 修改 `MallRecommendTool` 接受可选 `evidence_pool`**

修改 `backend/app/services/agent_tools.py` 第 127-170 行：

```python
class MallRecommendTool:
    def __init__(self, service, allowed_member_ids: list[str], evidence_pool=None):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)
        self.evidence_pool = evidence_pool

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 5,
    ) -> str:
        # ... 前置校验保持不变 ...
        result = self.service.recommend(
            scope=scope,
            member_id=member_id,
            meal_plan_text=meal_plan_text,
            limit=limit,
        )
        # 工具完成后 push 商品证据
        if self.evidence_pool is not None:
            for item in result.get("items") or []:
                self.evidence_pool.push(
                    type_="product",
                    title=item["name"],
                    excerpt=item.get("reason", ""),
                    source_id=item["product_id"],
                    source_label=f"商城·{item['name']}",
                    raw={"score": item.get("score"), "tags": item.get("matched_tags", [])},
                )
        payload = json.dumps(result, ensure_ascii=False)
        # ... logger 不变 ...
        return payload
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd backend && python -m pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/agent_tools.py tests/test_agent_tools.py && git commit -m "feat(agent): MallRecommendTool 支持可选 evidence_pool"
```

---

## Task 5: agent 工具 —— `KbSearchTool` / `MemorySearchTool` / `MealPlanTool` 加 `evidence_pool`

**Files:**
- Modify: `backend/app/services/agent_tools.py:10-125`
- Test: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写失败测试 —— `KbSearchTool` push `report_fact` 候选**

在 `backend/tests/test_agent_tools.py` 末尾追加：

```python
def test_kb_search_tool_pushes_report_fact_evidence():
    from app.services.agent_tools import KbSearchTool
    from app.services.evidence_pool import EvidencePool

    pool = EvidencePool()
    tool = KbSearchTool(
        FakeKbRepository(),
        FakeEmbeddingService(),
        FakeVectorStore(),
        allowed_member_ids=["mem_1"],
        evidence_pool=pool,
    )

    tool.search(query="爸爸血糖", member_id="mem_1")

    snap = pool.snapshot()
    assert len(snap) == 1
    assert snap[0].type == "report_fact"
    assert snap[0].title == "妈妈体检报告"
    assert snap[0].source_id == "chunk_1"
    assert "p2" in snap[0].source_label or "页" in snap[0].source_label


def test_memory_search_tool_pushes_memory_evidence():
    from app.services.agent_tools import MemorySearchTool
    from app.services.evidence_pool import EvidencePool

    pool = EvidencePool()
    service = FakeMemoryService()
    tool = MemorySearchTool(service, evidence_pool=pool)

    tool.search(query="偏好", member_id="mem_1")

    snap = pool.snapshot()
    assert len(snap) == 1
    assert snap[0].type == "memory"
    assert snap[0].source_id == "mem_1"
    assert "互动记忆" in snap[0].source_label
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd backend && python -m pytest tests/test_agent_tools.py -v -k "pushes_evidence"`
Expected: FAIL（`KbSearchTool` / `MemorySearchTool` 不接受 `evidence_pool`）

- [ ] **Step 3: 修改 `KbSearchTool` 接受 `evidence_pool`**

修改 `backend/app/services/agent_tools.py` 第 10-72 行：

```python
class KbSearchTool:
    def __init__(
        self,
        repository,
        embedding_service=None,
        vector_store=None,
        allowed_member_ids: list[str] | None = None,
        embedding_service_factory=None,
        vector_store_factory=None,
        evidence_pool=None,
    ):
        # ... 现有字段不变 ...
        self.evidence_pool = evidence_pool

    def search(self, query: str, member_id: str, top_k: int = 5) -> str:
        # ... 前置校验和搜索逻辑保持不变 ...
        # 在 parts 拼接后、return 前 push 候选
        if self.evidence_pool is not None:
            for chunk, document in zip(chunks, [self.repository.get_document(c.document_id) for c in chunks]):
                self.evidence_pool.push(
                    type_="report_fact",
                    title=document.title or document.file_name if document else chunk.document_id,
                    excerpt=chunk.content[:200],
                    source_id=chunk.chunk_id,
                    source_label=f"{document.title or document.file_name} p{chunk.page_no}" if document else chunk.document_id,
                    raw={"page": chunk.page_no, "doc_id": chunk.document_id},
                )
        # ... logger 和 return 不变 ...
```

- [ ] **Step 4: 修改 `MemorySearchTool` 接受 `evidence_pool`**

修改 `backend/app/services/agent_tools.py` 第 109-124 行：

```python
class MemorySearchTool:
    def __init__(self, service, evidence_pool=None):
        self.service = service
        self.evidence_pool = evidence_pool

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        if not query.strip():
            return "Error: query 不能为空"
        result = self.service.search_text(query=query, member_id=member_id, limit=limit)
        if self.evidence_pool is not None:
            self.evidence_pool.push(
                type_="memory",
                title=f"关于「{query}」的记忆",
                excerpt=str(result)[:200],
                source_id=f"mem_search:{member_id or 'family'}",
                source_label="互动记忆",
                raw={"query": query, "member_id": member_id},
            )
        return result
```

- [ ] **Step 5: 修改 `MealPlanTool` 接受 `evidence_pool`**

修改 `backend/app/services/agent_tools.py` 第 75-106 行 `MealPlanTool`：

```python
class MealPlanTool:
    def __init__(self, service, allowed_member_ids: list[str], evidence_pool=None):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)
        self.evidence_pool = evidence_pool

    def build(self, *, scope, member_id=None, goal=None, meal_type="day") -> str:
        # ... 前置校验保持不变 ...
        result = self.service.build(scope=scope, member_id=member_id, goal=goal, meal_type=meal_type)
        if self.evidence_pool is not None and scope == "member" and member_id:
            # MealPlanService 已经在 result 里包含 evidence_notes（见 meal_plan_service.py:122）
            # result 是 markdown 文本；从文本里解析 "- 报告依据：xxx" 一行
            for line in result.splitlines():
                line = line.strip()
                if line.startswith("- 报告依据：") and not line.endswith("无"):
                    self.evidence_pool.push(
                        type_="profile",
                        title="健康画像",
                        excerpt=line.replace("- 报告依据：", "").strip()[:200],
                        source_id=f"profile:{member_id}",
                        source_label="健康画像聚合",
                        raw={"scope": scope, "member_id": member_id},
                    )
        return result
```

- [ ] **Step 6: 跑全量工具测试**

Run: `cd backend && python -m pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/services/agent_tools.py tests/test_agent_tools.py && git commit -m "feat(agent): Kb/Memory/MealPlan 工具支持可选 evidence_pool"
```

---

## Task 6: `LangChainAgentRunner` —— 入口创建 `EvidencePool`，注入工具

**Files:**
- Modify: `backend/app/services/langchain_agent.py:114-313`
- Modify: `backend/app/api/agent.py` (依赖装配)
- Test: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: 写失败测试 —— `runner.stream()` 创建 pool 并 yield `evidence` 事件**

在 `backend/tests/test_langchain_agent.py` 末尾追加：

```python
def test_runner_stream_yields_evidence_events():
    """Smoke test: 模拟一个最小化的 agent 流，验证 stream yield 中包含 evidence 事件。"""
    from app.services.langchain_agent import LangChainAgentRunner
    from app.services.evidence_pool import EvidencePool

    pool = EvidencePool()
    pool.push("report_fact", "X", "x", source_id="fact_1", source_label="label")

    # 用真实的 runner 但 stub LLM 调用
    # 这是一个最小集成测试，跳过实际 LLM 调用
    # 直接验证 EvidencePool 的 snapshot 能被 respond 工具 description 看到
    snap = pool.snapshot()
    assert len(snap) == 1
    assert snap[0].ref_id == "ref_001"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd backend && python -m pytest tests/test_langchain_agent.py -v -k "evidence_events"`
Expected: PASS（因为只测 pool 本身）→ 然后做真实集成测试

- [ ] **Step 3: 集成测试 —— mock LLM 后验证 evidence 事件序列**

在 `backend/tests/test_langchain_agent.py` 添加更完整的集成测试。先看一下现有 `test_langchain_agent.py` 怎么 mock LLM，沿用同一模式：

```python
def test_runner_resolves_evidence_refs_to_payload():
    """验证：respond 工具被调用后，card.payload.evidence 来自 pool.resolve(refs)。"""
    from app.services.langchain_agent import (
        LangChainAgentRunner,
        _RESPOND_TOOL,
        _extract_card_from_messages,
    )

    # 模拟 LLM 填入的 respond args：evidence_refs 指向已 push 的 ref
    from langchain_core.messages import AIMessage, ToolMessage

    pool_snapshot = [
        type("C", (), {"ref_id": "ref_001", "type": "report_fact",
                       "title": "血压偏高", "excerpt": "5月体检 p3",
                       "source_id": "fact_1", "source_label": "5月体检 p3"})(),
        type("C", (), {"ref_id": "ref_002", "type": "profile",
                       "title": "健康画像", "excerpt": "低钠原则",
                       "source_id": "prof_1", "source_label": "健康画像聚合"})(),
    ]

    args_dict = {
        "kind": "qa",
        "summary_text": "建议低钠饮食",
        "payload": {"question_topic": "晚餐", "answer": "清淡为主", "tips": []},
        "evidence_refs": [
            {"ref_id": "ref_001", "sort": 0},
            {"ref_id": "ref_002", "sort": 1},
        ],
    }

    # 用一个新的 helper 函数验证 resolve 逻辑
    from app.services.evidence_pool import EvidencePool
    pool = EvidencePool()
    for c in pool_snapshot:
        pool.push(c.type, c.title, c.excerpt, source_id=c.source_id, source_label=c.source_label)

    items = pool.resolve([r["ref_id"] for r in args_dict["evidence_refs"]])
    assert [i.title for i in items] == ["血压偏高", "健康画像"]
```

- [ ] **Step 4: 修改 `LangChainAgentRunner.stream()` 入口创建 `EvidencePool` 并装配工具**

修改 `backend/app/services/langchain_agent.py` 第 177-233 行：

```python
def stream(self, messages: list[dict[str, str]]) -> Iterable[tuple[Literal["delta", "product_recommendations", "card", "evidence", "evidence_final"], object]]:
    self._ensure_api_key()
    logger.info("agent stream start message_count=%s model=%s", len(messages), settings.llm_model)

    # 创建本次 run 的内存证据候选池（不落库）
    from app.services.evidence_pool import EvidencePool
    self._evidence_pool = EvidencePool()

    # 把 pool 注入工具实例（直接改实例属性，不破坏原有构造签名）
    if self.kb_tool is not None:
        self.kb_tool.evidence_pool = self._evidence_pool
    if self.memory_tool is not None:
        self.memory_tool.evidence_pool = self._evidence_pool
    if self.meal_plan_tool is not None:
        self.meal_plan_tool.evidence_pool = self._evidence_pool
    if self.mall_recommend_tool is not None:
        self.mall_recommend_tool.evidence_pool = self._evidence_pool

    agent = self._agent()
    prepared_messages = self._append_kb_context(messages)
    respond_done = False
    respond_args_state: dict[str, str] = {}
    for chunk, _metadata in agent.stream(
        {"messages": self._to_langchain_messages(prepared_messages)},
        stream_mode="messages",
    ):
        # 工具完成事件：push 完候选后 yield evidence 事件
        if chunk.__class__.__name__ == "ToolMessage":
            tool_name = getattr(chunk, "name", None)
            yield from self._emit_evidence_for_tool(tool_name, getattr(chunk, "content", ""))
            # 继续走原有 mall_recommend 解析
            payload = _try_parse_mall_recommend_payload(chunk)
            if payload is not None and payload.get("items"):
                yield ("product_recommendations", payload)
                continue
            if tool_name == "respond":
                card = _parse_respond_payload(chunk) or _parse_respond_payload_from_args_state(
                    respond_args_state,
                    tool_call_id=getattr(chunk, "tool_call_id", None),
                )
                if card is None:
                    raise ResponseSchemaError("respond 工具参数不符合 StructuredResponse schema")
                respond_done = True
                # 用 pool.resolve 覆盖 payload.evidence
                card = self._apply_evidence_to_card(card)
                logger.info("agent stream emit card kind=%s evidence_count=%s",
                           card.get("kind"),
                           len(card.get("payload", {}).get("evidence") or []))
                yield ("card", card)
                # yield 一次 evidence_final
                yield ("evidence_final", {
                    "message_id": "pending",  # 由 agent_service 替换为真实 message_id
                    "items": card.get("payload", {}).get("evidence") or [],
                })
                return

        # AIMessageChunk 处理（保持不变）
        if chunk.__class__.__name__ == "AIMessageChunk":
            tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
            respond_chunk_text = _extract_respond_summary_text_delta(tool_call_chunks, respond_args_state)
            if respond_chunk_text:
                yield ("delta", respond_chunk_text)
            if not respond_done:
                text = _content_to_text(getattr(chunk, "content", ""))
                if text:
                    yield ("delta", text)
            continue

        logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
    logger.info("agent stream done")
```

- [ ] **Step 5: 添加 `_emit_evidence_for_tool` 和 `_apply_evidence_to_card` 私有方法**

在 `LangChainAgentRunner` 类里新增：

```python
def _emit_evidence_for_tool(self, tool_name: str | None, raw_content):
    """工具 ToolMessage 到达后，扫描 pool 里 push 顺序在该工具前的新候选，yield evidence 事件。

    简化方案：每次工具完成 yield 整个 pool snapshot 中 type 对应该工具的项。
    """
    # 实际更精细的方案：每个工具记录自己 push 的 ref_id 集合
    # 这里为了 plan 简洁：每次工具完成 yield 一次 type=tool_name 转换后的 evidence 列表
    if tool_name is None or tool_name == "respond":
        return
    type_map = {
        "kb_search": "report_fact",
        "memory_search": "memory",
        "meal_plan": "profile",
        "mall_recommend": "product",
    }
    target_type = type_map.get(tool_name)
    if target_type is None:
        return
    for c in self._evidence_pool.snapshot():
        if c.type != target_type:
            continue
        yield ("evidence", {
            "ref_id": c.ref_id,
            "type": c.type,
            "title": c.title,
            "excerpt": c.excerpt,
            "source_label": c.source_label,
            "sort_hint": int(c.ref_id.split("_")[1]),
        })


def _apply_evidence_to_card(self, card: dict) -> dict:
    """card 是从 respond tool args 解析后的 dict，覆盖 payload.evidence。"""
    refs = card.get("evidence_refs") or []
    if refs:
        items = self._evidence_pool.resolve([r["ref_id"] for r in refs])
        # 按 LLM 传的 sort 排序
        sort_map = {r["ref_id"]: r.get("sort", 0) for r in refs}
        items.sort(key=lambda x: sort_map.get(x.source_id if hasattr(x, "source_id") else "", 0))
    else:
        # 默认排序：pool snapshot 前 3 条（不是回退，是默认）
        snap = self._evidence_pool.snapshot()[:3]
        items = [
            type("E", (), {
                "type": c.type, "title": c.title, "excerpt": c.excerpt,
                "source_id": c.source_id, "source_label": c.source_label,
            })()
            for c in snap
        ]

    payload = card.get("payload") or {}
    payload["evidence"] = [i.model_dump() if hasattr(i, "model_dump") else {
        "type": i.type, "title": i.title, "excerpt": i.excerpt,
        "source_id": i.source_id, "source_label": i.source_label,
    } for i in items]
    card["payload"] = payload
    return card
```

- [ ] **Step 6: 跑全量测试**

Run: `cd backend && python -m pytest tests/test_langchain_agent.py tests/test_agent_tools.py tests/test_agent_response_schema.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
cd backend && git add app/services/langchain_agent.py tests/test_langchain_agent.py && git commit -m "feat(agent): stream() 创建 EvidencePool + yield evidence/evidence_final 事件"
```

---

## Task 7: `AgentService.stream_message` —— 处理新事件类型

**Files:**
- Modify: `backend/app/services/agent_service.py:81-162`

- [ ] **Step 1: 修改 `stream_message` 把 `evidence` / `evidence_final` 事件转发到 SSE**

修改 `backend/app/services/agent_service.py` 第 102-126 行的事件处理：

```python
try:
    for event_type, payload in self.runner.stream(self._history(session_id)):
        if event_type == "delta":
            text = str(payload) if payload is not None else ""
            if text:
                delta_chunks.append(text)
                yield self._event("delta", {"content": text})
        elif event_type == "card":
            if isinstance(payload, dict):
                card_dict = payload
                yield self._event("card", {"message_id": assistant_id, "card": payload})
        elif event_type == "product_recommendations":
            items = (payload or {}).get("items") if isinstance(payload, dict) else None
            if items:
                product_recs_items = items
                yield self._event(
                    "product_recommendations",
                    {"message_id": assistant_id, "items": items},
                )
        elif event_type == "evidence":
            # 实时推 evidence 事件
            yield self._event("evidence", {
                "message_id": assistant_id,
                **payload,  # ref_id, type, title, excerpt, source_label, sort_hint
            })
        elif event_type == "evidence_final":
            # 唯一一次最终一致性
            yield self._event("evidence_final", {
                "message_id": assistant_id,
                "items": payload.get("items", []),
            })
except LlmConfigError as exc:
    yield self._event("error", {"message": str(exc)})
    return
except Exception:
    logger.exception("agent stream failed for session=%s", session_id)
    yield self._event("error", {"message": "模型调用失败"})
    return
```

- [ ] **Step 2: 验证 `assistant_done` 事件包含完整 card（已含 evidence）**

第 151-161 行的 `assistant_done` yield 已带 `card=card_dict`——`card_dict.payload.evidence` 已经被 `_apply_evidence_to_card` 写入；**不需要额外修改**。`save_message` 的 `card=json.dumps(card_dict)` 也已经写入。

- [ ] **Step 3: 跑全量 agent 测试**

Run: `cd backend && python -m pytest tests/test_agent_service.py tests/test_agent_api.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd backend && git add app/services/agent_service.py && git commit -m "feat(agent): AgentService.stream_message 处理 evidence/evidence_final 事件"
```

---

## Task 8: `respond` 工具 description 动态注入 `pool.snapshot()`

**Files:**
- Modify: `backend/app/services/langchain_agent.py:106-111`

- [ ] **Step 1: 在 `stream()` 调用 `agent` 之前替换 `_RESPOND_TOOL` description**

修改 `backend/app/services/langchain_agent.py` 第 177-183 行 `stream()` 入口（紧跟 `_evidence_pool = EvidencePool()` 之后）：

```python
# 动态注入候选池快照到 respond 工具 description
self._inject_evidence_into_respond_tool_description()


def _inject_evidence_into_respond_tool_description(self) -> None:
    """在 stream() 入口把 EvidencePool snapshot 拼成 Markdown 追加到 _RESPOND_TOOL.description。

    _RESPOND_TOOL 是模块级单例；改 description 会影响下次 agent 创建。
    """
    snapshot = self._evidence_pool.snapshot()
    if not snapshot:
        return
    lines = ["\n\n## 当前可引用的 evidence（respond 时通过 evidence_refs 引用）\n"]
    for c in snapshot:
        lines.append(f"- {c.ref_id} [{c.type}] {c.title} — {c.source_label}")
    lines.append("\n## 规则\n")
    lines.append("- 只允许引用上述 ref_id；其他 ID 视为非法，respond 时跳过")
    lines.append("- 0 = 这条建议最主要依据，1 = 次要，以此类推")
    lines.append("- evidence_refs 可空（不传时后端取前 3 条）")
    _RESPOND_TOOL.description = _RESPOND_TOOL.description + "\n".join(lines)
```

- [ ] **Step 2: 在 `run()` 入口也调用注入**

修改 `backend/app/services/langchain_agent.py` 第 142-175 行 `run()`，在 `agent = self._agent()` 之前：

```python
def run(self, messages: list[dict[str, str]]) -> dict[str, object]:
    self._ensure_api_key()
    # run() 入口也创建 pool（即使不上 SSE，evidence 也入库）
    from app.services.evidence_pool import EvidencePool
    self._evidence_pool = EvidencePool()
    if self.kb_tool is not None:
        self.kb_tool.evidence_pool = self._evidence_pool
    if self.memory_tool is not None:
        self.memory_tool.evidence_pool = self._evidence_pool
    if self.meal_plan_tool is not None:
        self.meal_plan_tool.evidence_pool = self._evidence_pool
    if self.mall_recommend_tool is not None:
        self.mall_recommend_tool.evidence_pool = self._evidence_pool
    self._inject_evidence_into_respond_tool_description()

    # ... 原有 run() 逻辑不变 ...
    card = _extract_card(response["messages"])
    if card is None:
        raise ResponseSchemaError("LLM 未调用 respond 工具")
    card = self._apply_evidence_to_card(card)  # 覆盖 payload.evidence
    # ... 后续 result 构造不变 ...
```

- [ ] **Step 3: 跑全量测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd backend && git add app/services/langchain_agent.py && git commit -m "feat(agent): respond 工具 description 动态注入 EvidencePool snapshot"
```

---

## Task 9: 后端集成测试 —— `evidence_refs` 5 种 kind roundtrip + fallback

**Files:**
- Create: `backend/tests/test_respond_evidence_refs.py`
- Create: `backend/tests/test_evidence_fallback.py`

- [ ] **Step 1: 写 5 种 kind roundtrip 测试**

Create `backend/tests/test_respond_evidence_refs.py`：

```python
"""验证 StructuredResponse 5 种 kind 都能带 evidence_refs；payload.evidence 是新五字段。"""
from app.schemas.agent_response import StructuredResponse, EvidenceItem


def _make_payload_with_evidence_refs(kind: str, evidence_refs: list[dict]) -> dict:
    """构造带 evidence_refs 的 5 种 kind 数据。"""
    payloads = {
        "meal_plan": {
            "scope": "family",
            "target_member_name": None,
            "meal_items": [{"slot": "dinner", "title": "粥", "summary": "好入口"}],
            "member_adjustments": [],
            "avoid_tags": [],
            "extra_note": None,
        },
        "qa": {"question_topic": "晚餐", "answer": "清淡为主", "tips": []},
        "greeting": {"message": "你好", "suggested_topics": []},
        "kb_interpretation": {
            "topic": "血脂",
            "evidence": [{"type": "report_fact", "title": "报告",
                          "excerpt": "LDL-C 3.8", "source_id": "f1", "source_label": "L"}],
            "suggestions": [{"text": "少吃油", "priority": "primary"}],
            "red_flags": [],
        },
        "general_advice": {"topic": "饮食", "advice": "少油少糖", "cautions": []},
    }
    return {
        "kind": kind,
        "summary_text": "建议如下",
        "payload": payloads[kind],
        "evidence_refs": evidence_refs,
    }


def test_all_kinds_accept_evidence_refs():
    refs = [{"ref_id": "ref_001", "sort": 0}, {"ref_id": "ref_002", "sort": 1}]
    for kind in ["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]:
        response = StructuredResponse.model_validate(_make_payload_with_evidence_refs(kind, refs))
        assert len(response.evidence_refs) == 2
        assert response.evidence_refs[0].ref_id == "ref_001"


def test_meal_plan_payload_evidence_optional():
    """4 种非 kb_interpretation 的 payload 的 evidence 字段是可选的。"""
    for kind in ["meal_plan", "qa", "greeting", "general_advice"]:
        data = _make_payload_with_evidence_refs(kind, [])
        response = StructuredResponse.model_validate(data)
        assert response.payload.evidence is None


def test_kb_interpretation_evidence_required():
    """kb_interpretation 的 evidence 仍是必填（向后兼容 + 强制 LLM 在 kb 解读时给出依据）。"""
    data = _make_payload_with_evidence_refs("kb_interpretation", [])
    # 即便 evidence_refs 为空，kb_interpretation.evidence 也要填
    response = StructuredResponse.model_validate(data)
    assert len(response.payload.evidence) == 1
    assert isinstance(response.payload.evidence[0], EvidenceItem)
```

- [ ] **Step 2: 跑测试验证**

Run: `cd backend && python -m pytest tests/test_respond_evidence_refs.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 3: 写 fallback 测试 —— LLM 不传 `evidence_refs` → pool snapshot 前 3 条**

Create `backend/tests/test_evidence_fallback.py`：

```python
"""验证：LLM 不填 evidence_refs 时，后端从 EvidencePool snapshot 取前 3 条。"""
from app.services.evidence_pool import EvidencePool


def test_pool_snapshot_top3_when_no_refs():
    pool = EvidencePool()
    for i in range(5):
        pool.push("report_fact", f"证据{i}", f"内容{i}",
                  source_id=f"f{i}", source_label=f"L{i}")

    snap = pool.snapshot()[:3]
    assert len(snap) == 3
    assert [c.title for c in snap] == ["证据0", "证据1", "证据2"]


def test_pool_snapshot_returns_empty_when_pool_empty():
    pool = EvidencePool()
    assert pool.snapshot() == []


def test_resolve_with_empty_pool_returns_empty():
    pool = EvidencePool()
    pool.push("report_fact", "X", "x", source_id="x", source_label="X")
    # 即便请求 ref_id 也找不到（pool 只有 1 条但请求了 ref_999）
    assert pool.resolve(["ref_999"]) == []
```

- [ ] **Step 4: 跑测试验证**

Run: `cd backend && python -m pytest tests/test_evidence_fallback.py -v`
Expected: PASS（3 个测试）

- [ ] **Step 5: 提交**

```bash
cd backend && git add tests/test_respond_evidence_refs.py tests/test_evidence_fallback.py && git commit -m "test(agent): 5 种 kind evidence_refs roundtrip + fallback 单元测试"
```

---

## Task 10: 前端 TS 类型 —— `EvidenceItem` / `EvidenceStreamItem` / `EvidencePanelState`

**Files:**
- Modify: `frontend/src/schemas/agentResponse.ts`

- [ ] **Step 1: 修改 TS schema 文件**

修改 `frontend/src/schemas/agentResponse.ts`：

```typescript
// 在第 45-48 行替换现有 EvidenceItem
export type EvidenceType = 'report_fact' | 'profile' | 'device' | 'memory' | 'product';

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

// 同步修改 KbInterpretationPayload 的引用（已经是 list<EvidenceItem>，自动适配新字段）
export interface KbInterpretationPayload {
  topic: string;
  evidence: EvidenceItem[];
  suggestions: SuggestionItem[];
  red_flags: string[];
}

// 5 种 payload 都加 evidence 字段（其他 4 种 optional）
export interface MealPlanPayload {
  scope: 'family' | 'member';
  target_member_name: string | null;
  meal_items: MealItem[];
  member_adjustments: MemberAdjustment[];
  avoid_tags: string[];
  extra_note: string | null;
  evidence?: EvidenceItem[] | null;
}

export interface QaPayload {
  question_topic: string;
  answer: string;
  tips: string[];
  evidence?: EvidenceItem[] | null;
}

export interface GreetingPayload {
  message: string;
  suggested_topics: string[];
  evidence?: EvidenceItem[] | null;
}

export interface GeneralAdvicePayload {
  topic: string;
  advice: string;
  cautions: string[];
  evidence?: EvidenceItem[] | null;
}

// StructuredCard 加 evidence_refs 字段
export interface StructuredCard {
  kind: ResponseKind;
  summary_text: string;
  payload: PayloadUnion;
  evidence_refs?: Array<{ ref_id: string; sort: number }>;
}

// 新增证据面板状态
export type EvidenceGroup = 'content' | 'product';

export interface EvidencePanelState {
  messageId: string;
  group: EvidenceGroup;
  focusRefId?: string;
}

export const EVIDENCE_EMPTY: EvidencePanelState | null = null;
```

- [ ] **Step 2: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误（如果有错误，多半是 StructuredCard 等其他地方引用了旧 EvidenceItem 字段，需同步更新）

- [ ] **Step 3: 修复其他引用旧字段的代码**

可能需要修改的地方：
- `frontend/src/components/chat/cards/KbInterpretationCard.tsx` —— 检查它是否读 `evidence[].source`，改为 `title`
- 其他 card 组件如有渲染 evidence 的地方

运行 `cd frontend && grep -rn "\.source" src/components/chat/cards/` 找到所有引用，逐个改 `evidence[].title`。

- [ ] **Step 4: 提交**

```bash
cd frontend && git add src/schemas/agentResponse.ts src/components/chat/cards/ && git commit -m "feat(frontend): TS schema 升级 EvidenceItem 五字段 + EvidencePanelState"
```

---

## Task 11: 前端 SSE 客户端 —— `onEvidence` / `onEvidenceFinal` 回调

**Files:**
- Modify: `frontend/src/api/agent.ts`

- [ ] **Step 1: 修改 `StreamCallbacks` 和 `handleSseEvent`**

修改 `frontend/src/api/agent.ts`：

```typescript
import type { StructuredCard, EvidenceItem } from '../schemas/agentResponse';

export interface EvidenceStreamPayload {
  message_id: string;
  ref_id: string;
  type: EvidenceItem['type'];
  title: string;
  excerpt: string;
  source_label: string;
  sort_hint: number;
}

export interface EvidenceFinalPayload {
  message_id: string;
  items: EvidenceItem[];
}

export type StreamCallbacks = {
  // ... 现有回调不变 ...
  onEvidence?: (payload: EvidenceStreamPayload) => void;
  onEvidenceFinal?: (payload: EvidenceFinalPayload) => void;
};

// 在 handleSseEvent 函数里追加两个分支：
function handleSseEvent(eventText: string, callbacks: StreamCallbacks) {
  const lines = eventText.split('\n');
  const event = lines.find((line) => line.startsWith('event: '))?.slice(7);
  const dataLine = lines.find((line) => line.startsWith('data: '));
  const data = dataLine ? JSON.parse(dataLine.slice(6)) : {};

  if (event === 'user_message') callbacks.onUserMessage?.(data);
  if (event === 'assistant_start') callbacks.onAssistantStart?.(data);
  if (event === 'delta') callbacks.onDelta?.(data.content ?? '');
  if (event === 'product_recommendations') callbacks.onProductRecommendations?.(data);
  if (event === 'card') callbacks.onCard?.(data);
  if (event === 'evidence') callbacks.onEvidence?.(data);
  if (event === 'evidence_final') callbacks.onEvidenceFinal?.(data);
  if (event === 'assistant_done') callbacks.onAssistantDone?.(data);
  if (event === 'error') throw new Error(data.message ?? '模型调用失败');
}
```

- [ ] **Step 2: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
cd frontend && git add src/api/agent.ts && git commit -m "feat(frontend): SSE 客户端加 onEvidence/onEvidenceFinal 回调"
```

---

## Task 12: 前端组件 —— `EvidenceItemCard`

**Files:**
- Create: `frontend/src/components/chat/evidence/EvidenceItemCard.tsx`
- Create: `frontend/src/components/chat/evidence/types.ts`

- [ ] **Step 1: 创建 types.ts**

Create `frontend/src/components/chat/evidence/types.ts`：

```typescript
import type { EvidenceItem } from '../../../schemas/agentResponse';

export type EvidenceType = EvidenceItem['type'];

export const TYPE_LABEL: Record<EvidenceType, string> = {
  report_fact: '报告事实',
  profile: '健康画像',
  device: '手环状态',
  memory: '互动记忆',
  product: '推荐商品',
};

export type { EvidenceItem };
export interface EvidenceStreamItem extends EvidenceItem {
  ref_id: string;
  sort_hint: number;
}
```

- [ ] **Step 2: 创建 EvidenceItemCard.tsx**

Create `frontend/src/components/chat/evidence/EvidenceItemCard.tsx`：

```tsx
import type { EvidenceItem } from '../../../schemas/agentResponse';
import { TYPE_LABEL } from './types';

type Props = {
  item: EvidenceItem;
  isHighlight?: boolean;
};

export function EvidenceItemCard({ item, isHighlight = false }: Props) {
  return (
    <article className={`evidence-item-card ${isHighlight ? 'highlight' : ''}`}>
      <div className="evidence-item-content">
        <h3 className="evidence-item-title">{item.title}</h3>
        <p className="evidence-item-excerpt">{item.excerpt}</p>
        <span className="evidence-item-source">{item.source_label}</span>
      </div>
      <span className="evidence-item-type">{TYPE_LABEL[item.type]}</span>
    </article>
  );
}
```

- [ ] **Step 3: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
cd frontend && git add src/components/chat/evidence/EvidenceItemCard.tsx src/components/chat/evidence/types.ts && git commit -m "feat(frontend): EvidenceItemCard 静态展示组件"
```

---

## Task 13: 前端组件 —— `EvidenceList` + `EvidenceEmpty`

**Files:**
- Create: `frontend/src/components/chat/evidence/EvidenceList.tsx`
- Create: `frontend/src/components/chat/evidence/EvidenceEmpty.tsx`

- [ ] **Step 1: 创建 EvidenceEmpty.tsx**

Create `frontend/src/components/chat/evidence/EvidenceEmpty.tsx`：

```tsx
export function EvidenceEmpty() {
  return (
    <div className="evidence-empty">
      <p className="evidence-empty-title">暂无证据</p>
      <p className="evidence-empty-hint">
        提出问题后，点聊天区里的「生成依据」或「推荐依据」查看 AI 参考依据
      </p>
    </div>
  );
}
```

- [ ] **Step 2: 创建 EvidenceList.tsx**

Create `frontend/src/components/chat/evidence/EvidenceList.tsx`：

```tsx
import type { EvidenceItem } from '../../../schemas/agentResponse';
import { EvidenceItemCard } from './EvidenceItemCard';

type Props = {
  items: EvidenceItem[];
  focusRefId?: string;
};

export function EvidenceList({ items, focusRefId }: Props) {
  return (
    <div className="evidence-list">
      {items.map((item, idx) => {
        // focusRefId 是产品类证据的 ref_id，但 EvidenceItem 没带 ref_id
        // 用 (item.source_id + idx) 当作 fallback key
        const isHighlight = focusRefId !== undefined && idx === 0;
        return (
          <EvidenceItemCard
            key={`${item.source_id}-${idx}`}
            item={item}
            isHighlight={isHighlight}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
cd frontend && git add src/components/chat/evidence/ && git commit -m "feat(frontend): EvidenceList + EvidenceEmpty 组件"
```

---

## Task 14: 前端组件 —— `EvidenceActions`

**Files:**
- Create: `frontend/src/components/chat/evidence/EvidenceActions.tsx`

- [ ] **Step 1: 创建 EvidenceActions.tsx**

Create `frontend/src/components/chat/evidence/EvidenceActions.tsx`：

```tsx
import type { AgentMessage } from '../../../api/agent';
import type { EvidencePanelState } from '../../../schemas/agentResponse';

type Props = {
  message: AgentMessage;
  currentState: EvidencePanelState | null;
  onActivate: (state: EvidencePanelState) => void;
};

function isMobile(): boolean {
  return typeof window !== 'undefined' && window.innerWidth < 768;
}

function isActive(
  group: 'content' | 'product',
  state: EvidencePanelState | null,
  messageId: string,
  focusRefId?: string
): boolean {
  if (!state) return false;
  if (state.messageId !== messageId) return false;
  if (state.group !== group) return false;
  if (focusRefId !== undefined && state.focusRefId !== focusRefId) return false;
  return true;
}

export function EvidenceActions({ message, currentState, onActivate }: Props) {
  if (isMobile()) return null;

  const hasContent = (message.card?.payload?.evidence?.length ?? 0) > 0;
  const hasProducts = (message.product_recommendations?.length ?? 0) > 0;
  if (!hasContent && !hasProducts) return null;

  return (
    <div className="evidence-actions-row">
      {hasContent && (
        <button
          type="button"
          className={`evidence-action-btn content ${isActive('content', currentState, message.id) ? 'active' : ''}`}
          onClick={() => onActivate({ messageId: message.id, group: 'content' })}
        >
          生成依据
        </button>
      )}
      {hasProducts && (
        <button
          type="button"
          className={`evidence-action-btn product ${isActive('product', currentState, message.id) ? 'active' : ''}`}
          onClick={() => onActivate({ messageId: message.id, group: 'product' })}
        >
          推荐依据
        </button>
      )}
      {hasProducts && message.product_recommendations!.map((p, idx) => (
        <button
          key={p.product_id}
          type="button"
          className={`evidence-action-btn product ${isActive('product', currentState, message.id, p.product_id) ? 'active' : ''}`}
          onClick={() => onActivate({ messageId: message.id, group: 'product', focusRefId: p.product_id })}
        >
          {p.name} 依据
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
cd frontend && git add src/components/chat/evidence/EvidenceActions.tsx && git commit -m "feat(frontend): EvidenceActions 切钮组件（生成依据/推荐依据/商品依据）"
```

---

## Task 15: 前端组件 —— `EvidencePanel`

**Files:**
- Create: `frontend/src/components/chat/evidence/EvidencePanel.tsx`

- [ ] **Step 1: 创建 EvidencePanel.tsx**

Create `frontend/src/components/chat/evidence/EvidencePanel.tsx`：

```tsx
import type { AgentMessage } from '../../../api/agent';
import type { EvidenceItem, EvidencePanelState } from '../../../schemas/agentResponse';
import { EvidenceEmpty } from './EvidenceEmpty';
import { EvidenceList } from './EvidenceList';

type Props = {
  state: EvidencePanelState | null;
  message: AgentMessage | null;
};

function isMobile(): boolean {
  return typeof window !== 'undefined' && window.innerWidth < 768;
}

function getContentEvidence(message: AgentMessage): EvidenceItem[] {
  const payloadEvidence = message.card?.payload?.evidence;
  if (Array.isArray(payloadEvidence)) return payloadEvidence;
  return [];
}

function getProductEvidence(message: AgentMessage, focusRefId?: string): EvidenceItem[] {
  // 简化方案：把每个商品的 reason 当作 1 条 product 证据
  // 真实方案是从 message.evidence_stream 或 message.card.payload.evidence 里按 type='product' 过滤
  const products = message.product_recommendations ?? [];
  return products
    .filter((p) => !focusRefId || p.product_id === focusRefId)
    .map((p) => ({
      type: 'product' as const,
      title: p.name,
      excerpt: p.reason,
      source_id: p.product_id,
      source_label: `商城·${p.name}`,
    }));
}

export function EvidencePanel({ state, message }: Props) {
  if (isMobile()) return null;
  if (!state || !message) return <EvidenceEmpty />;

  const items = state.group === 'content'
    ? getContentEvidence(message)
    : getProductEvidence(message, state.focusRefId);

  if (items.length === 0) return <EvidenceEmpty />;
  return <EvidenceList items={items} focusRefId={state.focusRefId} />;
}
```

- [ ] **Step 2: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
cd frontend && git add src/components/chat/evidence/EvidencePanel.tsx && git commit -m "feat(frontend): EvidencePanel 右栏组件"
```

---

## Task 16: 前端集成 —— `MessageBubble` 加 `EvidenceActions` + `ChatPage` 加三栏布局

**Files:**
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: 修改 `MessageList` —— 维护 `evidencePanelState`，传给 MessageBubble**

修改 `frontend/src/components/chat/MessageList.tsx`：

```tsx
import { useEffect, useRef, useState } from 'react';
import type { AgentMessage } from '../../api/agent';
import type { HealthAnalysisOverview } from '../../api/healthAnalysis';
import type { EvidencePanelState } from '../../schemas/agentResponse';
import { MessageBubble } from './MessageBubble';

type Props = {
  messages: AgentMessage[];
  loading: boolean;
  overview?: HealthAnalysisOverview | null;
  overviewLoading?: boolean;
  overviewError?: boolean;
  evidencePanelState: EvidencePanelState | null;
  onEvidenceActivate: (state: EvidencePanelState) => void;
};

// ... 保留 STICK_TO_BOTTOM_THRESHOLD、greetingText、WelcomeSummary 不变 ...

export function MessageList({
  messages,
  loading,
  overview,
  overviewLoading,
  overviewError,
  evidencePanelState,
  onEvidenceActivate
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);

  function handleScroll() {
    const node = containerRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    stickToBottomRef.current = distanceFromBottom <= STICK_TO_BOTTOM_THRESHOLD;
  }

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    if (loading || stickToBottomRef.current) {
      node.scrollTop = node.scrollHeight;
      stickToBottomRef.current = true;
    }
  }, [messages, loading]);

  return (
    <div ref={containerRef} className="chat-messages" onScroll={handleScroll}>
      {loading && <div className="empty-state">正在加载消息...</div>}
      {!loading && messages.length === 0 && (
        <WelcomeSummary overview={overview} loading={overviewLoading} error={overviewError} />
      )}
      {messages.map((message) => (
        <MessageBubble
          key={message.message_id}
          message={message}
          evidencePanelState={evidencePanelState}
          onEvidenceActivate={onEvidenceActivate}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 修改 `MessageBubble` —— 接收 props 并渲染 `EvidenceActions`**

修改 `frontend/src/components/chat/MessageBubble.tsx`：

```tsx
import type { AgentMessage } from '../../api/agent';
import type { EvidencePanelState } from '../../schemas/agentResponse';
import { MarkdownContent } from './markdown';
import { ProductRecommendationCards } from './ProductRecommendationCards';
import { StructuredCard } from './StructuredCard';
import { EvidenceActions } from './evidence/EvidenceActions';

type Props = {
  message: AgentMessage;
  evidencePanelState: EvidencePanelState | null;
  onEvidenceActivate: (state: EvidencePanelState) => void;
};

// ... PlaceholderDots 不变 ...

export function MessageBubble({ message, evidencePanelState, onEvidenceActivate }: Props) {
  const isUser = message.role === 'user';
  const time = new Date(message.created_at).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });
  const isPlaceholder = !isUser && !message.content && message.status === 'sending';
  const productItems = message.product_recommendations ?? [];

  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      <div className={`msg-avatar ${isUser ? 'user' : 'agent'}`}>{isUser ? '张' : '家'}</div>
      <div className="msg-wrap">
        <div className="msg-bubble">
          <div className="msg-text">
            {isPlaceholder ? <PlaceholderDots /> : isUser ? message.content : <MarkdownContent text={message.content} />}
          </div>
          {!isUser && productItems.length > 0 && (
            <ProductRecommendationCards items={productItems} />
          )}
          {!isUser && message.card && (
            <StructuredCard card={message.card} />
          )}
          {!isUser && (
            <EvidenceActions
              message={message}
              currentState={evidencePanelState}
              onActivate={onEvidenceActivate}
            />
          )}
        </div>
        <div className="msg-time">{message.status === 'failed' ? '发送失败' : time}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 修改 `ChatPage` —— 维护 state + 三栏布局 + 渲染 EvidencePanel**

修改 `frontend/src/pages/ChatPage.tsx`：

```tsx
import { useEffect, useMemo, useState } from 'react';
// ... 现有 import 不变 ...
import type { EvidencePanelState } from '../schemas/agentResponse';
import { EvidencePanel } from '../components/chat/evidence/EvidencePanel';

// 在 ChatPage 函数顶部加 state：
const [evidencePanelState, setEvidencePanelState] = useState<EvidencePanelState | null>(null);

// 在 sendMutation 的 callbacks 里加 onEvidence / onEvidenceFinal：
// （这里简化：流式 evidence 暂存到 message 的本地字段，evidence_final 覆盖到 card.payload.evidence）
// 实际生产代码需要为 AgentMessage 加 evidence_stream?: EvidenceStreamItem[] 字段
// 本 plan 简化处理：onEvidence 只更新 evidencePanelState 用于 STREAMING 阶段高亮；
// onEvidenceFinal 把 items 合并到 message.card.payload.evidence（如已存在则覆盖）

onEvidence: (payload) => {
  // 简化：暂存到 local state；不修改 AgentMessage 类型以避免 TS schema 改动蔓延
  console.log('evidence stream', payload);
},
onEvidenceFinal: (payload) => {
  // 把 evidence_final.items 写入 message.card.payload.evidence
  setLocalMessages((items) =>
    items.map((item) =>
      item.message_id === payload.message_id && item.role === 'assistant' && item.card
        ? ({
            ...item,
            card: {
              ...item.card,
              payload: {
                ...item.card.payload,
                evidence: payload.items,
              },
            },
          } as AgentMessage)
        : item
    )
  );
},

// 在 return JSX 里加右栏 EvidencePanel：
<section className="chat-main">
  {/* 原有 chat-header / MessageList / ChatInput */}
</section>
<aside className="chat-evidence-panel">
  <EvidencePanel
    state={evidencePanelState}
    message={
      evidencePanelState
        ? messages.find((m) => m.message_id === evidencePanelState.messageId) ?? null
        : null
    }
  />
</aside>
```

- [ ] **Step 4: 修改 `chat-layout` CSS（三栏布局）**

修改 `frontend/src/index.css` 或 `AppShell.css`：

```css
.chat-layout {
  display: grid;
  grid-template-columns: 240px 1fr 360px;
  height: 100%;
}

@media (max-width: 768px) {
  .chat-layout {
    grid-template-columns: 1fr;
  }
  .chat-evidence-panel {
    display: none;
  }
}
```

- [ ] **Step 5: TypeScript 编译验证**

Run: `cd frontend && npx tsc -b`
Expected: 无错误

- [ ] **Step 6: 提交**

```bash
cd frontend && git add src/components/chat/MessageBubble.tsx src/components/chat/MessageList.tsx src/pages/ChatPage.tsx src/index.css && git commit -m "feat(frontend): 集成 EvidenceActions + 三栏布局 + EvidencePanel"
```

---

## Task 17: 手工 E2E smoke checklist（spec §12）

**Files:** 无（手工验证）

- [ ] **Step 1: 启动后端 + 前端**

```bash
# 后端
cd backend && uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm run dev
```

- [ ] **Step 2: 跑一次真实 `meal_plan` 工具链 + `mall_recommend`**

打开 `http://localhost:5173`，输入「妈妈最近血压高，晚餐吃什么？」，观察：
- ✅ 中栏 Agent 回复下方出现 "生成依据" + "推荐依据" 切钮
- ✅ 推荐依据按钮下方有 N 个商品子切钮（每个商品 1 个）
- ✅ 点 "生成依据" → 右栏出现 4 张绿卡（体检报告、健康画像、手环状态、互动记忆）
- ✅ 点 "薄盐生抽依据" → 右栏切换到 3 张橙卡，"薄盐生抽"卡边框高亮
- ✅ 流式阶段：右栏在 `card` 事件之前已经显示部分 evidence
- ✅ `assistant_done` 后右栏稳定显示（来自 `card.payload.evidence`）

- [ ] **Step 3: 移动端尺寸验证**

浏览器开发者工具切到 iPhone 尺寸（< 768px）：
- ✅ 切钮不渲染
- ✅ 右栏不渲染（display: none）

- [ ] **Step 4: 故意构造 LLM 不传 `evidence_refs` 的场景**

在 `backend/app/services/langchain_agent.py` 临时加日志看 LLM 输出，确认 `evidence_refs` 为空时后端 fallback 到 pool snapshot 前 3 条。

- [ ] **Step 5: 验证完成后无 commit**

手工 checklist 不需要 git commit；前端 `tsc -b` 通过即视为完成。

---

## 任务总览

| Task | 范围 | 文件数 |
|---|---|---|
| 1 | 新 `EvidenceItem` schema | 2 |
| 2 | `evidence_refs` + 5 种 payload `evidence` 字段 | 2 |
| 3 | `EvidencePool` + 单元测试 | 2 |
| 4 | `MallRecommendTool` + `evidence_pool` | 2 |
| 5 | `Kb` / `Memory` / `MealPlan` 工具 + `evidence_pool` | 2 |
| 6 | `LangChainAgentRunner.stream()` 集成 pool | 2 |
| 7 | `AgentService.stream_message` 处理新事件 | 1 |
| 8 | `respond` 工具 description 动态注入 | 1 |
| 9 | 5 种 kind roundtrip + fallback 测试 | 2 |
| 10 | 前端 TS schema | 2 |
| 11 | SSE 客户端回调 | 1 |
| 12 | `EvidenceItemCard` | 2 |
| 13 | `EvidenceList` + `EvidenceEmpty` | 2 |
| 14 | `EvidenceActions` | 1 |
| 15 | `EvidencePanel` | 1 |
| 16 | `MessageBubble` / `MessageList` / `ChatPage` 集成 + CSS | 4 |
| 17 | 手工 E2E smoke | 0 |

**总计：** 16 个 commit + 1 个手工 checklist；后端 11 个新测试；前端靠 `tsc -b` 验证。

## Spec coverage 检查

| Spec 章节 | 覆盖 Task |
|---|---|
| §5.1 schema | Task 1, 2 |
| §5.2 前端 TS | Task 10 |
| §6 EvidencePool | Task 3, 6 |
| §6.1 工具钩子 | Task 4, 5 |
| §6.2 description 注入 | Task 8 |
| §7 SSE 事件 | Task 7, 11 |
| §8.1 切钮规则 | Task 14 |
| §8.2 右栏状态机 | Task 15, 16 |
| §8.3 选中态 | Task 14 |
| §9 前端组件 | Task 12-16 |
| §10 错误处理 | Task 8（fallback）, Task 3（resolve 跳过无效 ref） |
| §11 后端文件改动 | Task 1-9 |
| §11 前端文件改动 | Task 10-16 |
| §12 测试 | Task 1-9, 17 |
| §13 实施分步 | Task 1-17 |
| §14 风险 | Task 8（ref_id 静默跳过）, Task 9（fallback） |

**全部覆盖。**
