# P3 Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 P3 设计接入 mem0 记忆系统，让用户偏好、排斥、阶段目标和营销反馈能跨会话影响 Agent 餐单输出。

**Architecture:** 新增 `MemoryService` 薄封装 mem0，`MemorySearchTool` 暴露给 LangChain Agent，`AgentService` 在保存用户消息后写入记忆，`MealPlanService` 在生成餐单前读取记忆并应用最小个性化规则。记忆归属按当前消息和家庭成员列表解析：明确成员时使用 `member_id` 作为 mem0 `user_id`，明确全家时使用 `default_family`，归属不明时跳过写入。第一版不新增本地记忆表、不做前端页面、不做复杂工具路由。

**Tech Stack:** FastAPI、SQLAlchemy 2 ORM、pytest、LangChain、mem0ai、OpenAI-compatible DashScope/Qwen。

---

## Scope

依据：

- `docs/liangda-health-iteration-roadmap.md` 的 P3。
- `docs/superpowers/specs/2026-06-15-memory-system-design.md`。

实现内容：

- 新增 `mem0ai` 依赖。
- 新增记忆配置。
- 新增 `backend/app/services/memory_service.py`。
- 根据家庭成员 `relation/name/member_id` 推断记忆归属。
- 新增 `MemorySearchTool`。
- `LangChainAgentRunner` 注册 `memory_search` 工具。
- `AgentService` 保存用户消息后写入记忆。
- `MealPlanService` 生成餐单前读取记忆，并处理“不喜欢鱼/不吃鱼”。
- API 依赖组装传入同一个 `MemoryService`。
- 增加后端测试。

不实现：

- 不新增前端页面。
- 不新增本地 `agent_memories` 表。
- 不做逻辑删除。
- 不做推荐证据链 UI。
- 不提前做 P4-P6 的完整意图路由、商品转化和证据链。

## Files

- Modify: `backend/requirements.txt`
  - 增加 `mem0ai`。
- Modify: `pyproject.toml`
  - 增加 `mem0ai`。
- Modify: `backend/app/core/config.py`
  - 增加记忆配置。
- Create: `backend/app/services/memory_service.py`
  - mem0 薄封装、记忆归属解析、fake client 友好接口、结果格式化。
- Modify: `backend/app/services/agent_tools.py`
  - 增加 `MemorySearchTool`。
- Modify: `backend/app/services/langchain_agent.py`
  - 注册 `memory_search` 工具，更新 system prompt。
- Modify: `backend/app/services/meal_plan_service.py`
  - 接收 `memory_service`，读取记忆并替换鱼。
- Modify: `backend/app/services/agent_service.py`
  - 保存用户消息后写入记忆。
- Modify: `backend/app/api/agent.py`
  - 组装 `MemoryService`、`MemorySearchTool`、带记忆的 `MealPlanService`。
- Create: `backend/tests/test_memory_service.py`
  - 覆盖写入、搜索、格式化、disabled。
- Modify: `backend/tests/test_agent_tools.py`
  - 覆盖 `MemorySearchTool`。
- Modify: `backend/tests/test_langchain_agent.py`
  - 覆盖 `memory_search` 工具和 prompt。
- Modify: `backend/tests/test_meal_plan_service.py`
  - 覆盖“不喜欢鱼”和健康约束优先。
- Modify: `backend/tests/test_agent_service.py`
  - 覆盖用户消息写入记忆和异常不阻断。

---

### Task 1: 配置和依赖

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `pyproject.toml`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 更新依赖文件**

在 `backend/requirements.txt` 末尾增加：

```text
mem0ai
```

在 `pyproject.toml` 的 `dependencies` 数组中增加：

```toml
    "mem0ai",
```

- [ ] **Step 2: 更新配置**

在 `backend/app/core/config.py` 的 `Settings` 中，放在 LLM 配置之后：

```python
    memory_enabled: bool = True
    memory_family_user_id: str = "default_family"
    memory_provider: str = "mem0"
```

- [ ] **Step 3: 运行配置相关测试**

Run:

```bash
pytest backend/tests/test_metadata.py -q
```

Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add backend/requirements.txt pyproject.toml backend/app/core/config.py
git commit -m "chore: add memory configuration"
```

---

### Task 2: 新增 MemoryService

**Files:**
- Create: `backend/app/services/memory_service.py`
- Create: `backend/tests/test_memory_service.py`

- [ ] **Step 1: 写 failing tests**

创建 `backend/tests/test_memory_service.py`：

```python
from types import SimpleNamespace

from app.services.memory_service import MemoryService


class FakeMem0Client:
    def __init__(self, search_result=None):
        self.add_calls = []
        self.search_calls = []
        self.search_result = search_result or []

    def add(self, messages, user_id=None, metadata=None):
        self.add_calls.append(
            {
                "messages": messages,
                "user_id": user_id,
                "metadata": metadata,
            }
        )
        return {"status": "ok"}

    def search(self, query, top_k=5, filters=None):
        self.search_calls.append(
            {
                "query": query,
                "top_k": top_k,
                "filters": filters,
            }
        )
        return self.search_result


def _members():
    return [
        SimpleNamespace(member_id="mem_dad", name="李建国", relation="爸爸"),
        SimpleNamespace(member_id="mem_mom", name="王丽", relation="妈妈"),
    ]


def test_memory_service_adds_member_message_with_member_id_as_user_id():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("爸爸不喜欢鱼")

    assert client.add_calls[0]["user_id"] == "mem_dad"
    assert client.add_calls[0]["metadata"]["member_id"] == "mem_dad"
    content = client.add_calls[0]["messages"][0]["content"]
    assert "爸爸不喜欢鱼" in content
    assert "记忆归属：mem_dad" in content
    assert "preference、avoidance、goal、marketing_feedback" in content
    assert "不要记录健康禁忌" in content


def test_memory_service_adds_family_message_with_default_family_user_id():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("我们全家都不喜欢鱼")

    assert client.add_calls[0]["user_id"] == "default_family"
    assert client.add_calls[0]["metadata"]["scope"] == "family"


def test_memory_service_skips_ambiguous_message_without_owner():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("不喜欢鱼")

    assert client.add_calls == []


def test_memory_service_searches_and_formats_results():
    client = FakeMem0Client(
        search_result=[
            {"memory": "爸爸不喜欢鱼", "metadata": {"memory_type": "avoidance", "member_id": "mem_dad"}},
            {"text": "妈妈最近想控糖", "metadata": {"memory_type": "goal", "member_id": "mem_mom"}},
        ]
    )
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    items = service.search("爸爸 饮食 排斥", member_id="mem_dad", limit=3)
    text = service.search_text("爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert client.search_calls[0]["query"] == "爸爸 饮食 排斥"
    assert client.search_calls[0]["top_k"] == 3
    assert client.search_calls[0]["filters"] == {"user_id": "mem_dad"}
    assert items[0].content == "爸爸不喜欢鱼"
    assert items[0].memory_type == "avoidance"
    assert "[avoidance] 爸爸不喜欢鱼" in text
    assert "[goal] 妈妈最近想控糖" in text


def test_memory_service_searches_family_memory_when_member_id_missing():
    client = FakeMem0Client(search_result=[{"memory": "全家不喜欢鱼"}])
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    service.search("全家 饮食 排斥")

    assert client.search_calls[0]["filters"] == {"user_id": "default_family"}


def test_memory_service_disabled_is_noop():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", enabled=False)

    service.add_from_user_message("爸爸不喜欢鱼")
    items = service.search("爸爸 饮食 排斥")

    assert client.add_calls == []
    assert client.search_calls == []
    assert items == []
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
pytest backend/tests/test_memory_service.py -q
```

Expected: FAIL，提示 `ModuleNotFoundError: No module named 'app.services.memory_service'`。

- [ ] **Step 3: 实现 MemoryService**

创建 `backend/app/services/memory_service.py`：

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryItem:
    content: str
    memory_type: str | None = None
    member_id: str | None = None


@dataclass(frozen=True)
class MemoryOwner:
    user_id: str
    member_id: str | None = None
    scope: str = "member"


class MemoryService:
    def __init__(
        self,
        client=None,
        family_user_id: str | None = None,
        member_provider: Callable[[], Iterable[object]] | None = None,
        enabled: bool | None = None,
    ):
        self._client = client
        self.family_user_id = family_user_id or settings.memory_family_user_id
        self.member_provider = member_provider or (lambda: [])
        self.enabled = settings.memory_enabled if enabled is None else enabled

    def add_from_user_message(self, content: str, *, member_id: str | None = None) -> None:
        if not self.enabled or not content.strip():
            return
        owner = self._resolve_owner(content, member_id=member_id)
        if owner is None:
            return
        prompt = (
            "只沉淀 preference、avoidance、goal、marketing_feedback。\n"
            "不要记录健康禁忌、诊断结论、报告事实或手环数据。\n"
            f"记忆归属：{owner.user_id}\n"
            f"用户原话：{content.strip()}"
        )
        metadata = {"source": "agent_user_message", "scope": owner.scope}
        if owner.member_id:
            metadata["member_id"] = owner.member_id
        try:
            self._get_client().add(
                [{"role": "user", "content": prompt}],
                user_id=owner.user_id,
                metadata=metadata,
            )
        except Exception:
            logger.exception("memory add failed")

    def search(self, query: str, *, member_id: str | None = None, limit: int = 5) -> list[MemoryItem]:
        if not self.enabled or not query.strip():
            return []
        filters = {"user_id": member_id or self.family_user_id}
        try:
            raw_items = self._get_client().search(
                query.strip(),
                top_k=limit,
                filters=filters,
            )
        except Exception:
            logger.exception("memory search failed")
            return []
        return [_to_memory_item(item) for item in _normalize_results(raw_items)]

    def search_text(self, query: str, *, member_id: str | None = None, limit: int = 5) -> str:
        items = self.search(query, member_id=member_id, limit=limit)
        if not items:
            return "未检索到相关记忆。"
        lines = []
        for item in items:
            label = item.memory_type or "memory"
            lines.append(f"[{label}] {item.content}")
        return "\n".join(lines)

    def _get_client(self):
        if self._client is None:
            if settings.memory_provider != "mem0":
                raise RuntimeError(f"unsupported memory provider: {settings.memory_provider}")
            from mem0 import Memory

            self._client = Memory.from_config(_mem0_config())
        return self._client

    def _resolve_owner(self, content: str, *, member_id: str | None = None) -> MemoryOwner | None:
        if member_id:
            return MemoryOwner(user_id=member_id, member_id=member_id)
        normalized = content.strip()
        if _is_family_scope(normalized):
            return MemoryOwner(user_id=self.family_user_id, scope="family")
        for member in self.member_provider():
            candidate_id = getattr(member, "member_id", None)
            if not candidate_id:
                continue
            names = [
                getattr(member, "relation", None),
                getattr(member, "name", None),
                candidate_id,
            ]
            if any(name and str(name) in normalized for name in names):
                return MemoryOwner(user_id=str(candidate_id), member_id=str(candidate_id))
        return None


def _mem0_config() -> dict:
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": settings.llm_model,
                "api_key": settings.llm_api_key,
                "openai_base_url": settings.llm_base_url,
                "temperature": settings.llm_temperature,
            },
        }
    }


def _normalize_results(raw_items) -> list:
    if isinstance(raw_items, dict) and isinstance(raw_items.get("results"), list):
        return raw_items["results"]
    if isinstance(raw_items, list):
        return raw_items
    return []


def _is_family_scope(content: str) -> bool:
    family_words = ("全家", "我们家", "家里人", "一家人")
    return any(word in content for word in family_words)


def _to_memory_item(item) -> MemoryItem:
    if isinstance(item, str):
        return MemoryItem(content=item)
    if not isinstance(item, dict):
        return MemoryItem(content=str(item))
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    content = item.get("memory") or item.get("text") or item.get("content") or ""
    return MemoryItem(
        content=str(content),
        memory_type=metadata.get("memory_type") or item.get("memory_type"),
        member_id=metadata.get("member_id") or item.get("member_id"),
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
pytest backend/tests/test_memory_service.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/memory_service.py backend/tests/test_memory_service.py
git commit -m "feat: add memory service"
```

---

### Task 3: 接入 MemorySearchTool 和 LangChain 工具

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/tests/test_agent_tools.py`
- Modify: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: 写 agent tool 测试**

在 `backend/tests/test_agent_tools.py` 末尾追加：

```python
class FakeMemoryService:
    def __init__(self):
        self.calls = []

    def search_text(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return "[avoidance] 爸爸不喜欢鱼"


def test_memory_search_tool_returns_memory_text():
    from app.services.agent_tools import MemorySearchTool

    service = FakeMemoryService()
    tool = MemorySearchTool(service)

    result = tool.search(query="爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert service.calls == [("爸爸 饮食 排斥", "mem_dad", 3)]
    assert "爸爸不喜欢鱼" in result


def test_memory_search_tool_rejects_empty_query():
    from app.services.agent_tools import MemorySearchTool

    service = FakeMemoryService()
    tool = MemorySearchTool(service)

    result = tool.search(query="   ")

    assert result == "Error: query 不能为空"
    assert service.calls == []
```

- [ ] **Step 2: 写 LangChain runner 测试**

在 `backend/tests/test_langchain_agent.py` 中 `FakeMealPlanTool` 后追加：

```python
class FakeMemoryTool:
    def __init__(self):
        self.calls = []

    def search(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return "[avoidance] 爸爸不喜欢鱼"
```

在测试区追加：

```python
def test_langchain_agent_registers_memory_search_tool(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    memory_tool = FakeMemoryTool()
    runner = LangChainAgentRunner(memory_tool=memory_tool)

    tools = runner._tools()
    result = tools[0](query="爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert memory_tool.calls == [("爸爸 饮食 排斥", "mem_dad", 3)]
    assert "爸爸不喜欢鱼" in result


def test_runner_system_prompt_includes_memory_rules():
    runner = LangChainAgentRunner()

    prompt = runner._system_prompt()

    assert "memory_search" in prompt
    assert "记忆只能用于个性化表达" in prompt
    assert "不能覆盖过敏" in prompt
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
pytest backend/tests/test_agent_tools.py backend/tests/test_langchain_agent.py -q
```

Expected: FAIL，提示 `MemorySearchTool` 不存在或 `LangChainAgentRunner.__init__` 不接受 `memory_tool`。

- [ ] **Step 4: 实现 MemorySearchTool**

修改 `backend/app/services/agent_tools.py`，在 `MealPlanTool` 后增加：

```python
class MemorySearchTool:
    def __init__(self, service):
        self.service = service

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        if not query.strip():
            return "Error: query 不能为空"
        return self.service.search_text(query=query, member_id=member_id, limit=limit)
```

- [ ] **Step 5: 修改 LangChainAgentRunner**

修改 `backend/app/services/langchain_agent.py`：

构造函数改为：

```python
class LangChainAgentRunner:
    def __init__(self, kb_tool=None, meal_plan_tool=None, memory_tool=None, member_provider=None):
        self.kb_tool = kb_tool
        self.meal_plan_tool = meal_plan_tool
        self.memory_tool = memory_tool
        self.member_provider = member_provider or (lambda: [])
```

在 `SYSTEM_PROMPT_TEMPLATE` 要求列表中增加：

```text
10. 涉及餐单、商品推荐、饮食偏好、排斥、阶段目标或购买反馈时，先调用 memory_search 工具。
11. 涉及某位家人时，memory_search 传入该家人的 member_id；涉及全家时不传 member_id，检索家庭级记忆；无法明确归属时不要伪造 member_id。
12. 记忆只能用于个性化表达，不能覆盖过敏、健康禁忌、报告事实和健康安全约束。
```

注意原来的跨家人报告对比序号需要顺延，不影响功能。

在 `_tools()` 的 `meal_plan` 和 `kb_search` 之间或之后增加：

```python
        if self.memory_tool is not None:
            def memory_search(query: str, member_id: str | None = None, limit: int = 5) -> str:
                """检索家庭或指定家人的长期互动记忆，包括偏好、排斥、阶段目标和营销反馈。"""
                return self.memory_tool.search(query=query, member_id=member_id, limit=limit)

            tools.append(memory_search)
```

- [ ] **Step 6: 运行测试确认通过**

Run:

```bash
pytest backend/tests/test_agent_tools.py backend/tests/test_langchain_agent.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/agent_tools.py backend/app/services/langchain_agent.py backend/tests/test_agent_tools.py backend/tests/test_langchain_agent.py
git commit -m "feat: expose memory search tool"
```

---

### Task 4: 餐单服务读取记忆并避开鱼

**Files:**
- Modify: `backend/app/services/meal_plan_service.py`
- Modify: `backend/tests/test_meal_plan_service.py`

- [ ] **Step 1: 写 failing tests**

在 `backend/tests/test_meal_plan_service.py` 中追加：

```python
class FakeMemoryService:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def search_text(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return self.text


def test_meal_plan_member_avoids_fish_from_memory(db_session):
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=["高血压"],
    )
    memory = FakeMemoryService("[avoidance] 爸爸不喜欢鱼")

    result = MealPlanService(db_session, memory_service=memory).build_member_plan("mem_dad")

    assert memory.calls == [("李建国 爸爸 饮食 偏好 排斥", "mem_dad", 5)]
    assert "鱼" not in result
    assert "鸡胸肉/豆腐" in result
    assert "个性化记忆：已避开爸爸不喜欢的鱼。" in result
    assert "低钠" in result


def test_meal_plan_member_keeps_health_safety_above_memory(db_session):
    _add_member(
        db_session,
        member_id="mem_dad",
        name="李建国",
        relation="爸爸",
        gender="男",
        health_tags=["高血压"],
    )
    memory = FakeMemoryService("[preference] 爸爸喜欢咸口")

    result = MealPlanService(db_session, memory_service=memory).build_member_plan("mem_dad")

    assert "低钠" in result
    assert "重盐" not in result
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
pytest backend/tests/test_meal_plan_service.py -q
```

Expected: FAIL，提示 `MealPlanService.__init__()` 不接受 `memory_service`。

- [ ] **Step 3: 修改 MealPlanService**

修改 `backend/app/services/meal_plan_service.py`：

构造函数改为：

```python
class MealPlanService:
    def __init__(self, db: Session, memory_service=None):
        self.profile_service = HealthProfileService(db)
        self.memory_service = memory_service
```

`build_member_plan` 改为：

```python
    def build_member_plan(self, member_id: str, goal: str | None = None, meal_type: str = "day") -> str:
        profile = self.profile_service.get_member_profile(member_id)
        memory_text = self._memory_text_for_member(profile)
        meals = _apply_memory_to_meals(_member_meals(profile), memory_text)
        return _format_member_plan(profile, meals, goal, meal_type, memory_text)
```

`build_family_plan` 改为：

```python
    def build_family_plan(self, goal: str | None = None, meal_type: str = "day") -> str:
        profile = self.profile_service.get_family_profile()
        memory_text = self._memory_text_for_family()
        meals = _apply_memory_to_meals(_family_meals(profile), memory_text)
        return _format_family_plan(profile, meals, goal, meal_type, memory_text)
```

在类中新增：

```python
    def _memory_text_for_member(self, profile: HealthProfile) -> str:
        if self.memory_service is None:
            return ""
        query = f"{profile.name} {profile.relation} 饮食 偏好 排斥"
        return self.memory_service.search_text(query, member_id=profile.member_id, limit=5)

    def _memory_text_for_family(self) -> str:
        if self.memory_service is None:
            return ""
        return self.memory_service.search_text("全家 饮食 偏好 排斥", limit=5)
```

修改格式化函数签名：

```python
def _format_member_plan(
    profile: HealthProfile,
    meals: dict[str, str],
    goal: str | None,
    meal_type: str,
    memory_text: str = "",
) -> str:
```

在 `if profile.today_modifiers:` 后增加：

```python
    if _should_avoid_fish(memory_text):
        lines.append(f"个性化记忆：已避开{profile.relation or profile.name}不喜欢的鱼。")
```

修改 family 格式化函数签名：

```python
def _format_family_plan(
    profile: FamilyHealthProfile,
    meals: dict[str, str],
    goal: str | None,
    meal_type: str,
    memory_text: str = "",
) -> str:
```

在 family `if profile.family_modifiers:` 后增加：

```python
    if _should_avoid_fish(memory_text):
        lines.append("个性化记忆：已避开家人不喜欢的鱼。")
```

文件底部新增：

```python
def _apply_memory_to_meals(meals: dict[str, str], memory_text: str) -> dict[str, str]:
    if not _should_avoid_fish(memory_text):
        return meals
    return {key: value.replace("清蒸鱼/鸡胸肉", "鸡胸肉/豆腐").replace("清蒸鱼", "鸡胸肉/豆腐").replace("鱼", "鸡胸肉/豆腐") for key, value in meals.items()}


def _should_avoid_fish(memory_text: str) -> bool:
    return "不喜欢鱼" in memory_text or "不吃鱼" in memory_text
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
pytest backend/tests/test_meal_plan_service.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/meal_plan_service.py backend/tests/test_meal_plan_service.py
git commit -m "feat: personalize meal plans with memory"
```

---

### Task 5: AgentService 保存用户消息后写入记忆

**Files:**
- Modify: `backend/app/services/agent_service.py`
- Modify: `backend/tests/test_agent_service.py`

- [ ] **Step 1: 写 failing tests**

在 `backend/tests/test_agent_service.py` 中追加：

```python
class FakeMemoryService:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def add_from_user_message(self, content, member_id=None):
        self.calls.append((content, member_id))
        if self.fail:
            raise RuntimeError("memory failed")


def test_agent_service_writes_user_message_to_memory(db_session):
    memory = FakeMemoryService()
    service = AgentService(SqlAlchemyAgentRepository(db_session), StaticRunner(), memory_service=memory)
    session = service.create_session("新对话")

    service.send_message(session.session_id, "爸爸不喜欢鱼")

    assert memory.calls == [("爸爸不喜欢鱼", None)]


def test_agent_service_memory_failure_does_not_block_send(db_session):
    memory = FakeMemoryService(fail=True)
    service = AgentService(SqlAlchemyAgentRepository(db_session), StaticRunner(), memory_service=memory)
    session = service.create_session("新对话")

    user_message, assistant_message = service.send_message(session.session_id, "爸爸不喜欢鱼")

    assert user_message.content == "爸爸不喜欢鱼"
    assert assistant_message.content == "收到：爸爸不喜欢鱼"
    assert memory.calls == [("爸爸不喜欢鱼", None)]


def test_agent_service_stream_writes_user_message_to_memory(db_session):
    memory = FakeMemoryService()
    service = AgentService(SqlAlchemyAgentRepository(db_session), StaticRunner(), memory_service=memory)
    session = service.create_session("新对话")

    events = list(service.stream_message(session.session_id, "爸爸不喜欢鱼"))

    assert memory.calls == [("爸爸不喜欢鱼", None)]
    assert any("assistant_done" in event for event in events)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
pytest backend/tests/test_agent_service.py -q
```

Expected: FAIL，提示 `AgentService.__init__()` 不接受 `memory_service`。

- [ ] **Step 3: 修改 AgentService**

修改 `backend/app/services/agent_service.py`：

构造函数：

```python
class AgentService:
    def __init__(self, repository: SqlAlchemyAgentRepository, runner, memory_service=None):
        self.repository = repository
        self.runner = runner
        self.memory_service = memory_service
```

在 `_save_user_message` 后新增方法：

```python
    def _remember_user_message(self, content: str) -> None:
        if self.memory_service is None:
            return
        try:
            self.memory_service.add_from_user_message(content)
        except Exception:
            logger.exception("memory write failed for agent user message")
```

在 `send_message` 中：

```python
        user_message = self._save_user_message(session_id, content)
        self._remember_user_message(content)
```

在 `stream_message` 中：

```python
        user_message = self._save_user_message(session_id, content)
        self._remember_user_message(content)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
pytest backend/tests/test_agent_service.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/agent_service.py backend/tests/test_agent_service.py
git commit -m "feat: write agent messages to memory"
```

---

### Task 6: API 依赖组装和整体验证

**Files:**
- Modify: `backend/app/api/agent.py`
- Modify: `backend/tests/test_agent_api.py`

- [ ] **Step 1: 检查现有 API 测试**

Run:

```bash
pytest backend/tests/test_agent_api.py -q
```

Expected: 当前基线 PASS。

- [ ] **Step 2: 修改 API 依赖组装**

修改 `backend/app/api/agent.py` imports：

```python
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.services.agent_tools import KbSearchTool, MealPlanTool, MemorySearchTool
from app.services.memory_service import MemoryService
```

新增依赖：

```python
def get_memory_service(db: Session = Depends(get_db)):
    member_repository = SqlAlchemyMemberRepository(db)
    return MemoryService(member_provider=member_repository.list_members)
```

修改 `get_agent_runner` 签名：

```python
def get_agent_runner(
    db: Session = Depends(get_db),
    memory_service: MemoryService = Depends(get_memory_service),
):
```

在 runner 组装中：

```python
        meal_plan_tool=MealPlanTool(
            service=MealPlanService(db, memory_service=memory_service),
            allowed_member_ids=[m.member_id for m in member_provider()],
        ),
        memory_tool=MemorySearchTool(memory_service),
        member_provider=member_provider,
```

修改 `get_agent_service` 签名：

```python
def get_agent_service(
    db: Session = Depends(get_db),
    runner=Depends(get_agent_runner),
    memory_service: MemoryService = Depends(get_memory_service),
) -> AgentService:
    return AgentService(
        repository=SqlAlchemyAgentRepository(db),
        runner=runner,
        memory_service=memory_service,
    )
```

注意：FastAPI 会按 dependency cache 在同一个请求内复用同一个 `get_memory_service()` 返回值。

- [ ] **Step 3: 如果 API 测试需要禁用记忆，增加 override**

若 `backend/tests/test_agent_api.py` 因 mem0 初始化失败而失败，在测试里覆盖依赖：

```python
from app.api.agent import get_memory_service


class NoopMemoryService:
    def add_from_user_message(self, content, member_id=None):
        pass

    def search_text(self, query, member_id=None, limit=5):
        return "未检索到相关记忆。"


client.app.dependency_overrides[get_memory_service] = lambda: NoopMemoryService()
```

把 override 放在已有测试 client fixture 或单测 setup 中，测试结束清理：

```python
client.app.dependency_overrides.pop(get_memory_service, None)
```

- [ ] **Step 4: 运行相关测试**

Run:

```bash
pytest backend/tests/test_memory_service.py backend/tests/test_agent_tools.py backend/tests/test_langchain_agent.py backend/tests/test_meal_plan_service.py backend/tests/test_agent_service.py backend/tests/test_agent_api.py -q
```

Expected: PASS。

- [ ] **Step 5: 运行更广测试**

Run:

```bash
pytest backend/tests -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/agent.py backend/tests/test_agent_api.py
git commit -m "feat: wire memory into agent api"
```

---

## Manual Verification

在本地服务可用且已配置 `HEALTH_AGENT_LLM_API_KEY` 后：

1. 启动后端。

```bash
uvicorn app.main:app --app-dir backend --reload
```

2. 创建会话并发送：

```text
爸爸不喜欢鱼
```

3. 继续发送：

```text
爸爸今晚吃什么
```

预期：

- Agent 调用 `meal_plan`。
- 餐单不出现鱼。
- 输出包含鸡胸肉/豆腐。
- 输出包含“个性化记忆：已避开爸爸不喜欢的鱼。”。
- 仍保留低钠、控糖、过敏等健康安全约束。

## Self-Review Checklist

- Spec 覆盖：P3 的 mem0、四类记忆、Agent 推荐前读取、餐单个性化均有任务覆盖。
- 范围控制：没有前端页面、本地记忆表、复杂审核流、证据链 UI。
- 类型一致：`MemoryService.search_text(query, member_id=None, limit=5)` 在 tool、meal plan 和测试中一致。
- 测试路径：每个行为都有对应 pytest。
- 风险点：真实 mem0 SDK 的 config 字段可能和版本有关；如果 `Memory.from_config(_mem0_config())` 报配置错误，执行时应先查当前安装版本文档，只调整 `_mem0_config()`，不要改变业务接口。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-15-p3-memory-system.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
