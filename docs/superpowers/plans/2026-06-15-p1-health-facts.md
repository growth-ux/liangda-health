# P1 健康事实库实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/liangda-health-iteration-roadmap.md` 的 P1，新增 `health_facts`，在报告上传后用 LLM 结构化抽取健康事实，并保存文档、页码、原文证据和可选 chunk 弱关联。

**Architecture:** 本阶段只做健康事实库闭环：新增 ORM 表、仓储、LLM 抽取服务、结构化校验、可选 chunk 证据匹配、上传后后台抽取任务、报告详情抽取状态、查询接口和测试。`source_document_id + source_page_no + evidence_text` 是强证据字段；`source_chunk_id` 只是后续 RAG 证据链增强字段，允许为空，匹配不到或置信度低时不写入。LLM 抽取不阻塞 PDF 上传接口。

**Tech Stack:** FastAPI、SQLAlchemy 2 ORM、Pydantic、pytest、MySQL 测试库、OpenAI-compatible DashScope/Qwen、现有 PDF/OCR/RAG 上传链路。

---

## Scope

对应 roadmap：

```text
P1：健康事实库
目标：
- 新增 health_facts
- 上传报告后抽取健康事实
- 健康事实保留文档、页码、chunk 和原文证据
```

本次执行原则：

- 抽取以 LLM 结构化输出为主，不使用纯规则抽取作为主方案。
- LLM 只从报告原文抽取明确出现的事实；不做医学推断，不把否定句抽成风险。
- 第一版只抽异常和可行动事实：异常指标、明确风险/异常结论、明确生活方式建议。
- 不抽正常指标、普通阴性结论、泛泛健康宣教或复查/随访类任务。
- 后端负责 JSON schema 校验、字段归一化和非法结果过滤。
- `source_document_id`、`source_page_no`、`evidence_text` 必填。
- `source_chunk_id` 可空，是弱关联字段；仅在同页 chunk 能高置信匹配证据文本时写入。
- 上传报告成功后提交后台任务抽取事实；上传失败不提交抽取任务。
- 报告详情记录事实抽取状态：`pending`、`processing`、`ready`、`failed`。
- 健康事实可能晚于报告 ready 状态写入；查询接口需要返回抽取状态，区分“抽取中”和“已抽完但没有事实”。
- 删除报告时同步删除该报告的事实。
- 提供查询接口供后续 P2/P6 复用，但本次不改健康画像、Agent、mem0 或商城推荐逻辑。
- 不新增前端页面；先通过 API 验证。

## Why Not Pure Rules

纯规则抽取不适合作为 P1 主方案：

- 体检报告表格格式不稳定，PDF/OCR 文本可能把指标名、结果、单位、参考范围拆散。
- 指标别名很多，例如 `LDL-C`、`低密度脂蛋白`、`低密度脂蛋白胆固醇`。
- “高于参考范围”不一定紧挨指标。
- 不同医院参考范围不同，单靠固定阈值容易误判。
- 关键词会误判否定句，例如“未见血糖异常”不能抽成“血糖偏高”。

因此 P1 采用：

```text
PDF/OCR 页文本
→ 文档、页、chunk、向量入库，报告 ready
→ 后台任务读取报告 pages/chunks
→ LLM 结构化抽取
→ Pydantic schema 校验
→ 同页 chunk 弱匹配 source_chunk_id
→ health_facts 入库
→ 更新报告 fact_extract_status
```

## Extraction Scope

P1 第一版只抽对后续健康画像、饮食原则和商品推荐有直接价值的事实：

```text
metric: 只抽 warning/danger 的异常指标，例如总胆固醇升高、尿酸升高、骨密度降低。
risk: 报告明确提示的风险或异常结论，例如血脂偏高、脂肪肝、骨量减少。
advice: 报告明确给出的饮食、运动、生活方式建议，例如低脂饮食、控制体重、增加运动。
```

不抽：

```text
normal metric: 正常范围内的普通指标。
recheck: 复查、随访、进一步检查类事项，本阶段没有提醒/任务模块承接。
negative finding: 未见异常、阴性、无明显异常。
generic education: 泛泛健康宣教，不是针对报告结果给出的建议。
```

入库的 `status` 只保留 `warning` 或 `danger`。如果 LLM 输出 `normal`，后端直接过滤，不让正常事实进入 `health_facts`。

## Async Extraction Model

健康事实抽取走后台任务，不阻塞上传接口。第一版不引入 Celery、RQ、Redis 或单独 job 表，状态直接放在报告详情 `kb_documents` 上。

报告新增字段：

```text
fact_extract_status: pending | processing | ready | failed
fact_extract_error: nullable text
```

状态流：

```text
创建报告:
document.status = processing
fact_extract_status = pending

PDF/OCR、pages、chunks、embedding、vector upsert 完成:
document.status = ready
fact_extract_status = pending
提交后台抽取任务

后台任务开始:
fact_extract_status = processing

抽取成功:
fact_extract_status = ready
fact_extract_error = null

抽取失败:
fact_extract_status = failed
fact_extract_error = 错误信息
```

后台任务必须重新创建 DB session，不能复用请求生命周期里的 `Session`。任务按 `document_id` 重新读取 document、pages、chunks，再调用 `HealthFactExtractor` 并保存 facts。

## Evidence Model

强证据字段：

```text
source_document_id
source_page_no
evidence_text
```

弱关联字段：

```text
source_chunk_id
```

`source_chunk_id` 的价值是后续 P6 推荐证据链可以从结构化事实跳回 RAG chunk，展示或检索原文上下文。但匹配方式不天然准确，所以本阶段必须遵守：

- 只在同一页 chunks 内匹配。
- 优先精确包含匹配。
- 再做简单相似度匹配。
- 低于阈值不绑定，保持 `source_chunk_id = None`。
- 页面或 Agent 展示推荐依据时，优先使用 `evidence_text`。

## Files

- Create: `backend/app/models/health_fact.py`
  - 定义 `HealthFact` ORM。
- Modify: `backend/app/models/kb.py`
  - 在报告详情上记录事实抽取状态和错误信息。
- Modify: `backend/app/models/__init__.py`
  - 导入新模型，保证 `Base.metadata.create_all()` 能建表。
- Create: `backend/app/repositories/health_fact_repository.py`
  - 保存、查询和删除事实。
- Create: `backend/app/services/health_fact_extractor.py`
  - LLM 结构化抽取、schema 校验、同页 chunk 弱匹配。
- Create: `backend/app/services/health_fact_tasks.py`
  - 后台健康事实抽取任务，使用新 DB session 读取报告并保存 facts。
- Modify: `backend/app/services/kb_service.py`
  - 上传 PDF 生成 pages/chunks/vector 后标记报告 ready；不再同步调用 LLM 抽取。
- Modify: `backend/app/repositories/kb_repository.py`
  - 删除文档时先删对应 facts；提供报告事实抽取状态更新和 pages/chunks 读取。
- Modify: `backend/app/schemas/kb.py`
  - 新增报告详情事实抽取状态字段；新增健康事实查询响应 schema。
- Modify: `backend/app/api/kb.py`
  - 上传成功后提交后台抽取任务；新增文档维度和成员维度事实查询接口。
- Create: `backend/tests/test_health_fact_extractor.py`
  - 验证 LLM JSON 解析、否定句过滤、chunk 弱匹配。
- Create: `backend/tests/test_health_fact_repository.py`
  - 验证仓储保存、查询、删除。
- Create: `backend/tests/test_health_fact_tasks.py`
  - 验证后台任务读取报告、保存 facts、更新抽取状态和失败错误。
- Modify: `backend/tests/test_kb_service.py`
  - 验证上传链路不再同步调用抽取，报告 ready 后保持 facts pending。
- Modify: `backend/tests/test_api_kb.py`
  - 验证上传接口提交后台任务、事实查询 API、抽取状态和删除报告同步删除 facts。

---

### Task 1: 新增 HealthFact ORM 和仓储

**Files:**
- Create: `backend/app/models/health_fact.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/repositories/health_fact_repository.py`
- Create: `backend/tests/test_health_fact_repository.py`

- [ ] **Step 1: 写仓储测试**

创建 `backend/tests/test_health_fact_repository.py`：

```python
from app.models.health_fact import HealthFact
from app.repositories.health_fact_repository import HealthFactCreate, SqlAlchemyHealthFactRepository


def _fact(**overrides):
    data = {
        "fact_id": "fact_1",
        "member_id": "mem_1",
        "fact_type": "risk",
        "name": "血脂偏高",
        "value": None,
        "unit": None,
        "reference_range": None,
        "status": "warning",
        "source_document_id": "doc_1",
        "source_page_no": 2,
        "source_chunk_id": None,
        "evidence_text": "总胆固醇高于参考范围",
    }
    data.update(overrides)
    return HealthFactCreate(**data)


def test_health_fact_repository_saves_and_lists_by_document(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)

    repository.save_facts([_fact(source_chunk_id="chunk_1")])

    facts = repository.list_by_document("doc_1")
    assert len(facts) == 1
    assert facts[0].fact_id == "fact_1"
    assert facts[0].member_id == "mem_1"
    assert facts[0].fact_type == "risk"
    assert facts[0].name == "血脂偏高"
    assert facts[0].reference_range is None
    assert facts[0].status == "warning"
    assert facts[0].source_page_no == 2
    assert facts[0].source_chunk_id == "chunk_1"
    assert facts[0].evidence_text == "总胆固醇高于参考范围"


def test_health_fact_repository_lists_by_member(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)
    repository.save_facts(
        [
            _fact(fact_id="fact_1", member_id="mem_1", source_document_id="doc_1"),
            _fact(fact_id="fact_2", member_id="mem_2", source_document_id="doc_2"),
        ]
    )

    facts = repository.list_by_member("mem_1")

    assert [fact.fact_id for fact in facts] == ["fact_1"]


def test_health_fact_repository_keeps_source_chunk_optional(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)

    repository.save_facts([_fact(source_chunk_id=None)])

    fact = repository.list_by_document("doc_1")[0]
    assert fact.source_chunk_id is None


def test_health_fact_repository_deletes_by_document(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)
    repository.save_facts([_fact()])

    repository.delete_by_document("doc_1")

    assert db_session.query(HealthFact).filter(HealthFact.source_document_id == "doc_1").all() == []
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_health_fact_repository.py -q
```

Expected: FAIL，提示 `app.models.health_fact` 或 `app.repositories.health_fact_repository` 不存在。

- [ ] **Step 3: 新增 ORM**

创建 `backend/app/models/health_fact.py`：

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HealthFact(Base):
    __tablename__ = "health_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="warning", index=True)
    source_document_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_chunk_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
```

修改 `backend/app/models/__init__.py`：

```python
"""ORM models."""

from app.models.device import DeviceBinding, DeviceDailyMetric
from app.models.health_fact import HealthFact

__all__ = ["DeviceBinding", "DeviceDailyMetric", "HealthFact"]
```

- [ ] **Step 4: 新增仓储**

创建 `backend/app/repositories/health_fact_repository.py`：

```python
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.health_fact import HealthFact


@dataclass(frozen=True)
class HealthFactCreate:
    fact_id: str
    member_id: str
    fact_type: str
    name: str
    value: str | None
    unit: str | None
    reference_range: str | None
    status: str
    source_document_id: str
    source_page_no: int
    source_chunk_id: str | None
    evidence_text: str


class SqlAlchemyHealthFactRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_facts(self, facts: list[HealthFactCreate]) -> None:
        if not facts:
            return
        self.db.add_all(
            [
                HealthFact(
                    fact_id=fact.fact_id,
                    member_id=fact.member_id,
                    fact_type=fact.fact_type,
                    name=fact.name,
                    value=fact.value,
                    unit=fact.unit,
                    reference_range=fact.reference_range,
                    status=fact.status,
                    source_document_id=fact.source_document_id,
                    source_page_no=fact.source_page_no,
                    source_chunk_id=fact.source_chunk_id,
                    evidence_text=fact.evidence_text,
                )
                for fact in facts
            ]
        )
        self.db.commit()

    def list_by_document(self, document_id: str) -> list[HealthFact]:
        return (
            self.db.query(HealthFact)
            .filter(HealthFact.source_document_id == document_id)
            .order_by(HealthFact.source_page_no.asc(), HealthFact.id.asc())
            .all()
        )

    def list_by_member(self, member_id: str) -> list[HealthFact]:
        return (
            self.db.query(HealthFact)
            .filter(HealthFact.member_id == member_id)
            .order_by(HealthFact.created_at.desc(), HealthFact.id.desc())
            .all()
        )

    def delete_by_document(self, document_id: str) -> None:
        for fact in self.db.query(HealthFact).filter(HealthFact.source_document_id == document_id).all():
            self.db.delete(fact)
        self.db.commit()
```

- [ ] **Step 5: 运行仓储测试**

Run:

```bash
cd backend
pytest tests/test_health_fact_repository.py -q
```

Expected: PASS。

---

### Task 2: 新增 LLM 健康事实抽取器

**Files:**
- Create: `backend/app/services/health_fact_extractor.py`
- Create: `backend/tests/test_health_fact_extractor.py`

- [ ] **Step 1: 写抽取器测试**

创建 `backend/tests/test_health_fact_extractor.py`：

```python
from app.services.chunker import TextChunk
from app.services.health_fact_extractor import HealthFactExtractor
from app.services.kb_service import PageCreate


class FakeLlmClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def extract(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def _page(text: str, page_no: int = 1) -> PageCreate:
    return PageCreate(document_id="doc_1", page_no=page_no, text_content=text)


def _chunk(content: str, *, chunk_id: str = "chunk_1", page_no: int = 1) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        document_id="doc_1",
        member_id="mem_1",
        page_no=page_no,
        content=content,
    )


def test_llm_extractor_builds_health_facts_and_exact_chunk_match():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "metric",
              "name": "总胆固醇",
              "value": "6.2",
              "unit": "mmol/L",
              "reference_range": "<5.2",
              "status": "warning",
              "evidence_text": "总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2")],
        chunks=[_chunk("姓名 张三 总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2")],
    )

    assert len(facts) == 1
    assert facts[0].member_id == "mem_1"
    assert facts[0].fact_type == "metric"
    assert facts[0].name == "总胆固醇"
    assert facts[0].value == "6.2"
    assert facts[0].unit == "mmol/L"
    assert facts[0].reference_range == "<5.2"
    assert facts[0].status == "warning"
    assert facts[0].source_document_id == "doc_1"
    assert facts[0].source_page_no == 1
    assert facts[0].source_chunk_id == "chunk_1"
    assert facts[0].evidence_text == "总胆固醇 6.2 mmol/L ↑ 参考范围 <5.2"
    assert "不要把否定句抽取为风险" in llm.calls[0]


def test_llm_extractor_filters_invalid_negated_and_normal_facts():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "risk",
              "name": "血糖偏高",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "evidence_text": "未见血糖异常"
            },
            {
              "fact_type": "metric",
              "name": "",
              "value": "6.2",
              "unit": "mmol/L",
              "reference_range": null,
              "status": "warning",
              "evidence_text": "总胆固醇 6.2"
            },
            {
              "fact_type": "metric",
              "name": "血红蛋白",
              "value": "145",
              "unit": "g/L",
              "reference_range": "130-175",
              "status": "normal",
              "evidence_text": "血红蛋白 145 g/L 参考范围 130-175"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("未见血糖异常。总胆固醇 6.2。血红蛋白 145 g/L 参考范围 130-175")],
        chunks=[_chunk("未见血糖异常。总胆固醇 6.2。血红蛋白 145 g/L 参考范围 130-175")],
    )

    assert facts == []


def test_llm_extractor_rejects_recheck_facts_for_p1_scope():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "recheck",
              "name": "复查血脂",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "evidence_text": "建议三个月后复查血脂"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("建议三个月后复查血脂")],
        chunks=[_chunk("建议三个月后复查血脂")],
    )

    assert facts == []


def test_llm_extractor_leaves_source_chunk_empty_when_match_is_weak():
    llm = FakeLlmClient(
        """
        {
          "facts": [
            {
              "fact_type": "risk",
              "name": "骨密度低",
              "value": null,
              "unit": null,
              "reference_range": null,
              "status": "warning",
              "evidence_text": "骨密度 T 值 -2.1，提示骨量减少"
            }
          ]
        }
        """
    )
    extractor = HealthFactExtractor(llm_client=llm)

    facts = extractor.extract(
        document_id="doc_1",
        member_id="mem_1",
        pages=[_page("骨密度 T 值 -2.1，提示骨量减少")],
        chunks=[_chunk("完全无关的文本", chunk_id="chunk_1")],
    )

    assert len(facts) == 1
    assert facts[0].source_chunk_id is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_health_fact_extractor.py -q
```

Expected: FAIL，提示 `health_fact_extractor` 不存在。

- [ ] **Step 3: 实现 LLM client、schema 校验和弱 chunk 匹配**

创建 `backend/app/services/health_fact_extractor.py`：

```python
from __future__ import annotations

import json
from difflib import SequenceMatcher
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.repositories.health_fact_repository import HealthFactCreate
from app.services.chunker import TextChunk
from app.services.kb_service import PageCreate


class ExtractedHealthFact(BaseModel):
    fact_type: str = Field(pattern="^(metric|risk|advice)$")
    name: str
    value: str | None = None
    unit: str | None = None
    reference_range: str | None = None
    status: str = Field(pattern="^(normal|warning|danger)$")
    evidence_text: str


class ExtractedHealthFactsPayload(BaseModel):
    facts: list[ExtractedHealthFact]


class DashScopeHealthFactLlmClient:
    def extract(self, prompt: str) -> str:
        from openai import OpenAI

        if not settings.llm_api_key:
            return '{"facts": []}'

        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        response = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or '{"facts": []}'


class HealthFactExtractor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or DashScopeHealthFactLlmClient()

    def extract(
        self,
        *,
        document_id: str,
        member_id: str,
        pages: list[PageCreate],
        chunks: list[TextChunk],
    ) -> list[HealthFactCreate]:
        facts: list[HealthFactCreate] = []
        seen: set[tuple[int, str, str, str | None]] = set()
        chunks_by_page = _group_chunks_by_page(chunks)

        for page in pages:
            payload = self._extract_page(page)
            for item in payload.facts:
                cleaned = _clean_fact(item)
                if cleaned is None:
                    continue
                key = (page.page_no, cleaned.fact_type, cleaned.name, cleaned.value)
                if key in seen:
                    continue
                seen.add(key)
                source_chunk_id = _match_source_chunk_id(cleaned.evidence_text, chunks_by_page.get(page.page_no, []))
                facts.append(
                    HealthFactCreate(
                        fact_id=f"fact_{uuid4().hex}",
                        member_id=member_id,
                        fact_type=cleaned.fact_type,
                        name=cleaned.name,
                        value=cleaned.value,
                        unit=cleaned.unit,
                        reference_range=cleaned.reference_range,
                        status=cleaned.status,
                        source_document_id=document_id,
                        source_page_no=page.page_no,
                        source_chunk_id=source_chunk_id,
                        evidence_text=cleaned.evidence_text[:500],
                    )
                )

        return facts

    def _extract_page(self, page: PageCreate) -> ExtractedHealthFactsPayload:
        raw = self.llm_client.extract(_build_user_prompt(page))
        try:
            return ExtractedHealthFactsPayload.model_validate_json(_strip_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError):
            return ExtractedHealthFactsPayload(facts=[])


_SYSTEM_PROMPT = """你是健康体检报告结构化抽取器。只输出 JSON，不输出 Markdown。
你只能抽取报告原文明确出现的事实，不要医学推断。
不要把否定句抽取为风险，例如“未见异常”“未见血糖异常”“无高血压”不能抽为 warning。
每条事实必须有 evidence_text，且 evidence_text 必须是报告原文中的短句或表格行。"""


def _build_user_prompt(page: PageCreate) -> str:
    return f"""请从下面第 {page.page_no} 页体检报告文本中抽取健康事实。

只允许输出这个 JSON 结构：
{{
  "facts": [
    {{
      "fact_type": "metric|risk|advice",
      "name": "异常指标名、风险名或建议名",
      "value": "指标值，没有则为 null",
      "unit": "单位，没有则为 null",
      "reference_range": "参考范围，没有则为 null",
      "status": "warning|danger",
      "evidence_text": "报告原文证据"
    }}
  ]
}}

抽取规则：
- 只抽异常和可行动事实，不抽正常指标、普通阴性结论、复查事项或泛泛健康宣教。
- metric：只抽报告明确异常的指标，例如总胆固醇升高、空腹血糖升高、尿酸升高、BMI 超标、骨密度降低。
- risk：报告明确提示的风险或异常，例如血脂偏高、血糖偏高、骨密度低。
- advice：报告明确给出的饮食、运动、生活方式建议。
- 不要把否定句抽取为风险。
- 不要输出报告没有明确写出的结论。
- 不要输出 status=normal 的事实。

报告文本：
{page.text_content}
"""


def _strip_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM response does not contain JSON object")
    return text[start : end + 1]


def _clean_fact(item: ExtractedHealthFact) -> ExtractedHealthFact | None:
    name = item.name.strip()
    evidence_text = item.evidence_text.strip()
    if not name or not evidence_text:
        return None
    if item.status == "normal":
        return None
    if _is_negated(evidence_text) and item.fact_type == "risk":
        return None
    return ExtractedHealthFact(
        fact_type=item.fact_type,
        name=name,
        value=item.value.strip() if item.value else None,
        unit=item.unit.strip() if item.unit else None,
        reference_range=item.reference_range.strip() if item.reference_range else None,
        status=item.status,
        evidence_text=evidence_text,
    )


def _is_negated(text: str) -> bool:
    return any(keyword in text for keyword in ("未见", "无明显", "无异常", "未提示", "阴性"))


def _group_chunks_by_page(chunks: list[TextChunk]) -> dict[int, list[TextChunk]]:
    result: dict[int, list[TextChunk]] = {}
    for chunk in chunks:
        result.setdefault(chunk.page_no, []).append(chunk)
    return result


def _match_source_chunk_id(evidence_text: str, chunks: list[TextChunk]) -> str | None:
    if not evidence_text or not chunks:
        return None
    normalized_evidence = _normalize(evidence_text)
    for chunk in chunks:
        if normalized_evidence and normalized_evidence in _normalize(chunk.content):
            return chunk.chunk_id

    best_chunk_id: str | None = None
    best_score = 0.0
    for chunk in chunks:
        score = SequenceMatcher(None, normalized_evidence, _normalize(chunk.content)).ratio()
        if score > best_score:
            best_score = score
            best_chunk_id = chunk.chunk_id
    return best_chunk_id if best_score >= 0.75 else None


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()
```

- [ ] **Step 4: 运行抽取器测试**

Run:

```bash
cd backend
pytest tests/test_health_fact_extractor.py -q
```

Expected: PASS。

---

### Task 3: 报告详情接入事实抽取状态

**Files:**
- Modify: `backend/app/models/kb.py`
- Modify: `backend/app/repositories/kb_repository.py`
- Modify: `backend/app/schemas/kb.py`
- Modify: `backend/tests/test_kb_service.py`
- Modify: `backend/tests/test_api_kb.py`

- [ ] **Step 1: 扩展报告模型和 schema**

在 `backend/app/models/kb.py` 的 `KbDocument` 增加：

```python
fact_extract_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
fact_extract_error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

在 `backend/app/schemas/kb.py` 的报告响应 schema 中增加：

```python
fact_extract_status: str = "pending"
fact_extract_error: str | None = None
```

上传返回 `UploadResult` 可增加：

```python
fact_extract_status: str = "pending"
```

- [ ] **Step 2: 扩展 KB 仓储状态方法**

修改 `backend/app/repositories/kb_repository.py`，为 `SqlAlchemyKbRepository` 增加：

```python
def mark_fact_extract_pending(self, document_id: str) -> None:
    document = self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one()
    document.fact_extract_status = "pending"
    document.fact_extract_error = None
    self.db.commit()


def mark_fact_extract_processing(self, document_id: str) -> None:
    document = self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one()
    document.fact_extract_status = "processing"
    document.fact_extract_error = None
    self.db.commit()


def mark_fact_extract_ready(self, document_id: str) -> None:
    document = self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one()
    document.fact_extract_status = "ready"
    document.fact_extract_error = None
    self.db.commit()


def mark_fact_extract_failed(self, document_id: str, error_message: str) -> None:
    document = self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one_or_none()
    if document is None:
        return
    document.fact_extract_status = "failed"
    document.fact_extract_error = error_message[:1000]
    self.db.commit()
```

- [ ] **Step 3: 上传链路不再同步抽取**

修改 `backend/app/services/kb_service.py`：

- 不在 `KbService.__init__` 注入 `HealthFactExtractor`。
- 不在 `upload_pdf()` 中调用 `health_fact_extractor.extract()`。
- `mark_ready()` 后返回 `fact_extract_status="pending"`。

`backend/tests/test_kb_service.py` 需要验证上传完成后只保存 pages/chunks/vector，未同步写入 facts。

- [ ] **Step 4: 运行服务测试**

Run:

```bash
cd backend
pytest tests/test_kb_service.py -q
```

Expected: PASS。

---

### Task 4: 后台任务抽取并保存 health_facts

**Files:**
- Create: `backend/app/services/health_fact_tasks.py`
- Modify: `backend/app/repositories/kb_repository.py`
- Create: `backend/tests/test_health_fact_tasks.py`
- Modify: `backend/tests/test_api_kb.py`

- [ ] **Step 1: 扩展 KB 仓储读取和删除能力**

修改 `backend/app/repositories/kb_repository.py`，新增 import：

```python
from app.models.health_fact import HealthFact
from app.models.kb import KbChunk, KbDocument, KbPage
from app.repositories.health_fact_repository import HealthFactCreate
```

在 `SqlAlchemyKbRepository` 中加入：

```python
def list_pages(self, document_id: str) -> list[KbPage]:
    return (
        self.db.query(KbPage)
        .filter(KbPage.document_id == document_id)
        .order_by(KbPage.page_no.asc())
        .all()
    )


def list_chunks(self, document_id: str) -> list[KbChunk]:
    return (
        self.db.query(KbChunk)
        .filter(KbChunk.document_id == document_id)
        .order_by(KbChunk.page_no.asc(), KbChunk.id.asc())
        .all()
    )


def save_facts(self, facts: list[HealthFactCreate]) -> None:
    if not facts:
        return
    self.db.add_all(
        [
            HealthFact(
                fact_id=fact.fact_id,
                member_id=fact.member_id,
                fact_type=fact.fact_type,
                name=fact.name,
                value=fact.value,
                unit=fact.unit,
                reference_range=fact.reference_range,
                status=fact.status,
                source_document_id=fact.source_document_id,
                source_page_no=fact.source_page_no,
                source_chunk_id=fact.source_chunk_id,
                evidence_text=fact.evidence_text,
            )
            for fact in facts
        ]
    )
    self.db.commit()


def delete_facts_by_document(self, document_id: str) -> None:
    for fact in self.db.query(HealthFact).filter(HealthFact.source_document_id == document_id).all():
        self.db.delete(fact)
    self.db.commit()
```

在 `delete_document()` 中删除 chunks/pages 前调用或执行 `delete_facts_by_document(document_id)`。

- [ ] **Step 2: 新增后台任务服务**

创建 `backend/app/services/health_fact_tasks.py`：

```python
from app.db.session import SessionLocal
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.services.health_fact_extractor import HealthFactExtractor


def extract_health_facts_for_document(document_id: str) -> None:
    db = SessionLocal()
    try:
        repository = SqlAlchemyKbRepository(db)
        document = repository.get_document(document_id)
        if document is None:
            return

        repository.mark_fact_extract_processing(document_id)
        try:
            pages = repository.list_pages(document_id)
            chunks = repository.list_chunks(document_id)
            facts = HealthFactExtractor().extract(
                document_id=document_id,
                member_id=document.member_id or "",
                pages=pages,
                chunks=chunks,
            )
            repository.delete_facts_by_document(document_id)
            repository.save_facts(facts)
            repository.mark_fact_extract_ready(document_id)
        except Exception as exc:
            repository.mark_fact_extract_failed(document_id, str(exc))
    finally:
        db.close()
```

- [ ] **Step 3: 写后台任务测试**

创建 `backend/tests/test_health_fact_tasks.py`，覆盖：

- 成功时状态从 `pending` 变为 `ready`，并写入 facts。
- 抽取器抛异常时状态变为 `failed`，写入 `fact_extract_error`。
- 后台任务通过 `document_id` 重新读取 pages/chunks，不依赖上传请求里的内存对象。

测试中可以 monkeypatch `HealthFactExtractor` 或给任务函数增加可选的 extractor factory；优先保持生产入口简单。

- [ ] **Step 4: 运行后台任务测试**

Run:

```bash
cd backend
pytest tests/test_health_fact_tasks.py tests/test_health_fact_extractor.py -q
```

Expected: PASS。

---

### Task 5: 上传 API 提交后台任务并查询 facts

**Files:**
- Modify: `backend/app/schemas/kb.py`
- Modify: `backend/app/api/kb.py`
- Modify: `backend/tests/test_api_kb.py`

- [ ] **Step 1: 写上传后台任务测试**

在 `backend/tests/test_api_kb.py` 中验证上传成功后会提交后台任务，但响应不等待 LLM 抽取：

```python
def test_upload_pdf_schedules_health_fact_extraction(monkeypatch):
    scheduled = []

    def fake_task(document_id: str):
        scheduled.append(document_id)

    monkeypatch.setattr("app.api.kb.extract_health_facts_for_document", fake_task)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.post(
        "/api/kb/documents",
        files={"file": ("report.pdf", b"%PDF fake", "application/pdf")},
        data={"member_id": "mem_1"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["fact_extract_status"] == "pending"
    assert scheduled == [response.json()["document_id"]]
```

- [ ] **Step 2: 写事实查询 API 测试**

在 `backend/tests/test_api_kb.py` 中新增：

```python
def test_kb_document_facts_endpoint_returns_health_facts():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get("/api/kb/documents/doc_1/facts")

    assert response.status_code == 200
    body = response.json()
    assert body["fact_extract_status"] == "ready"
    assert body["fact_extract_error"] is None
    item = body["items"][0]
    assert item["fact_id"] == "fact_1"
    assert item["member_id"] == "mem_1"
    assert item["fact_type"] == "risk"
    assert item["name"] == "骨密度低"
    assert item["reference_range"] is None
    assert item["status"] == "warning"
    assert item["source_document_id"] == "doc_1"
    assert item["source_page_no"] == 1
    assert item["source_chunk_id"] is None
    assert item["evidence_text"] == "骨密度 T 值 -2.1"


def test_kb_member_facts_endpoint_requires_existing_member():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDb()
    client = TestClient(app)

    response = client.get("/api/kb/members/mem_unknown/facts")

    assert response.status_code == 404
    assert response.json()["detail"] == "家人不存在"
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
cd backend
pytest tests/test_api_kb.py::test_upload_pdf_schedules_health_fact_extraction tests/test_api_kb.py::test_kb_document_facts_endpoint_returns_health_facts tests/test_api_kb.py::test_kb_member_facts_endpoint_requires_existing_member -q
```

Expected: FAIL，上传接口未提交后台任务，或事实查询响应没有抽取状态。

- [ ] **Step 4: 新增 schema**

在 `backend/app/schemas/kb.py` 中加入：

```python
class HealthFactItem(BaseModel):
    fact_id: str
    member_id: str
    fact_type: str
    name: str
    value: str | None
    unit: str | None
    reference_range: str | None
    status: str
    source_document_id: str
    source_page_no: int
    source_chunk_id: str | None
    evidence_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthFactsResponse(BaseModel):
    fact_extract_status: str
    fact_extract_error: str | None = None
    items: list[HealthFactItem]
```

- [ ] **Step 5: 上传 API 提交后台任务**

修改 `backend/app/api/kb.py`：

```python
from fastapi import BackgroundTasks
from app.services.health_fact_tasks import extract_health_facts_for_document
```

上传路由签名增加：

```python
background_tasks: BackgroundTasks,
```

调用 `KbService.upload_pdf()` 成功且 `result.status == "ready"` 后提交：

```python
background_tasks.add_task(extract_health_facts_for_document, result.document_id)
```

- [ ] **Step 6: 新增 facts API**

修改 `backend/app/api/kb.py` import，加入：

```python
from app.repositories.health_fact_repository import SqlAlchemyHealthFactRepository
```

在 schema import 中加入：

```python
HealthFactsResponse,
```

在 `get_document()` 路由前加入：

```python
@router.get("/documents/{document_id}/facts", response_model=HealthFactsResponse)
def list_document_health_facts(document_id: str, db: Session = Depends(get_db)):
    kb_repository = SqlAlchemyKbRepository(db)
    document = kb_repository.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    fact_repository = SqlAlchemyHealthFactRepository(db)
    return HealthFactsResponse(
        fact_extract_status=document.fact_extract_status,
        fact_extract_error=document.fact_extract_error,
        items=fact_repository.list_by_document(document_id),
    )


@router.get("/members/{member_id}/facts", response_model=HealthFactsResponse)
def list_member_health_facts(member_id: str, db: Session = Depends(get_db)):
    member_repository = SqlAlchemyMemberRepository(db)
    if not member_repository.exists_by_member_id(member_id):
        raise HTTPException(status_code=404, detail="家人不存在")
    fact_repository = SqlAlchemyHealthFactRepository(db)
    return HealthFactsResponse(
        fact_extract_status="ready",
        fact_extract_error=None,
        items=fact_repository.list_by_member(member_id),
    )
```

- [ ] **Step 7: 运行 API 测试**

Run:

```bash
cd backend
pytest tests/test_api_kb.py -q
```

Expected: PASS。

---

### Task 6: 全量后端验证

**Files:**
- No code changes.

- [ ] **Step 1: 运行 P1 相关测试**

Run:

```bash
cd backend
pytest tests/test_health_fact_extractor.py tests/test_health_fact_repository.py tests/test_health_fact_tasks.py tests/test_kb_service.py tests/test_api_kb.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行后端全量测试**

Run:

```bash
cd backend
pytest -q
```

Expected: PASS。

- [ ] **Step 3: 检查 git diff**

Run:

```bash
git diff -- backend/app/models/health_fact.py backend/app/models/kb.py backend/app/models/__init__.py backend/app/repositories/health_fact_repository.py backend/app/services/health_fact_extractor.py backend/app/services/health_fact_tasks.py backend/app/services/kb_service.py backend/app/repositories/kb_repository.py backend/app/schemas/kb.py backend/app/api/kb.py backend/tests/test_health_fact_extractor.py backend/tests/test_health_fact_repository.py backend/tests/test_health_fact_tasks.py backend/tests/test_kb_service.py backend/tests/test_api_kb.py
```

Expected: 只包含 P1 健康事实库相关变更；没有 P2 健康画像、P3 记忆或推荐逻辑变更。

---

## Self-Review

- Spec coverage: 覆盖 `health_facts` 建表、上传后后台 LLM 抽取、报告详情抽取状态、文档/页码/证据保存和可选 chunk 弱关联。
- Boundary check: 未接入 `HealthProfileService`，未改 Agent，未改商城推荐，符合 P1。
- Accuracy check: 明确纯规则抽取不作为主方案；使用 LLM 结构化抽取；只保留异常和可行动事实；过滤正常指标、复查事项、否定句和低置信 chunk 绑定。
- Evidence check: `source_document_id + source_page_no + evidence_text` 是强证据；`source_chunk_id` 可空。
- Test coverage: 覆盖 LLM JSON 解析、正常指标过滤、recheck 拒绝、否定句过滤、chunk 弱匹配、仓储、后台任务、上传链路、删除链路和 API 查询。
