# Agent 回复结构化卡片化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Agent 用户可见回复改造成结构化 JSON 卡片；`summary_text` 流式，payload 整体插入；前端按 `kind` 路由到 5 个专用卡片组件。

**Architecture:** LLM 必须调用新增的 `respond` 工具才能完成回复，工具参数是 `StructuredResponse` Pydantic 模型的 JSON schema。后端 `stream()` 把 `respond` 工具的 tool_call_chunk 中属于 `summary_text` 的部分作为 `delta` 事件流出去；工具返回的 ToolMessage 经 Pydantic 校验后作为 `card` 事件整体产出。前端 `StructuredCard` 按 `kind` 路由到 5 个子组件。LLM 绕过 `respond` 工具直接说话的 AIMessageChunk 会被丢弃。

**Tech Stack:** 后端：FastAPI + SQLAlchemy + LangChain + Pydantic（已有）。前端：React + Vite + TypeScript + Tailwind（已有）。**不引入新依赖。**

**注：** 前端目前没有测试框架（`package.json` 无 vitest/jest）。按用户"不过度设计"原则，本计划不安装测试框架；前端验收靠 `tsc -b` 编译通过 + 手动 smoke checklist（spec §9 已列）。spec §9 提到的前端单测视为手工 smoke 替代。

---

## Task 1: 新增 Pydantic `StructuredResponse` schema

**Files:**
- Create: `backend/app/schemas/agent_response.py`
- Test: `backend/tests/test_agent_response_schema.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_agent_response_schema.py`：

```python
import pytest
from pydantic import ValidationError

from app.schemas.agent_response import (
    GeneralAdvicePayload,
    GreetingPayload,
    KbInterpretationPayload,
    MealPlanPayload,
    QaPayload,
    StructuredResponse,
)


def test_meal_plan_payload_validates():
    payload = {
        "kind": "meal_plan",
        "summary_text": "今晚清淡为主。",
        "payload": {
            "scope": "family",
            "target_member_name": None,
            "meal_items": [
                {"slot": "dinner", "title": "清蒸鸡胸", "summary": "低脂高蛋白"},
            ],
            "member_adjustments": [
                {"member_name": "爸爸", "note": "控脂", "tags": ["控脂"]},
            ],
            "avoid_tags": ["油炸"],
            "extra_note": None,
        },
    }
    response = StructuredResponse.model_validate(payload)
    assert response.kind == "meal_plan"
    assert response.payload.scope == "family"
    assert response.payload.meal_items[0].title == "清蒸鸡胸"


def test_qa_payload_validates():
    payload = {
        "kind": "qa",
        "summary_text": "早餐建议如下。",
        "payload": {"question_topic": "早餐", "answer": "高蛋白 + 慢碳", "tips": ["加一个鸡蛋"]},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.kind == "qa"
    assert response.payload.tips == ["加一个鸡蛋"]


def test_greeting_payload_validates():
    payload = {
        "kind": "greeting",
        "summary_text": "你好，今天可以问我一日三餐。",
        "payload": {"message": "你好", "suggested_topics": ["三餐"]},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.suggested_topics == ["三餐"]


def test_kb_interpretation_payload_validates():
    payload = {
        "kind": "kb_interpretation",
        "summary_text": "爸爸血脂轻度偏高。",
        "payload": {
            "topic": "血脂",
            "evidence": [{"source": "2024 体检", "excerpt": "LDL-C 3.8"}],
            "suggestions": [{"text": "调整饮食", "priority": "primary"}],
            "red_flags": ["胸闷"],
        },
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.evidence[0].source == "2024 体检"


def test_general_advice_payload_validates():
    payload = {
        "kind": "general_advice",
        "summary_text": "少油少糖。",
        "payload": {"topic": "日常饮食", "advice": "少油少糖多蔬菜", "cautions": ["高糖"]},
    }
    response = StructuredResponse.model_validate(payload)
    assert response.payload.advice == "少油少糖多蔬菜"


def test_unknown_kind_rejected():
    payload = {
        "kind": "nonsense",
        "summary_text": "x",
        "payload": {},
    }
    with pytest.raises(ValidationError):
        StructuredResponse.model_validate(payload)


def test_summary_text_too_long_rejected():
    payload = {
        "kind": "qa",
        "summary_text": "x" * 401,
        "payload": {"question_topic": "x", "answer": "x", "tips": []},
    }
    with pytest.raises(ValidationError):
        StructuredResponse.model_validate(payload)


def test_meal_plan_missing_meal_items_rejected():
    payload = {
        "kind": "meal_plan",
        "summary_text": "x",
        "payload": {
            "scope": "family",
            "target_member_name": None,
            "member_adjustments": [],
            "avoid_tags": [],
            "extra_note": None,
        },
    }
    with pytest.raises(ValidationError):
        StructuredResponse.model_validate(payload)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_agent_response_schema.py -v
```

Expected: ImportError 或 ModuleNotFoundError，模块未存在。

- [ ] **Step 3: Write the implementation**

创建 `backend/app/schemas/agent_response.py`：

```python
"""Agent 用户可见回复的结构化 schema。

LLM 必须调用 respond 工具并填入本 schema；前端按 kind 路由卡片。
所有 Pydantic 模型严格校验——失败即抛 ValidationError，不做兜底降级。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ===== 餐单 payload =====

class MealItem(BaseModel):
    slot: Literal["breakfast", "lunch", "dinner"] | None = None
    title: str = Field(..., min_length=1, max_length=80)
    summary: str = Field(..., max_length=120)


class MemberAdjustment(BaseModel):
    member_name: str = Field(..., min_length=1, max_length=40)
    note: str = Field(..., max_length=200)
    tags: list[str] = Field(default_factory=list)


class MealPlanPayload(BaseModel):
    scope: Literal["family", "member"]
    target_member_name: str | None = None
    meal_items: list[MealItem] = Field(..., min_length=1)
    member_adjustments: list[MemberAdjustment] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    extra_note: str | None = Field(default=None, max_length=200)


# ===== 一般问答 payload =====

class QaPayload(BaseModel):
    question_topic: str = Field(..., min_length=1, max_length=80)
    answer: str = Field(..., min_length=1, max_length=400)
    tips: list[str] = Field(default_factory=list)


# ===== 寒暄 payload =====

class GreetingPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=200)
    suggested_topics: list[str] = Field(default_factory=list)


# ===== 健康解读 payload =====

class EvidenceItem(BaseModel):
    source: str = Field(..., min_length=1, max_length=80)
    excerpt: str = Field(..., min_length=1, max_length=300)


class SuggestionItem(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)
    priority: Literal["primary", "secondary"] = "primary"


class KbInterpretationPayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    evidence: list[EvidenceItem] = Field(..., min_length=1)
    suggestions: list[SuggestionItem] = Field(..., min_length=1)
    red_flags: list[str] = Field(default_factory=list)


# ===== 一般建议 payload =====

class GeneralAdvicePayload(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    advice: str = Field(..., min_length=1, max_length=400)
    cautions: list[str] = Field(default_factory=list)


# ===== 顶层 Envelope（respond 工具的参数） =====

ResponseKind = Literal["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]


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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_agent_response_schema.py -v
```

Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/agent_response.py backend/tests/test_agent_response_schema.py
git commit -m "feat: 新增 StructuredResponse Pydantic schema 与 8 个校验测试

LLM 调用 respond 工具时参数必须符合此 schema。
解析失败抛 ValidationError，不做降级。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: 在 LangChainAgentRunner 注册 `respond` 工具

**Files:**
- Modify: `backend/app/services/langchain_agent.py:144-220`（`_tools()` 方法）
- Modify: `backend/app/services/langchain_agent.py:63-77`（`__init__`）
- Test: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_langchain_agent.py` 末尾追加：

```python
def test_langchain_agent_registers_respond_tool(monkeypatch):
    """respond 工具的 schema 来自 StructuredResponse.model_json_schema()，且必含 kind/summary_text/payload。"""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()

    tools = runner._tools()
    respond = next(t for t in tools if t.name == "respond")

    # 工具存在
    assert respond is not None
    # 工具参数 schema 来自 StructuredResponse
    params = respond.args
    assert "kind" in params["properties"]
    assert "summary_text" in params["properties"]
    assert "payload" in params["properties"]
    # kind 是枚举
    assert set(params["properties"]["kind"]["enum"]) == {
        "meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"
    }


def test_langchain_agent_respond_tool_callable(monkeypatch):
    """respond 工具被 LLM 调用时直接返回 'ok'（payload 在 tool_call args 里，不在 result 里）。"""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()

    tools = runner._tools()
    respond = next(t for t in tools if t.name == "respond")

    result = respond.invoke(
        {
            "kind": "qa",
            "summary_text": "你好",
            "payload": {"question_topic": "测试", "answer": "测试回答", "tips": []},
        }
    )
    assert result == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_registers_respond_tool tests/test_langchain_agent.py::test_langchain_agent_respond_tool_callable -v
```

Expected: 失败，找不到名为 `respond` 的工具。

- [ ] **Step 3: Implement `respond` 工具**

修改 `backend/app/services/langchain_agent.py`：

1. 在文件顶部加 import：

```python
from langchain.tools import tool

from app.schemas.agent_response import StructuredResponse
```

2. 在 `LangChainAgentRunner.__init__` 不需要新增字段。

3. 在 `_tools()` 末尾添加 `respond` 工具（在 `return tools` 之前）：

```python
    @staticmethod
    @tool
    def respond(
        kind: str,
        summary_text: str,
        payload: dict,
    ) -> str:
        """返回对用户可见的回复。LLM 必须调用本工具才能完成回复——不能直接对用户说话。

        Args:
            kind: 回复类型枚举，meal_plan/qa/greeting/kb_interpretation/general_advice。
            summary_text: 口语化总结（1-2 句，≤ 400 字），会流式输出。
            payload: 按 kind 决定的结构化内容，前端按它渲染卡片。
        """
        return "ok"

    tools.append(respond)
```

> 说明：用 LangChain 的 `@tool` 装饰器自动从函数签名生成 OpenAI function calling 的 parameters schema，与我们 `StructuredResponse` 的字段名/枚举对齐。`payload` 故意标成 `dict`——LangChain 不会强制校验内部字段，由后续 ToolMessage 解析阶段用 Pydantic 严格校验。

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_registers_respond_tool tests/test_langchain_agent.py::test_langchain_agent_respond_tool_callable -v
```

Expected: 2 passed。

- [ ] **Step 5: Run full test suite to verify no regression**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py -v
```

Expected: 原有测试全部通过（新增 2 个）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "feat: LangChainAgentRunner 注册 respond 工具

LLM 必须调用此工具完成回复，工具参数 schema 来自 StructuredResponse。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: 重构 `stream()` 把 `respond` 工具返回的 ToolMessage 解析为 `card` 事件

**Files:**
- Modify: `backend/app/services/langchain_agent.py:120-142`（`stream()` 方法）
- Modify: `backend/app/services/langchain_agent.py:300-330`（文件末尾新增辅助函数）
- Test: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_langchain_agent.py` 末尾追加：

```python
def test_langchain_agent_stream_emits_card_event_for_respond(monkeypatch):
    """respond 工具返回后，stream() 产出 ('card', StructuredResponse-like dict) 事件。"""
    from langchain_core.messages import AIMessageChunk, ToolMessage

    card_args = {
        "kind": "qa",
        "summary_text": "你好",
        "payload": {"question_topic": "早餐", "answer": "高蛋白", "tips": []},
    }
    import json

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield AIMessageChunk(content="先回一句"), {}
            yield ToolMessage(
                content=json.dumps(card_args, ensure_ascii=False),
                tool_call_id="call_1",
                name="respond",
            ), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "早餐吃什么"}]))
    card_events = [p for k, p in events if k == "card"]
    deltas = [p for k, p in events if k == "delta"]

    assert len(card_events) == 1
    assert card_events[0]["kind"] == "qa"
    assert card_events[0]["payload"]["answer"] == "高蛋白"
    # 现有 delta 仍正常
    assert deltas == ["先回一句"]


def test_langchain_agent_stream_raises_on_invalid_respond_payload(monkeypatch):
    """respond 工具的 ToolMessage 解析失败抛 ResponseSchemaError。"""
    from langchain_core.messages import ToolMessage
    from app.services.langchain_agent import ResponseSchemaError

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield ToolMessage(
                content='{"kind": "nonsense", "summary_text": "x", "payload": {}}',
                tool_call_id="call_1",
                name="respond",
            ), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    with pytest.raises(ResponseSchemaError):
        list(runner.stream([{"role": "user", "content": "x"}]))


def test_langchain_agent_stream_drops_aimessage_after_respond(monkeypatch):
    """LLM 调了 respond 之后又发普通 AIMessage 文字，stream() 丢弃并 warn。"""
    from langchain_core.messages import AIMessageChunk, ToolMessage
    import json

    card_args = {
        "kind": "qa",
        "summary_text": "s",
        "payload": {"question_topic": "q", "answer": "a", "tips": []},
    }

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield ToolMessage(
                content=json.dumps(card_args, ensure_ascii=False),
                tool_call_id="call_1",
                name="respond",
            ), {}
            # 绕过工具直接说话 → 应被丢弃
            yield AIMessageChunk(content="这段不该给用户看到"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "x"}]))
    deltas = [p for k, p in events if k == "delta"]
    assert deltas == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_stream_emits_card_event_for_respond tests/test_langchain_agent.py::test_langchain_agent_stream_raises_on_invalid_respond_payload tests/test_langchain_agent.py::test_langchain_agent_stream_drops_aimessage_after_respond -v
```

Expected: 3 failed（`ResponseSchemaError` 未定义、`card` 事件不产出、丢弃逻辑不存在）。

- [ ] **Step 3: Implement**

修改 `backend/app/services/langchain_agent.py`：

1. 在文件顶部（`LlmConfigError` 旁）添加新异常类：

```python
class ResponseSchemaError(Exception):
    pass
```

2. 重写 `stream()` 方法。**完整替换**为：

```python
    def stream(self, messages: list[dict[str, str]]) -> Iterable[tuple[Literal["delta", "product_recommendations", "card"], object]]:
        self._ensure_api_key()
        logger.info("agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        respond_done = False
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            # 1) mall_recommend 工具：JSON 字符串 → 现有 product_recommendations 事件
            payload = _try_parse_mall_recommend_payload(chunk)
            if payload is not None and payload.get("items"):
                logger.info("agent stream emit product_recommendations item_count=%s", len(payload["items"]))
                yield ("product_recommendations", payload)
                continue

            # 2) respond 工具的 ToolMessage → 整体解析为 card 事件
            if chunk.__class__.__name__ == "ToolMessage" and getattr(chunk, "name", None) == "respond":
                card = _parse_respond_payload(chunk)
                if card is None:
                    logger.warning("agent stream respond payload invalid; raising")
                    raise ResponseSchemaError("respond 工具参数不符合 StructuredResponse schema")
                respond_done = True
                logger.info("agent stream emit card kind=%s", card.get("kind"))
                yield ("card", card)
                continue

            # 3) LLM 在 respond 之后又发普通 AIMessage 文字 → 丢弃 + warn
            if respond_done and chunk.__class__.__name__ == "AIMessageChunk":
                text = _content_to_text(getattr(chunk, "content", ""))
                if text:
                    logger.warning("agent stream drop post-respond AIMessageChunk chars=%s", len(text))
                continue

            # 4) 现有 delta 路径（含 respond tool_call_chunk 中属 summary_text 的 token，由下一 task 处理）
            if not _is_visible_assistant_chunk(chunk):
                logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
                continue
            content = getattr(chunk, "content", "")
            text = _content_to_text(content)
            if text:
                yield ("delta", text)
        logger.info("agent stream done")
```

3. 在文件末尾添加辅助函数 `_parse_respond_payload`（紧跟 `_try_parse_mall_recommend_payload`）：

```python
def _parse_respond_payload(tool_message) -> dict | None:
    """从 respond 工具的 ToolMessage 中解析结构化 payload。

    ToolMessage.content 是 LLM 填入 respond 工具的 JSON 字符串（LangChain 会把 args 序列化为 content）。
    用 Pydantic 严格校验；返回 None 表示解析失败（由调用方决定抛错）。
    """
    from app.schemas.agent_response import StructuredResponse

    raw = getattr(tool_message, "content", "")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        validated = StructuredResponse.model_validate(data)
    except Exception:
        return None
    return validated.model_dump()
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_stream_emits_card_event_for_respond tests/test_langchain_agent.py::test_langchain_agent_stream_raises_on_invalid_respond_payload tests/test_langchain_agent.py::test_langchain_agent_stream_drops_aimessage_after_respond -v
```

Expected: 3 passed。

- [ ] **Step 5: Run full langchain_agent test suite to verify no regression**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py -v
```

Expected: 全部 passed（旧的 stream 商品推荐事件测试需通过——它们在 mall_recommend 后没 respond，所以走路径 4，deltas 正常）。

> **重点检查：** `test_langchain_agent_stream_emits_structured_events`（line 130-179）。它 yield 顺序是 AIMessageChunk → ToolMessage(kb) → ToolMessage(mall) → AIMessageChunk。改写后：
> - kb ToolMessage 不是 mall_recommend/respond → 走现有路径，被 `_is_visible_assistant_chunk` 过滤掉
> - mall ToolMessage → 走路径 1，发出 product_recommendations
> - AIMessageChunk（前后两段）→ 走路径 4，发出 delta
> - 没有 respond，所以 `respond_done` 永远是 False，第二段 AIMessageChunk 正常 delta
>
> 应该能过。如果挂了，先看是不是 path 2 的判断误吞了 mall。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "feat: stream() 路由 respond ToolMessage 为 card 事件，丢弃 post-respond AIMessage

Pydantic 校验失败抛 ResponseSchemaError。
LLM 绕过工具直接说话被丢弃 + warn 日志。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: 重构 `run()` 同步路径也提取 `card` 字段

**Files:**
- Modify: `backend/app/services/langchain_agent.py:91-118`（`run()` 方法）
- Test: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_langchain_agent.py` 末尾追加：

```python
def test_langchain_agent_run_extracts_card(monkeypatch):
    """run() 同步路径应从 respond ToolMessage 提取 card 字段，校验失败抛 ResponseSchemaError。"""
    from langchain_core.messages import AIMessage, ToolMessage
    from app.services.langchain_agent import ResponseSchemaError
    import json

    card_args = {
        "kind": "qa",
        "summary_text": "你好",
        "payload": {"question_topic": "早餐", "answer": "高蛋白", "tips": []},
    }

    class FakeAgent:
        def invoke(self, payload):
            return {
                "messages": [
                    ToolMessage(
                        content=json.dumps(card_args, ensure_ascii=False),
                        tool_call_id="call_1",
                        name="respond",
                    ),
                    AIMessage(content="已生成回复"),
                ]
            }

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    result = runner.run([{"role": "user", "content": "早餐"}])
    assert result["card"] is not None
    assert result["card"]["kind"] == "qa"
    assert result["card"]["payload"]["answer"] == "高蛋白"


def test_langchain_agent_run_raises_when_no_respond(monkeypatch):
    """run() 路径 LLM 没调 respond 抛 ResponseSchemaError。"""
    from langchain_core.messages import AIMessage
    from app.services.langchain_agent import ResponseSchemaError

    class FakeAgent:
        def invoke(self, payload):
            return {"messages": [AIMessage(content="直接说话没用")]}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    with pytest.raises(ResponseSchemaError):
        runner.run([{"role": "user", "content": "x"}])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_run_extracts_card tests/test_langchain_agent.py::test_langchain_agent_run_raises_when_no_respond -v
```

Expected: 2 failed（`result["card"]` KeyError / `ResponseSchemaError` 未抛）。

- [ ] **Step 3: Implement**

修改 `run()` 方法（替换原方法体）：

```python
    def run(self, messages: list[dict[str, str]]) -> dict[str, object]:
        self._ensure_api_key()
        logger.info("agent run start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        response = agent.invoke({"messages": self._to_langchain_messages(prepared_messages)})
        response_message = response["messages"][-1]
        token_usage = (
            response_message.response_metadata.get("token_usage", {})
            if response_message.response_metadata
            else {}
        )
        product_recs = _extract_product_recommendations(response["messages"])
        card = _extract_card(response["messages"])
        if card is None:
            logger.warning("agent run no respond tool call in messages; raising")
            raise ResponseSchemaError("LLM 未调用 respond 工具")
        result = {
            "content": card.get("summary_text", ""),
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
            "product_recommendations": product_recs,
            "card": card,
        }
        logger.info(
            "agent run done kind=%s summary_chars=%s prompt_tokens=%s completion_tokens=%s item_count=%s",
            card.get("kind"),
            len(card.get("summary_text", "")),
            result["token_prompt"],
            result["token_completion"],
            len((product_recs or {}).get("items") or []),
        )
        return result
```

在文件末尾添加 `_extract_card` 辅助函数：

```python
def _extract_card(messages) -> dict | None:
    """从 agent.invoke 的完整消息列表中找出 respond 工具的结果并解析。"""
    for message in messages:
        if message.__class__.__name__ != "ToolMessage":
            continue
        if getattr(message, "name", None) != "respond":
            continue
        return _parse_respond_payload(message)
    return None
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_run_extracts_card tests/test_langchain_agent.py::test_langchain_agent_run_raises_when_no_respond -v
```

Expected: 2 passed。

- [ ] **Step 5: Run full suite to check regression on old `test_langchain_agent_run_extracts_product_recommendations`**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py -v
```

Expected: 全部 passed。

> **旧测试兼容性：** `test_langchain_agent_run_extracts_product_recommendations`（line 207）的 FakeAgent.invoke 返回 `[ToolMessage(mall_recommend), AIMessage(content="全家晚餐建议...")]`。改写后 `response_message` 是最后一条 AIMessage，提取的 `content` 会是 "全家晚餐建议..."。但 `_extract_card` 会返回 None（旧测试没有 respond），从而抛 `ResponseSchemaError`——**这条旧测试会挂**。
>
> 修正方法：扩展旧 FakeAgent 让它也 yield 一个 respond ToolMessage：

```python
    def invoke(self, payload):
        mall_payload = json.dumps({...}, ensure_ascii=False)
        respond_payload = json.dumps({
            "kind": "qa",
            "summary_text": "全家晚餐建议...",
            "payload": {"question_topic": "晚餐", "answer": "清淡为主", "tips": []},
        }, ensure_ascii=False)
        return {
            "messages": [
                ToolMessage(content=mall_payload, tool_call_id="call_1", name="mall_recommend"),
                ToolMessage(content=respond_payload, tool_call_id="call_2", name="respond"),
                AIMessage(content="全家晚餐建议..."),
            ]
        }
```

把 `assert "全家晚餐建议" in result["content"]` 改成 `assert result["content"] == "全家晚餐建议..."`（因为 content 来自 card.summary_text）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "feat: run() 同步路径从 respond ToolMessage 提取 card

LLM 未调 respond 抛 ResponseSchemaError，不降级。
同步 test_langchain_agent_run_extracts_product_recommendations 让其也走 respond 路径。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: 让 `stream()` 真正流式 `summary_text`

**Files:**
- Modify: `backend/app/services/langchain_agent.py:120-187`（`stream()` 方法）
- Test: `backend/tests/test_langchain_agent.py`

> **为什么单独一个 task：** Task 3 的 `stream()` 走的是"LLM 直接说话"的 delta 路径，respond 工具引入后，summary_text 来自 tool_call 的 args（LangChain 把它序列化为 ToolMessage.content），不是 AIMessageChunk.content。需要解析 tool_call_chunks。

- [ ] **Step 1: Write the failing test**

```python
def test_langchain_agent_stream_emits_summary_text_deltas_from_respond_tool_call(monkeypatch):
    """LLM 调 respond 工具时，summary_text 字段在 tool_call_chunks 里逐渐生成，stream() 把它的 token 作为 delta 发出。"""
    from langchain_core.messages import AIMessageChunk
    from langchain_core.messages.tool import ToolCallChunk

    class FakeAgent:
        def stream(self, payload, stream_mode):
            # 第一次 chunk：开始 tool call，args 是 '{"kind": "qa", "summary_text": "你'
            chunk1 = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    ToolCallChunk(name="respond", args='{"kind": "qa", "summary_text": "你', index=0, id="call_1"),
                ],
            )
            yield chunk1, {}
            # 第二次 chunk：args 增加 '好"，payload: {...}'
            chunk2 = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    ToolCallChunk(name="respond", args='好", "payload": {"question_topic": "t", "answer": "a", "tips": []}}', index=0, id="call_1"),
                ],
            )
            yield chunk2, {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    deltas = [p for k, p in runner.stream([{"role": "user", "content": "x"}]) if k == "delta"]
    assert "".join(deltas) == "你好"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_stream_emits_summary_text_deltas_from_respond_tool_call -v
```

Expected: failed（deltas 为空）。

- [ ] **Step 3: Implement respond tool_call chunk 提取**

修改 `stream()` 中"AIMessageChunk 处理"段（在路径 4 之前）。把循环里的路径 3-4 重写为：

```python
            # 3) AIMessageChunk 含 respond 工具的 tool_call_chunk → 提取 summary_text 字段增量
            if chunk.__class__.__name__ == "AIMessageChunk":
                tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
                respond_chunk_text = _extract_respond_summary_text_delta(tool_call_chunks, respond_args_state)
                if respond_chunk_text:
                    yield ("delta", respond_chunk_text)
                # AIMessageChunk.content 文本 → 仅在 respond 未完成时走 delta；否则丢弃
                if not respond_done:
                    text = _content_to_text(getattr(chunk, "content", ""))
                    if text:
                        yield ("delta", text)
                continue
```

（**删除**原 stream() 里的路径 3-4。`respond_done` 标志和 respond ToolMessage 处理保留在路径 2。`respond_args_state` 是本 task 新增的局部变量，在 stream() 开头定义。）

在 `stream()` 开头加（**用局部变量，不要放 self 上**——runner 是单例，多请求并发会争用）：

```python
        respond_args_state: dict[str, str] = {}
```

在文件末尾添加辅助函数：

```python
def _extract_respond_summary_text_delta(tool_call_chunks: list, state: dict[str, str]) -> str:
    """从 AIMessageChunk.tool_call_chunks 中挑出 respond 工具的 args，提取 summary_text 字段的增量。

    state[id] 存的是上一次累积的 args 字符串。
    返回本次新增的 token 文本（已解 JSON 转义）。
    """
    SUMMARY_RE = re.compile(r'"summary_text"\s*:\s*"((?:[^"\\]|\\.)*)"')

    for tc in tool_call_chunks:
        if getattr(tc, "name", None) != "respond":
            continue
        tc_id = getattr(tc, "id", None) or "default"
        prev_args = state.get(tc_id, "")
        new_args = prev_args + (getattr(tc, "args", "") or "")
        state[tc_id] = new_args
        m = SUMMARY_RE.search(new_args)
        if not m:
            continue
        decoded = bytes(m.group(1), "utf-8").decode("unicode_escape", errors="ignore")
        # 增量 = decoded 减去上次的 decoded 长度
        prev_match = SUMMARY_RE.search(prev_args)
        if prev_match:
            prev_decoded = bytes(prev_match.group(1), "utf-8").decode("unicode_escape", errors="ignore")
            return decoded[len(prev_decoded):]
        return decoded
    return ""
```

在文件顶部加 import：

```python
import re
```

- [ ] **Step 4: Run new test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_langchain_agent_stream_emits_summary_text_deltas_from_respond_tool_call -v
```

Expected: passed。

- [ ] **Step 5: Run full suite to verify no regression**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py -v
```

Expected: 全部 passed。

> **旧测试 `test_langchain_agent_stream_emits_structured_events` 兼容性：** 它用 AIMessageChunk(content="首先，")，没 tool_call_chunks，路径 3 进入后 `respond_chunk_text=""`，`respond_done=False`（因为没 respond ToolMessage），所以走 "content 文本 → delta" 分支，输出 "首先，"。✅ 兼容。
>
> **旧测试 `test_langchain_agent_stream_skips_mall_recommend_error_payload` 兼容性：** ToolMessage(mall_recommend, content="Error: ...") → 路径 1 但 JSON 解析失败返回 None；接下来 AIMessageChunk(content="暂时无法推荐商品。") → 路径 3，respond_done=False，content 文本 → delta，输出 "暂时无法推荐商品。"。✅ 兼容。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "feat: stream() 解析 respond 工具 tool_call_chunks 中 summary_text 字段

LLM 边写 respond 边流式吐出 token，用户感知到逐字出现。
兼容原有 mall_recommend delta 路径。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: 更新 `SYSTEM_PROMPT_TEMPLATE` 强制调 `respond` 工具

**Files:**
- Modify: `backend/app/services/langchain_agent.py:11-42`（`SYSTEM_PROMPT_TEMPLATE`）
- Test: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_langchain_agent.py` 末尾追加：

```python
def test_runner_system_prompt_requires_respond_tool():
    """system_prompt 必须明确要求 LLM 调用 respond 工具才算完成回复。"""
    runner = LangChainAgentRunner()
    prompt = runner._system_prompt()
    assert "respond" in prompt
    assert "必须调用" in prompt or "只能通过" in prompt


def test_runner_system_prompt_documents_kinds():
    """system_prompt 必须列出 5 个 kind 的选择规则。"""
    runner = LangChainAgentRunner()
    prompt = runner._system_prompt()
    for kind in ["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]:
        assert kind in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_runner_system_prompt_requires_respond_tool tests/test_langchain_agent.py::test_runner_system_prompt_documents_kinds -v
```

Expected: 2 failed。

- [ ] **Step 3: Update `SYSTEM_PROMPT_TEMPLATE`**

修改 `SYSTEM_PROMPT_TEMPLATE`（在 `backend/app/services/langchain_agent.py:11-42`）。原模板有编号 1-24，最后一行是 `24. mall_recommend 的 scope 和 member_id 必须与 meal_plan 保持一致；全家餐单使用 scope="family"，不传 member_id。` + 末尾 `"""`。

**操作：** 在 `24. ...` 这一行**之后**、模板结束 `"""` 之前**直接追加**（不重新编号）：

```text
25. **【硬性要求】** Agent 完成一次用户回复必须调用 `respond` 工具，**不能**直接用普通文本对用户说话。`respond` 工具参数：
   - `kind`：5 选 1——`meal_plan`（用户问餐单/三餐/早午晚吃什么）/ `qa`（用户简单问答）/ `greeting`（首问/寒暄）/ `kb_interpretation`（用户问"为什么/要不要紧"且你刚调过 kb_search）/ `general_advice`（其他健康建议）
   - `summary_text`：口语化总结（1-2 句，≤ 400 字），会流式产出给用户
   - `payload`：按 kind 决定的结构化字段（见各 kind 定义）
   各 kind payload 要求：
   - `meal_plan.payload`：`scope` (family/member) / `target_member_name` / `meal_items[]` (slot/title/summary) / `member_adjustments[]` (member_name/note/tags) / `avoid_tags[]` / `extra_note`
   - `qa.payload`：`question_topic` / `answer` / `tips[]`
   - `greeting.payload`：`message` / `suggested_topics[]`
   - `kb_interpretation.payload`：`topic` / `evidence[]` (source/excerpt) / `suggestions[]` (text/priority) / `red_flags[]`
   - `general_advice.payload`：`topic` / `advice` / `cautions[]`
26. 完成工具链（meal_plan / kb_search 等）后，**立即**调用 `respond`，不要再继续说话。
27. 调完 `respond` 后不要再追加任何普通文本。
```

> **注意：** `{members_block}` 处于模板中间位置（替换 "15. ..." 行），新规则 25-27 写在 `{members_block}` 之后，编号与原 1-24 续接，不要触碰 `{members_block}` 那段。

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py::test_runner_system_prompt_requires_respond_tool tests/test_langchain_agent.py::test_runner_system_prompt_documents_kinds -v
```

Expected: 2 passed。

- [ ] **Step 5: Run full langchain_agent test suite to verify no regression on existing prompt tests**

```bash
cd backend && .venv/bin/pytest tests/test_langchain_agent.py -v
```

Expected: 全部 passed（包括 `test_runner_system_prompt_includes_member_list` / `_includes_memory_rules` / `_requires_mall_recommend_after_meal_plan`）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "feat: SYSTEM_PROMPT 强制 LLM 调用 respond 工具，列出 5 种 kind 规则

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: 给 `AgentMessage` 模型加 `card` 列 + 写迁移脚本

**Files:**
- Modify: `backend/app/models/agent.py:26-41`（`AgentMessage` 类）
- Create: `backend/app/scripts/migrate_add_agent_card.py`

- [ ] **Step 1: Create the migration script**

创建 `backend/app/scripts/migrate_add_agent_card.py`（仿照 `migrate_add_product_recommendations.py`）：

```python
"""为 agent_messages 表新增 card 列，存储结构化 respond payload（JSON 字符串）。

用法：
    python -m backend.app.scripts.migrate_add_agent_card            # 实际迁移
    python -m backend.app.scripts.migrate_add_agent_card --dry-run  # 只预览不写库
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.db.session import SessionLocal


def _column_exists(db, table: str, column: str) -> bool:
    rows = db.execute(text(f"SHOW COLUMNS FROM {table}")).fetchall()
    return any(row[0] == column for row in rows)


def migrate(db, dry_run: bool = False) -> dict:
    summary = {"table": "agent_messages", "column": "card", "existed": False, "added": False}

    if _column_exists(db, "agent_messages", "card"):
        summary["existed"] = True
        return summary

    ddl = "ALTER TABLE agent_messages ADD COLUMN card TEXT NULL"
    print(ddl)
    if not dry_run:
        db.execute(text(ddl))
        db.commit()
        summary["added"] = True

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="为 agent_messages 增加 card 列")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写库")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = migrate(db, dry_run=args.dry_run)
        if summary["existed"]:
            print("列已存在，跳过。")
        elif summary["added"]:
            print("列已添加。")
        else:
            print("dry-run 完成，未写库。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run dry-run to verify the script is correct**

```bash
cd backend && .venv/bin/python -m app.scripts.migrate_add_agent_card --dry-run
```

Expected: 输出 DDL `ALTER TABLE agent_messages ADD COLUMN card TEXT NULL`，状态 `dry-run 完成，未写库。`

- [ ] **Step 3: Add `card` column to `AgentMessage` model**

修改 `backend/app/models/agent.py:26-41`（在 `product_recommendations` 之后、`token_prompt` 之前）插入：

```python
    # 结构化卡片：respond 工具的 StructuredResponse，JSON 字符串。
    # 与 content / product_recommendations 解耦，前端按结构直接渲染对应卡片。
    card: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: Run the migration**

```bash
cd backend && .venv/bin/python -m app.scripts.migrate_add_agent_card
```

Expected: 输出 `ALTER TABLE agent_messages ADD COLUMN card TEXT NULL` + `列已添加。`（首次运行），或 `列已存在，跳过。`（重跑）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/agent.py backend/app/scripts/migrate_add_agent_card.py
git commit -m "feat: agent_messages 表加 card 列 + 迁移脚本

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: 仓储 `save_message` 接受 `card`，`AgentMessageItem` schema 暴露 `card`

**Files:**
- Modify: `backend/app/repositories/agent_repository.py:59-89`（`save_message` 方法）
- Modify: `backend/app/schemas/agent.py:29-57`（`AgentMessageItem`）

- [ ] **Step 1: Update repository**

修改 `backend/app/repositories/agent_repository.py` 的 `save_message`：

1. 在签名加 `card: str | None = None`：

```python
    def save_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        content: str,
        status: str = "done",
        product_recommendations: str | None = None,
        card: str | None = None,
        token_prompt: int | None = None,
        token_completion: int | None = None,
        model_name: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            status=status,
            product_recommendations=product_recommendations,
            card=card,
            token_prompt=token_prompt,
            token_completion=token_completion,
            model_name=model_name,
            created_at=utc_now(),
        )
```

- [ ] **Step 2: Update `AgentMessageItem` schema**

修改 `backend/app/schemas/agent.py`：

1. 在 `product_recommendations: list[dict] | None = None` 之后加：

```python
    card: dict | None = None
```

2. 在 `_parse_product_recommendations` 之后加 `_parse_card` 校验器：

```python
    @field_validator("card", mode="before")
    @classmethod
    def _parse_card(cls, value):
        # ORM 里存的是 JSON 字符串；None / 已是 dict / 解析失败 → None
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            import json

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None
```

- [ ] **Step 3: Verify existing test_agent_api / test_agent_service still pass**

```bash
cd backend && .venv/bin/pytest tests/test_agent_api.py tests/test_agent_service.py -v
```

Expected: 全部 passed（这次只加新字段，默认值都是 None，旧调用无影响）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/agent_repository.py backend/app/schemas/agent.py
git commit -m "feat: 仓储 + AgentMessageItem 暴露 card 字段

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: `AgentService.send_message` 透传 `card` 落库

**Files:**
- Modify: `backend/app/services/agent_service.py:41-74`（`send_message` 方法）
- Test: `backend/tests/test_agent_service.py`

- [ ] **Step 1: Write the failing test**

在 `backend/tests/test_agent_service.py` 末尾追加（先看现有测试怎么 mock runner）：

```python
def test_agent_service_send_message_persists_card(monkeypatch):
    """runner.run() 返回 result['card'] 时，仓储应落库为 JSON 字符串。"""
    from app.services.agent_service import AgentService

    class FakeRunner:
        def run(self, messages):
            return {
                "content": "你好",
                "token_prompt": 1,
                "token_completion": 2,
                "model_name": "m",
                "product_recommendations": None,
                "card": {
                    "kind": "qa",
                    "summary_text": "你好",
                    "payload": {"question_topic": "x", "answer": "y", "tips": []},
                },
            }

    saved_cards = []

    class FakeRepo:
        def __init__(self):
            self.session = self._make_session()

        def _make_session(self):
            s = type("S", (), {"session_id": "sess_1", "title": "新对话"})()
            return s

        def get_session(self, session_id):
            return self.session if session_id == "sess_1" else None

        def list_recent_messages(self, session_id, limit=8):
            return []

        def save_message(self, **kwargs):
            if kwargs.get("card") is not None:
                saved_cards.append(kwargs["card"])
            return type("M", (), {**kwargs, "message_id": kwargs.get("message_id", "msg_x")})()

        def update_session_title(self, *args, **kwargs):
            return None

    svc = AgentService(repository=FakeRepo(), runner=FakeRunner())
    user_msg, asst_msg = svc.send_message(session_id="sess_1", content="x")

    assert len(saved_cards) == 1
    import json
    parsed = json.loads(saved_cards[0])
    assert parsed["kind"] == "qa"
    assert parsed["payload"]["answer"] == "y"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_agent_service.py::test_agent_service_send_message_persists_card -v
```

Expected: failed（FakeRepo.save_message 收到 kwargs 无 `card`，saved_cards 空）。

- [ ] **Step 3: Update `send_message`**

修改 `backend/app/services/agent_service.py:53-66`，把 `save_message` 调用改为：

```python
        assistant_message = self.repository.save_message(
            message_id=f"msg_{uuid.uuid4().hex[:16]}",
            session_id=session_id,
            role="assistant",
            content=str(result["content"]),
            product_recommendations=(
                json.dumps((result.get("product_recommendations") or {}).get("items") or [], ensure_ascii=False)
                if result.get("product_recommendations") and (result["product_recommendations"].get("items") or [])
                else None
            ),
            card=(
                json.dumps(result.get("card"), ensure_ascii=False)
                if result.get("card") is not None
                else None
            ),
            token_prompt=result.get("token_prompt"),
            token_completion=result.get("token_completion"),
            model_name=result.get("model_name"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_agent_service.py::test_agent_service_send_message_persists_card -v
```

Expected: passed。

- [ ] **Step 5: Run full agent_service test suite**

```bash
cd backend && .venv/bin/pytest tests/test_agent_service.py -v
```

Expected: 全部 passed。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent_service.py backend/tests/test_agent_service.py
git commit -m "feat: AgentService.send_message 把 card 落库为 JSON 字符串

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: `AgentService.stream_message` 处理 `card` 事件并落库

**Files:**
- Modify: `backend/app/services/agent_service.py:76-150`（`stream_message` 方法）
- Test: `backend/tests/test_agent_service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_service_stream_message_emits_card_event(monkeypatch):
    """runner.stream() yield ('card', dict) 时，service 透传为 SSE 'card' 事件并落库。"""
    from app.services.agent_service import AgentService

    card_dict = {
        "kind": "qa",
        "summary_text": "你好",
        "payload": {"question_topic": "x", "answer": "y", "tips": []},
    }

    class FakeRunner:
        def stream(self, messages):
            yield ("delta", "先回")
            yield ("card", card_dict)
            yield ("delta", "结束")

    saved_cards = []

    class FakeRepo:
        def __init__(self):
            self.session = type("S", (), {"session_id": "sess_1", "title": "新对话"})()

        def get_session(self, session_id):
            return self.session if session_id == "sess_1" else None

        def list_recent_messages(self, session_id, limit=8):
            return []

        def save_message(self, **kwargs):
            if kwargs.get("card") is not None:
                saved_cards.append(kwargs["card"])
            return type("M", (), {**kwargs, "message_id": "msg_x"})()

        def update_session_title(self, *args, **kwargs):
            return None

    svc = AgentService(repository=FakeRepo(), runner=FakeRunner())
    events = list(svc.stream_message(session_id="sess_1", content="x"))

    # 验证 SSE 事件序列含 card
    card_events = [e for e in events if "event: card" in e]
    assert len(card_events) == 1
    assert '"kind": "qa"' in card_events[0] or '"kind":"qa"' in card_events[0]

    # 验证落库
    assert len(saved_cards) == 1
    import json
    parsed = json.loads(saved_cards[0])
    assert parsed["kind"] == "qa"

    # 验证 assistant_done 事件含 card 字段
    done_events = [e for e in events if "event: assistant_done" in e]
    assert len(done_events) == 1
    assert '"card"' in done_events[0]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && .venv/bin/pytest tests/test_agent_service.py::test_agent_service_stream_message_emits_card_event -v
```

Expected: failed（`event: card` 不存在）。

- [ ] **Step 3: Update `stream_message`**

修改 `backend/app/services/agent_service.py` 的 `stream_message`：

1. 在 `delta_chunks` 旁加 `card_dict: dict | None = None`。
2. 在 for 循环中加分支：

```python
        card_dict: dict | None = None
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
```

3. 把 `save_message` 调用加 `card=` 参数：

```python
        assistant_message = self.repository.save_message(
            message_id=assistant_id,
            session_id=session_id,
            role="assistant",
            content=content_done,
            product_recommendations=product_recs_json,
            card=json.dumps(card_dict, ensure_ascii=False) if card_dict is not None else None,
        )
```

4. 在 `assistant_done` 事件 payload 加 `card` 字段：

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

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && .venv/bin/pytest tests/test_agent_service.py::test_agent_service_stream_message_emits_card_event -v
```

Expected: passed。

- [ ] **Step 5: Run full agent_service test suite**

```bash
cd backend && .venv/bin/pytest tests/test_agent_service.py -v
```

Expected: 全部 passed。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent_service.py backend/tests/test_agent_service.py
git commit -m "feat: stream_message 处理 card 事件 + assistant_done 带 card

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: 前端 TypeScript 类型镜像

**Files:**
- Create: `frontend/src/schemas/agentResponse.ts`

- [ ] **Step 1: Write the types**

创建 `frontend/src/schemas/agentResponse.ts`：

```typescript
// 镜像 backend/app/schemas/agent_response.py
// 改 Pydantic 时务必同步改这里

export type ResponseKind =
  | 'meal_plan'
  | 'qa'
  | 'greeting'
  | 'kb_interpretation'
  | 'general_advice';

export type MealSlot = 'breakfast' | 'lunch' | 'dinner';

export interface MealItem {
  slot: MealSlot | null;
  title: string;
  summary: string;
}

export interface MemberAdjustment {
  member_name: string;
  note: string;
  tags: string[];
}

export interface MealPlanPayload {
  scope: 'family' | 'member';
  target_member_name: string | null;
  meal_items: MealItem[];
  member_adjustments: MemberAdjustment[];
  avoid_tags: string[];
  extra_note: string | null;
}

export interface QaPayload {
  question_topic: string;
  answer: string;
  tips: string[];
}

export interface GreetingPayload {
  message: string;
  suggested_topics: string[];
}

export interface EvidenceItem {
  source: string;
  excerpt: string;
}

export interface SuggestionItem {
  text: string;
  priority: 'primary' | 'secondary';
}

export interface KbInterpretationPayload {
  topic: string;
  evidence: EvidenceItem[];
  suggestions: SuggestionItem[];
  red_flags: string[];
}

export interface GeneralAdvicePayload {
  topic: string;
  advice: string;
  cautions: string[];
}

export type PayloadUnion =
  | MealPlanPayload
  | QaPayload
  | GreetingPayload
  | KbInterpretationPayload
  | GeneralAdvicePayload;

export interface StructuredResponse<K extends ResponseKind = ResponseKind> {
  kind: K;
  summary_text: string;
  payload: K extends 'meal_plan' ? MealPlanPayload
    : K extends 'qa' ? QaPayload
    : K extends 'greeting' ? GreetingPayload
    : K extends 'kb_interpretation' ? KbInterpretationPayload
    : GeneralAdvicePayload;
}

// 简化版：前端大多数场景只关心 kind + summary_text + payload，松类型即可
export type StructuredCard = {
  kind: ResponseKind;
  summary_text: string;
  payload: PayloadUnion;
};
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 无 error。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/schemas/agentResponse.ts
git commit -m "feat: 前端 TypeScript 类型镜像（StructuredResponse / PayloadUnion）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: 前端 SSE 事件分发加 `onCard` + `AgentMessage` 加 `card` 字段

**Files:**
- Modify: `frontend/src/api/agent.ts:18-46`

- [ ] **Step 1: Update types**

修改 `frontend/src/api/agent.ts`：

1. 在文件顶部加 import：

```typescript
import type { StructuredCard } from '../schemas/agentResponse';
```

2. 在 `AgentMessage` 加 `card?: StructuredCard` 字段（紧跟 `product_recommendations?: ...`）：

```typescript
export type AgentMessage = {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  status: 'done' | 'failed' | 'sending';
  created_at: string;
  attachments?: Attachment[];
  product_recommendations?: ProductRecommendationItem[];
  card?: StructuredCard;
};
```

3. 在 `StreamCallbacks` 加 `onCard` 回调（紧跟 `onProductRecommendations`）：

```typescript
export type StreamCallbacks = {
  onUserMessage?: (message: Pick<AgentMessage, 'message_id' | 'session_id' | 'role' | 'content' | 'attachments'>) => void;
  onAssistantStart?: (message: Pick<AgentMessage, 'message_id' | 'role'>) => void;
  onDelta?: (content: string) => void;
  onProductRecommendations?: (payload: { message_id: string; items: ProductRecommendationItem[] }) => void;
  onCard?: (payload: { message_id: string; card: StructuredCard }) => void;
  onAssistantDone?: (message: Pick<AgentMessage, 'message_id' | 'session_id' | 'role' | 'content' | 'product_recommendations' | 'card'>) => void;
};
```

4. 在 `handleSseEvent` 加 `card` 事件分支（紧跟 `product_recommendations` 分支）：

```typescript
  if (event === 'product_recommendations') callbacks.onProductRecommendations?.(data);
  if (event === 'card') callbacks.onCard?.(data);
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 无 error。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/agent.ts
git commit -m "feat: AgentMessage + StreamCallbacks 加 card 字段

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 13: 前端 `StructuredCard` 路由组件

**Files:**
- Create: `frontend/src/components/chat/StructuredCard.tsx`

- [ ] **Step 1: Write the component**

创建 `frontend/src/components/chat/StructuredCard.tsx`：

```tsx
import type { StructuredCard as Card } from '../../schemas/agentResponse';
import { MealPlanCard } from './cards/MealPlanCard';
import { QaCard } from './cards/QaCard';
import { GreetingCard } from './cards/GreetingCard';
import { KbInterpretationCard } from './cards/KbInterpretationCard';
import { GeneralAdviceCard } from './cards/GeneralAdviceCard';

type Props = { card: Card };

export function StructuredCard({ card }: Props) {
  switch (card.kind) {
    case 'meal_plan':
      return <MealPlanCard payload={card.payload as any} />;
    case 'qa':
      return <QaCard payload={card.payload as any} />;
    case 'greeting':
      return <GreetingCard payload={card.payload as any} />;
    case 'kb_interpretation':
      return <KbInterpretationCard payload={card.payload as any} />;
    case 'general_advice':
      return <GeneralAdviceCard payload={card.payload as any} />;
    default: {
      // 未知 kind（理论上 Pydantic 不会放过，但前端兜底）
      const exhaustive: never = card;
      return <pre className="text-xs text-red-500">{JSON.stringify(exhaustive)}</pre>;
    }
  }
}
```

- [ ] **Step 2: Verify type-check fails as expected (cards/ doesn't exist yet)**

```bash
cd frontend && npx tsc --noEmit
```

Expected: error 报告 cards/MealPlanCard 等模块未找到。✅ 预期，下一 task 创建。

- [ ] **Step 3: Commit (with broken state is fine — commit incrementally)**

```bash
git add frontend/src/components/chat/StructuredCard.tsx
git commit -m "feat: StructuredCard 按 kind 路由到 5 个子组件

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 14: 创建 `MealPlanCard` 组件（时间线 + 标签云）

**Files:**
- Create: `frontend/src/components/chat/cards/MealPlanCard.tsx`

- [ ] **Step 1: Write the component**

创建 `frontend/src/components/chat/cards/MealPlanCard.tsx`：

```tsx
import type { MealItem, MealPlanPayload, MemberAdjustment } from '../../../schemas/agentResponse';

type Props = { payload: MealPlanPayload };

const SLOT_LABEL: Record<NonNullable<MealItem['slot']>, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
};

const SLOT_COLOR: Record<NonNullable<MealItem['slot']>, string> = {
  breakfast: 'border-amber-300',
  lunch: 'border-emerald-400',
  dinner: 'border-violet-400',
};

const SLOT_TITLE: Record<NonNullable<MealItem['slot']>, string> = {
  breakfast: 'text-amber-700',
  lunch: 'text-emerald-700',
  dinner: 'text-violet-700',
};

export function MealPlanCard({ payload }: Props) {
  const { scope, target_member_name, meal_items, member_adjustments, avoid_tags, extra_note } = payload;

  // 按 slot 分组
  const bySlot: Record<NonNullable<MealItem['slot']>, MealItem[]> = {
    breakfast: [], lunch: [], dinner: [],
  };
  for (const item of meal_items) {
    if (item.slot) bySlot[item.slot].push(item);
  }

  return (
    <div className="mt-3 flex flex-col gap-3 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="flex items-center gap-2 text-stone-600">
        <span className="text-base">🍽️</span>
        <span className="font-semibold">
          {scope === 'family' ? '全家' : target_member_name || '单人'} · 餐单
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {(['breakfast', 'lunch', 'dinner'] as const).map((slot) => {
          const items = bySlot[slot];
          if (items.length === 0) return null;
          return (
            <div key={slot} className={`rounded-lg border-t-4 ${SLOT_COLOR[slot]} bg-white p-3`}>
              <div className={`text-xs font-semibold ${SLOT_TITLE[slot]} mb-1.5`}>{SLOT_LABEL[slot]}</div>
              {items.map((item, i) => (
                <div key={i} className="text-stone-700 leading-relaxed">
                  {item.title}
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {member_adjustments.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="text-xs font-semibold text-emerald-700 mb-2">👨‍👩‍👧 成员调整</div>
          <div className="flex flex-wrap gap-1.5">
            {member_adjustments.map((adj: MemberAdjustment, i) => (
              <span key={i} className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-700">
                {adj.member_name}: {adj.note}
              </span>
            ))}
          </div>
        </div>
      )}

      {avoid_tags.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-2">⚠️ 避免</div>
          <div className="flex flex-wrap gap-1.5">
            {avoid_tags.map((tag, i) => (
              <span key={i} className="rounded-full bg-white px-2.5 py-0.5 text-xs text-amber-800">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {extra_note && (
        <div className="text-xs text-stone-500 px-1">💡 {extra_note}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd frontend && npx tsc --noEmit
```

Expected: StructuredCard 还在抱怨其它 4 个 cards 不存在；MealPlanCard 自己无 error。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/cards/MealPlanCard.tsx
git commit -m "feat: MealPlanCard 时间线 + 标签云

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 15: 创建 QaCard / GreetingCard / KbInterpretationCard / GeneralAdviceCard

**Files:**
- Create: `frontend/src/components/chat/cards/QaCard.tsx`
- Create: `frontend/src/components/chat/cards/GreetingCard.tsx`
- Create: `frontend/src/components/chat/cards/KbInterpretationCard.tsx`
- Create: `frontend/src/components/chat/cards/GeneralAdviceCard.tsx`

- [ ] **Step 1: QaCard**

创建 `frontend/src/components/chat/cards/QaCard.tsx`：

```tsx
import type { QaPayload } from '../../../schemas/agentResponse';

type Props = { payload: QaPayload };

export function QaCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="font-semibold text-stone-700">💬 {payload.question_topic}</div>
      <div className="rounded-lg bg-white p-3 text-stone-700 leading-relaxed">{payload.answer}</div>
      {payload.tips.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="text-xs font-semibold text-emerald-700 mb-1.5">小贴士</div>
          <ul className="list-disc pl-5 text-stone-700 space-y-0.5">
            {payload.tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: GreetingCard**

创建 `frontend/src/components/chat/cards/GreetingCard.tsx`：

```tsx
import type { GreetingPayload } from '../../../schemas/agentResponse';

type Props = { payload: GreetingPayload };

export function GreetingCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="rounded-lg bg-white p-3 text-stone-700 leading-relaxed">{payload.message}</div>
      {payload.suggested_topics.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="text-xs font-semibold text-emerald-700 mb-1.5">你可以问我</div>
          <div className="flex flex-wrap gap-1.5">
            {payload.suggested_topics.map((t, i) => (
              <span key={i} className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-700">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: KbInterpretationCard**

创建 `frontend/src/components/chat/cards/KbInterpretationCard.tsx`：

```tsx
import type { KbInterpretationPayload } from '../../../schemas/agentResponse';

type Props = { payload: KbInterpretationPayload };

export function KbInterpretationCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="flex items-center gap-2 text-stone-600">
        <span>📋</span>
        <span className="font-semibold">关于「{payload.topic}」的解读</span>
      </div>

      <div className="rounded-lg bg-white p-3">
        <div className="text-xs font-semibold text-emerald-700 mb-1.5">报告依据</div>
        <ul className="space-y-1.5 text-stone-700">
          {payload.evidence.map((e, i) => (
            <li key={i} className="leading-relaxed">
              <span className="text-stone-500 text-xs">[{e.source}]</span> {e.excerpt}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg bg-white p-3">
        <div className="text-xs font-semibold text-emerald-700 mb-1.5">一般建议</div>
        <ul className="space-y-1 text-stone-700">
          {payload.suggestions.map((s, i) => (
            <li key={i} className="leading-relaxed">
              {s.priority === 'primary' && <span className="text-emerald-600 mr-1">●</span>}
              {s.priority === 'secondary' && <span className="text-stone-400 mr-1">○</span>}
              {s.text}
            </li>
          ))}
        </ul>
      </div>

      {payload.red_flags.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-1.5">⚠️ 需要就医的信号</div>
          <ul className="list-disc pl-5 text-amber-900 space-y-0.5">
            {payload.red_flags.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: GeneralAdviceCard**

创建 `frontend/src/components/chat/cards/GeneralAdviceCard.tsx`：

```tsx
import type { GeneralAdvicePayload } from '../../../schemas/agentResponse';

type Props = { payload: GeneralAdvicePayload };

export function GeneralAdviceCard({ payload }: Props) {
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm">
      <div className="font-semibold text-stone-700">💡 {payload.topic}</div>
      <div className="rounded-lg bg-white p-3 text-stone-700 leading-relaxed">{payload.advice}</div>
      {payload.cautions.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-1.5">⚠️ 注意</div>
          <ul className="list-disc pl-5 text-amber-900 space-y-0.5">
            {payload.cautions.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify type-check passes**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 无 error。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/chat/cards/QaCard.tsx frontend/src/components/chat/cards/GreetingCard.tsx frontend/src/components/chat/cards/KbInterpretationCard.tsx frontend/src/components/chat/cards/GeneralAdviceCard.tsx
git commit -m "feat: 4 个一般卡片组件（QaCard / GreetingCard / KbInterpretationCard / GeneralAdviceCard）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 16: `MessageBubble` 集成 `StructuredCard`

**Files:**
- Modify: `frontend/src/components/chat/MessageBubble.tsx`

- [ ] **Step 1: Update component**

修改 `frontend/src/components/chat/MessageBubble.tsx`：

1. 在 import 末尾加：

```tsx
import { StructuredCard } from './StructuredCard';
```

2. 在 `message.card` 存在的位置渲染卡片。在 `MessageBubble` 函数体内，加变量：

```tsx
  const hasCard = !isUser && Boolean(message.card);
```

3. 在 `<div className="msg-bubble">` 内、`<div className="msg-text">` 之后插入：

```tsx
          {hasCard && message.card && (
            <StructuredCard card={message.card} />
          )}
```

完整结构（替换原 `.msg-bubble` 块）：

```tsx
      <div className="msg-wrap">
        <div className="msg-bubble">
          <div className="msg-text">
            {isPlaceholder ? <PlaceholderDots /> : isUser ? message.content : <MarkdownContent text={message.content} />}
          </div>
          {!isUser && productItems.length > 0 && (
            <ProductRecommendationCards items={productItems} />
          )}
          {hasCard && message.card && (
            <StructuredCard card={message.card} />
          )}
        </div>
        <div className="msg-time">{message.status === 'failed' ? '发送失败' : time}</div>
      </div>
```

- [ ] **Step 2: Verify type-check passes**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 无 error。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/MessageBubble.tsx
git commit -m "feat: MessageBubble 在 summary_text 之下渲染 StructuredCard

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 17: `ChatPage` 处理 `onCard` 事件 + 落本地 message

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: 找到 sendAgentMessageStream 调用位置并加 onCard**

在 `frontend/src/pages/ChatPage.tsx` 找到 `sendAgentMessageStream(...)` 调用（应包含 `onProductRecommendations`），在它紧邻加 `onCard` 回调：

```tsx
        onCard: (payload) => {
          // 与 onProductRecommendations 同样的策略：把 card 写进本地 message 状态
          setMessages((prev) =>
            prev.map((m) =>
              m.message_id === payload.message_id
                ? ({ ...m, card: payload.card } as AgentMessage)
                : m
            )
          );
        },
```

- [ ] **Step 2: 在 `onAssistantDone` 合并 card**

找到 `onAssistantDone` 回调（`product_recommendations` 合并处），在它末尾加：

```tsx
                    card:
                      message.card ?? item.card,
```

完整模式（参照现有 product_recommendations 合并）：

```tsx
          onAssistantDone: (message) => {
            setMessages((prev) =>
              prev.map((item) => {
                if (item.message_id !== message.message_id) return item;
                return {
                  ...item,
                  content: message.content || item.content,
                  product_recommendations:
                    message.product_recommendations ?? item.product_recommendations,
                  card:
                    message.card ?? item.card,
                  status: 'done',
                } as AgentMessage;
              })
            );
          },
```

- [ ] **Step 3: Verify type-check passes**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 无 error。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "feat: ChatPage 处理 onCard 事件 + assistant_done 合并 card

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 18: 完整 type-check + 手动 smoke 验证

**Files:** (no file changes, just verification)

- [ ] **Step 1: 完整前端构建**

```bash
cd frontend && npm run build
```

Expected: tsc 编译通过 + vite build 成功。

- [ ] **Step 2: 完整后端测试**

```bash
cd backend && .venv/bin/pytest -v
```

Expected: 全部 passed。

- [ ] **Step 3: 启动后端 + 前端 dev server（手动）**

```bash
# 终端 1
cd backend && .venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000

# 终端 2
cd frontend && npm run dev
```

- [ ] **Step 4: 手动 smoke checklist（spec §9）**

依次验证：

1. **餐单场景**：问"妈妈今天一日三餐怎么吃" → 应看到 `meal_plan` 卡片（时间线 + 标签云）+ 1-2 句 summary_text
2. **健康解读**：问"爸爸血脂偏高要紧吗" → 应看到 `kb_interpretation` 卡片（报告依据 + 一般建议 + 红旗信号）
3. **一般问答**：问"早餐吃什么好" → 应看到 `qa` 卡片
4. **寒暄**：开新会话，刷新聊天页 → 应看到 `greeting` 卡片

- [ ] **Step 5: 错误路径验证**

手动构造：临时改 system_prompt 去掉"必须调 respond" 规则，提问后查看后端日志。预期看到 `ResponseSchemaError` + 前端消息 `status='failed'`，**无降级展示**。

> **做法：** 在 backend 容器/进程运行时改 `langchain_agent.py:25-27` 那段为宽松版（不要求调 respond），重启后端，问个问题。验证后改回原样。

- [ ] **Step 6: 提交验证报告（如有需要）**

如有发现需修的 bug，单独 commit 修复；否则此 task 完成。

```bash
# 如果无变更
git status  # 应为 clean
```

---

## 验收对照（spec §10）

| 验收项 | 验证方式 |
|--------|----------|
| 1. 所有 Agent 用户可见回复经 `respond` 工具 | Task 6 (system_prompt 强制) + Task 3/4 (校验) |
| 2. `summary_text` 流式 | Task 5 (tool_call_chunks 解析) |
| 3. `payload` 整体插入 | Task 3 (`card` 事件) + Task 10 (SSE 透传) |
| 4. 餐单时间线 + 标签云 | Task 14 (MealPlanCard) + Task 18 smoke |
| 5. 健康解读/问答/寒暄/建议 各卡片 | Task 15 + Task 18 smoke |
| 6. 校验失败 `failed`，无降级 | Task 3/4 (ResponseSchemaError) + Task 18 error path |
| 7. `meal_plan` 工具仍正常 | 旧测试通过 (Task 2 Step 5) |
| 8. `mall_recommend` 商品卡片仍正常 | 旧测试通过 (Task 3 Step 5) |
| 9. SSE 通道不变 + MarkdownContent 仍渲染 summary_text | 旧测试通过 (Task 10 Step 5) |
| 10. 无新依赖 + 无兜底 Markdown 路径 | Task 1 (Pydantic 严格校验) + 无新增 package.json 依赖 |
