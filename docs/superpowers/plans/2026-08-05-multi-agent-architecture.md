# 多 Agent 架构（Supervisor + 专家团）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单 Agent 对话链路改造为 Supervisor + 3 专家 Agent 的多 Agent 架构，新增 `agent_activity` SSE 事件与前端协作条，用于决赛演示。

**Architecture:** `langchain_agent.py` 中的 `LangChainAgentRunner` 重命名抽取为 `BaseAgentRunner`（保留 run/stream 事件协议与全部解析函数）；新增 `MultiAgentRunner` 继承它，用 handoff 工具（`ask_meal_planner` / `ask_shopping_guide` / `ask_report_reader`）内嵌 3 个专家 `create_agent`。stream 用工作线程 + 事件队列合并 chunk 与协作事件。零新依赖，纯 LangChain。

**Tech Stack:** Python 3.13 / LangChain create_agent / FastAPI SSE / React + TypeScript

**Spec:** `docs/superpowers/specs/2026-08-05-multi-agent-architecture-design.md`

**注意事项（AGENTS.md）：**
- 不改动现有日志打印文案；搬运代码时原样保留 logger 语句
- 不做兜底双链路/配置开关，直接替换
- 测试命令统一：`cd /Users/tiger/PycharmProjects/liangda-health/backend && python -m pytest <路径> -v`

---

### Task 1: 抽取 BaseAgentRunner 基类（协议测试换名通过）

**Files:**
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/tests/test_langchain_agent.py`

目的：把 stream 的 chunk 处理逻辑抽成可复用方法 `_process_stream_chunk`，把商品提取抽成可覆写钩子 `_extract_products`，供 `MultiAgentRunner` 继承。本任务不改任何行为。

- [ ] **Step 1: 修改 langchain_agent.py**

1. 类名 `LangChainAgentRunner` → `BaseAgentRunner`（仅这一处定义，`SYSTEM_PROMPT_TEMPLATE` 本任务先保留）。
2. `run()` 中把 `product_recs = _extract_product_recommendations(response["messages"])` 改为 `product_recs = self._extract_products(response["messages"])`。
3. 新增钩子方法（放在 `run()` 之后）：

```python
    def _extract_products(self, messages) -> dict | None:
        return _extract_product_recommendations(messages)
```

4. `stream()` 的循环体替换为委托式（日志原样保留，只改结构）：

```python
        respond_args_state: dict[str, str] = {}
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            events, done = self._process_stream_chunk(chunk, respond_args_state)
            for event in events:
                yield event
            if done:
                return
        logger.warning(
            "agent stream finished without card args_state_keys=%s",
            list(respond_args_state.keys()),
        )
        fallback_card = self._fallback_evidence_card()
        if fallback_card is not None:
            logger.info("agent stream emit fallback evidence card")
            yield ("card", fallback_card)
```

（原 `respond_done` 变量及 mall/respond/AIMessageChunk 三段 if 整体移除——逻辑搬进下面的新方法；原 `if not respond_done:` 包裹的 fallback 段改为无条件走 fallback 判断。）

5. 新增 chunk 处理方法（从原 stream 循环逐段搬运，日志原样）：

```python
    def _process_stream_chunk(
        self, chunk, respond_args_state: dict[str, str]
    ) -> tuple[list[tuple], bool]:
        """处理单个 stream chunk，返回 (events, 终止标志)。终止为 True 表示已产出 respond 卡片。"""
        events: list[tuple] = []

        # 1) mall_recommend 工具：JSON 字符串 → 现有 product_recommendations 事件
        payload = _try_parse_mall_recommend_payload(chunk)
        if payload is not None and payload.get("items"):
            logger.info("agent stream emit product_recommendations item_count=%s", len(payload["items"]))
            events.append(("product_recommendations", payload))
            return events, False

        # 2) respond 工具的 ToolMessage → 整体解析为 card 事件
        if chunk.__class__.__name__ == "ToolMessage" and getattr(chunk, "name", None) == "respond":
            card = _parse_respond_payload(chunk) or _parse_respond_payload_from_args_state(
                respond_args_state,
                tool_call_id=getattr(chunk, "tool_call_id", None),
            )
            if card is None:
                raw_content = getattr(chunk, "content", "")
                logger.warning(
                    "agent stream respond payload invalid; raising. tool_call_id=%s raw_content=%r args_state_keys=%s",
                    getattr(chunk, "tool_call_id", None),
                    raw_content[:500] if isinstance(raw_content, str) else str(raw_content)[:500],
                    list(respond_args_state.keys()),
                )
                raise ResponseSchemaError("respond 工具参数不符合 StructuredResponse schema")
            card = self._apply_evidence_to_card(card)
            logger.info(
                "agent stream emit card kind=%s summary_chars=%s payload_keys=%s args_state_keys=%s",
                card.get("kind"),
                len(card.get("summary_text", "")),
                list((card.get("payload") or {}).keys()) if isinstance(card.get("payload"), dict) else [],
                list(respond_args_state.keys()),
            )
            events.append(("card", card))
            return events, True

        # 3) AIMessageChunk：respond args 增量 → delta；普通文本 → delta
        if chunk.__class__.__name__ == "AIMessageChunk":
            tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
            respond_chunk_text = _extract_respond_summary_text_delta(tool_call_chunks, respond_args_state)
            if respond_chunk_text:
                logger.info(
                    "agent stream emit delta from respond summary chars=%s args_state_keys=%s",
                    len(respond_chunk_text),
                    list(respond_args_state.keys()),
                )
                events.append(("delta", respond_chunk_text))
            text = _content_to_text(getattr(chunk, "content", ""))
            if text:
                logger.info("agent stream emit delta from content chars=%s", len(text))
                events.append(("delta", text))
            return events, False

        logger.info("agent stream skip internal_message type=%s", chunk.__class__.__name__)
        return events, False
```

- [ ] **Step 2: 测试文件全局替换类名**

`backend/tests/test_langchain_agent.py` 中把所有 `LangChainAgentRunner` 替换为 `BaseAgentRunner`（含 import 行）。

- [ ] **Step 3: 运行测试验证全绿**

Run: `cd /Users/tiger/PycharmProjects/liangda-health/backend && python -m pytest tests/test_langchain_agent.py -v`
Expected: 全部 PASS（数量与改造前一致）

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "refactor: 抽取 BaseAgentRunner 基类与 chunk 处理方法"
```

---

### Task 2: MultiAgentRunner 骨架（提示词 + 工具注册 + handoff）

**Files:**
- Create: `backend/app/services/multi_agent.py`
- Test: `backend/tests/test_multi_agent.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_multi_agent.py`**

```python
import json
import queue

import pytest

from app.core.config import settings
from app.services.langchain_agent import LlmConfigError
from app.services.multi_agent import (
    MEAL_PLANNER_PROMPT_TEMPLATE,
    REPORT_READER_PROMPT_TEMPLATE,
    SHOPPING_GUIDE_PROMPT_TEMPLATE,
    MultiAgentRunner,
)


class FakeMember:
    def __init__(self, member_id, name, relation):
        self.member_id = member_id
        self.name = name
        self.relation = relation


def test_supervisor_tools_registered(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = MultiAgentRunner()

    tools = runner._tools()
    names = [getattr(t, "name", None) or t.__name__ for t in tools]

    assert names == ["ask_meal_planner", "ask_shopping_guide", "ask_report_reader", "respond"]


def test_expert_tools_split_by_domain():
    runner = MultiAgentRunner(
        meal_plan_tool=object(),
        memory_tool=object(),
        mall_recommend_tool=object(),
        kb_tool=object(),
    )

    assert [t.__name__ for t in runner._meal_planner_tools()] == ["meal_plan", "memory_search"]
    assert [t.__name__ for t in runner._shopping_guide_tools()] == ["mall_recommend"]
    assert [t.__name__ for t in runner._report_reader_tools()] == ["kb_search"]


def test_supervisor_prompt_routes_experts():
    runner = MultiAgentRunner(member_provider=lambda: [FakeMember("mem_1", "张三", "本人")])

    prompt = runner._system_prompt()

    assert "ask_meal_planner" in prompt
    assert "ask_shopping_guide" in prompt
    assert "ask_report_reader" in prompt
    assert "张三" in prompt
    assert "mem_1" in prompt
    for kind in ["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]:
        assert kind in prompt
    assert "必须调用 respond" in prompt.replace("`", "")


def test_expert_prompts_focus_on_own_domain():
    runner = MultiAgentRunner()

    meal = runner._expert_prompt(MEAL_PLANNER_PROMPT_TEMPLATE)
    assert "memory_search" in meal and "meal_plan" in meal

    shop = runner._expert_prompt(SHOPPING_GUIDE_PROMPT_TEMPLATE)
    assert "mall_recommend" in shop

    report = runner._expert_prompt(REPORT_READER_PROMPT_TEMPLATE)
    assert "kb_search" in report


def test_run_expert_invokes_expert_and_returns_text(monkeypatch):
    runner = MultiAgentRunner()
    calls = []

    def fake_invoke(agent_key, task):
        calls.append((agent_key, task))
        return "晚餐：清蒸鱼配杂粮饭"

    monkeypatch.setattr(runner, "_expert_invoke", fake_invoke)

    result = runner._run_expert("meal_planner", "全家晚餐，少油")

    assert result == "晚餐：清蒸鱼配杂粮饭"
    assert calls == [("meal_planner", "全家晚餐，少油")]


def test_run_expert_exception_returns_error_text(monkeypatch):
    runner = MultiAgentRunner()

    def fake_invoke(agent_key, task):
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "_expert_invoke", fake_invoke)

    result = runner._run_expert("shopping_guide", "推荐油")

    assert result == "Error: 专家处理失败"


def test_handoff_tools_delegate_to_run_expert(monkeypatch):
    runner = MultiAgentRunner()
    seen = []
    monkeypatch.setattr(runner, "_run_expert", lambda key, task: seen.append((key, task)) or "专家结果")

    tools = {t.__name__: t for t in runner._tools() if not hasattr(t, "name")}
    assert tools["ask_meal_planner"]("做晚餐") == "专家结果"
    assert tools["ask_shopping_guide"]("推荐油") == "专家结果"
    assert tools["ask_report_reader"]("看报告") == "专家结果"
    assert [key for key, _ in seen] == ["meal_planner", "shopping_guide", "report_reader"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_multi_agent.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.multi_agent`）

- [ ] **Step 3: 实现 `backend/app/services/multi_agent.py`（本步只含骨架部分）**

```python
import json
import logging
import queue
import threading

from app.core.config import settings
from app.services.langchain_agent import (
    BaseAgentRunner,
    _build_members_block,
    _content_to_text,
)
from app.services.llm_logging import log_llm_request

logger = logging.getLogger(__name__)


AGENT_LABELS = {
    "supervisor": "调度中心",
    "meal_planner": "餐单规划师",
    "shopping_guide": "商品导购师",
    "report_reader": "报告解读师",
}


SUPERVISOR_PROMPT_TEMPLATE = """你是粮达健康的家庭健康管家「总调度 Agent」。你不直接干活，而是把任务分派给手下三位专家 Agent，再汇总他们的结果回复用户。

专家工具：
- ask_meal_planner(task)：餐单规划师，处理"吃什么/三餐/今晚做什么"类问题，他会自己查记忆和生成餐单。
- ask_shopping_guide(task)：商品导购师，处理商品/类目推荐。任务里带餐单文本时按餐单推荐；用户只问某类商品（油/米/调料/坚果/牛奶/零食等）时把用户原问题写进任务，不要先找餐单规划师。
- ask_report_reader(task)：报告解读师，只有用户明确问报告/体检结果时才调用，任务里写清家人和问题。

调度规则：
1. 三餐/吃什么问题：先调 ask_meal_planner；拿到餐单后，把餐单文本原样写进 ask_shopping_guide 的任务里继续推荐商品。
2. 纯商品/类目问题：直接调 ask_shopping_guide。
3. 专家返回以 "Error:" 开头的结果时，温和降级说明（如"暂时无法推荐商品"），同一专家最多重试 1 次。
4. 简单寒暄、普通健康问答不需要调度专家，直接调用 respond。
{members_block}
回复风格：
1. 用简体中文回答，不做诊断，不替代医生。
2. 语气像日常健康顾问，回复短一点、口语一点，优先说用户马上能理解和执行的做法。
3. 商品推荐结果会由系统自动附加商品卡片，不要把商品名、价格、推荐理由写进你的文本回复。
4. 餐单/报告解读这类信息密集回复，summary_text 只写"结论 + 关键安排 + 注意点"。
5. 餐单份量默认用日常说法（一小碗、一盘、一杯、一掌心），不要展开克数；只有用户明确要求精确克数或热量时才给。
6. 【硬性禁止】面向用户的文本中绝不能出现 member_id、session_id 等内部标识符，称呼家人用姓名或家庭称呼。

【硬性要求】完成一次用户回复必须调用 respond 工具，不能直接用普通文本对用户说话。respond 参数：
- kind：5 选 1——meal_plan / qa / greeting / kb_interpretation / general_advice
- summary_text：Markdown 摘要（≤400字），易扫读，可用少量加粗、emoji、短列表
- payload：按 kind 决定的结构化字段：
  * meal_plan.payload：scope / target_member_name / meal_items[] (slot/title/summary) / member_adjustments[] (member_name/note/tags) / avoid_tags[] / extra_note
  * qa.payload：question_topic / answer / tips[]
  * greeting.payload：message / suggested_topics[]
  * kb_interpretation.payload：topic / evidence[] (source/excerpt) / suggestions[] (text/priority) / red_flags[]
  * general_advice.payload：topic / advice / cautions[]
完成专家调度后立即调用 respond，调完不要再追加任何普通文本。
"""


MEAL_PLANNER_PROMPT_TEMPLATE = """你是粮达健康的「餐单规划师」专家 Agent，只对总调度负责，不直接面对用户。
工作流程：
1. 先用 memory_search 查询任务涉及家人（或全家）的饮食偏好和排斥；明确指向某位家人时传 member_id，全家不传。
2. 再调用 meal_plan 生成餐单：scope/member_id 按任务判断，全家用 family。
3. 把 meal_plan 返回的餐单文本作为最终回复原样返回，不要加评论、不要改写。
4. 任何工具返回 "Error:" 开头时，直接把该 Error 文本作为最终回复返回。
5. 记忆只能用于个性化表达，不能覆盖过敏、健康禁忌和健康安全约束。
6. 最终回复中不得出现 member_id 等内部标识符。
{members_block}
"""


SHOPPING_GUIDE_PROMPT_TEMPLATE = """你是粮达健康的「商品导购师」专家 Agent，只对总调度负责。
工作流程：
1. 任务里带餐单文本时：调用 mall_recommend，把餐单文本原样作为 meal_plan_text；scope/member_id 与任务描述一致，全家用 family。
2. 任务只问某类商品时：meal_plan_text 留空，把用户原问题放进 query_text。
3. 把 mall_recommend 返回的原始结果字符串作为最终回复原样返回，不要改写或总结。
4. 工具返回 "Error:" 开头时，直接原样返回该 Error 文本。
{members_block}
"""


REPORT_READER_PROMPT_TEMPLATE = """你是粮达健康的「报告解读师」专家 Agent，只对总调度负责。
工作流程：
1. 按任务中的 member_id 调用 kb_search 检索报告片段；跨家人对比时对每位家人分别检索再合成。
2. 基于检索结果给出简洁解读：说明来自哪份报告或页码，不做诊断，不替代医生。
3. 检索无结果或工具返回 "Error:" 时如实说明。
4. 最终回复中不得出现 member_id 等内部标识符，称呼家人用姓名或家庭称呼。
{members_block}
"""


class MultiAgentRunner(BaseAgentRunner):
    """Supervisor + 3 专家 Agent 的多 Agent runner，接口与 BaseAgentRunner 一致。"""

    SYSTEM_PROMPT_TEMPLATE = SUPERVISOR_PROMPT_TEMPLATE

    def __init__(self, kb_tool=None, meal_plan_tool=None, memory_tool=None, mall_recommend_tool=None, member_provider=None):
        super().__init__(
            kb_tool=kb_tool,
            meal_plan_tool=meal_plan_tool,
            memory_tool=memory_tool,
            mall_recommend_tool=mall_recommend_tool,
            member_provider=member_provider,
        )
        self._activity_queue = None
        self._product_payloads = []
        self._experts_cache = None

    # ---- 提示词 ----

    def _expert_prompt(self, template: str) -> str:
        return template.format(members_block=_build_members_block(self.member_provider()))

    # ---- 工具注册 ----

    def _tools(self):
        def ask_meal_planner(task: str) -> str:
            """把三餐/吃什么类任务交给餐单规划师。task 里写清用户诉求、scope（family/member）和 member_id。"""
            return self._run_expert("meal_planner", task)

        def ask_shopping_guide(task: str) -> str:
            """把商品推荐任务交给商品导购师。带餐单时 task 原样附餐单文本；只问商品类目时写用户原问题。"""
            return self._run_expert("shopping_guide", task)

        def ask_report_reader(task: str) -> str:
            """把报告检索和解读任务交给报告解读师。task 里写清 member_id 和用户问题。"""
            return self._run_expert("report_reader", task)

        from app.services.langchain_agent import _RESPOND_TOOL

        return [ask_meal_planner, ask_shopping_guide, ask_report_reader, _RESPOND_TOOL]

    def _meal_planner_tools(self):
        tools = []
        if self.meal_plan_tool is not None:
            def meal_plan(scope: str, member_id: str | None = None, goal: str | None = None, meal_type: str = "day") -> str:
                """根据单人或全家健康状态生成一日三餐或指定餐次建议。"""
                logger.info("expert tool call name=meal_plan scope=%s member_id=%s meal_type=%s", scope, member_id, meal_type)
                return self.meal_plan_tool.build(scope=scope, member_id=member_id, goal=goal, meal_type=meal_type)

            tools.append(meal_plan)
        if self.memory_tool is not None:
            def memory_search(query: str, member_id: str | None = None, limit: int = 5) -> str:
                """检索家庭或指定家人的长期互动记忆，包括偏好、排斥、阶段目标。"""
                logger.info("expert tool call name=memory_search member_id=%s limit=%s", member_id, limit)
                return self.memory_tool.search(query=query, member_id=member_id, limit=limit)

            tools.append(memory_search)
        return tools

    def _shopping_guide_tools(self):
        tools = []
        if self.mall_recommend_tool is not None:
            def mall_recommend(scope: str, member_id: str | None = None, meal_plan_text: str = "", query_text: str = "", limit: int = 5) -> str:
                """根据餐单文本或商品类目问题推荐商城商品。"""
                logger.info("expert tool call name=mall_recommend scope=%s member_id=%s limit=%s", scope, member_id, limit)
                raw = self.mall_recommend_tool.recommend(
                    scope=scope,
                    member_id=member_id,
                    meal_plan_text=meal_plan_text,
                    query_text=query_text,
                    limit=limit,
                )
                self._capture_product_payload(raw)
                return raw

            tools.append(mall_recommend)
        return tools

    def _report_reader_tools(self):
        tools = []
        if self.kb_tool is not None:
            def kb_search(query: str, member_id: str, top_k: int = 5) -> str:
                """检索指定家人的健康报告片段。"""
                logger.info("expert tool call name=kb_search member_id=%s top_k=%s", member_id, top_k)
                return self.kb_tool.search(query=query, member_id=member_id, top_k=top_k)

            tools.append(kb_search)
        return tools

    # ---- 专家执行 ----

    def _run_expert(self, agent_key: str, task: str) -> str:
        logger.info("multi_agent expert start agent=%s task_chars=%s", agent_key, len(task))
        self._emit_activity(agent_key, "start", f"{AGENT_LABELS[agent_key]}正在处理…")
        try:
            result = self._expert_invoke(agent_key, task)
        except Exception:
            logger.exception("multi_agent expert failed agent=%s", agent_key)
            result = "Error: 专家处理失败"
        self._emit_activity(agent_key, "done", f"{AGENT_LABELS[agent_key]}完成")
        logger.info("multi_agent expert done agent=%s output_chars=%s", agent_key, len(result))
        return result

    def _expert_invoke(self, agent_key: str, task: str) -> str:
        from langchain_core.messages import HumanMessage

        expert = self._expert_agents()[agent_key]
        response = expert.invoke({"messages": [HumanMessage(content=task)]})
        return _content_to_text(response["messages"][-1].content)

    def _expert_agents(self) -> dict:
        if self._experts_cache is None:
            from langchain.agents import create_agent

            model = self._model()
            self._experts_cache = {
                "meal_planner": create_agent(
                    model=model,
                    tools=self._meal_planner_tools(),
                    system_prompt=self._expert_prompt(MEAL_PLANNER_PROMPT_TEMPLATE),
                ),
                "shopping_guide": create_agent(
                    model=model,
                    tools=self._shopping_guide_tools(),
                    system_prompt=self._expert_prompt(SHOPPING_GUIDE_PROMPT_TEMPLATE),
                ),
                "report_reader": create_agent(
                    model=model,
                    tools=self._report_reader_tools(),
                    system_prompt=self._expert_prompt(REPORT_READER_PROMPT_TEMPLATE),
                ),
            }
        return self._experts_cache

    def _emit_activity(self, agent: str, action: str, detail: str = "") -> None:
        if self._activity_queue is not None:
            self._activity_queue.put(("activity", {"agent": agent, "action": action, "detail": detail}))
```

注意：`BaseAgentRunner` 需要支持子类覆盖 `SYSTEM_PROMPT_TEMPLATE`——检查 Task 1 后的 `_system_prompt`，如果它硬编码引用模块级 `SYSTEM_PROMPT_TEMPLATE`，改为 `self.SYSTEM_PROMPT_TEMPLATE`（`BaseAgentRunner` 上加类属性 `SYSTEM_PROMPT_TEMPLATE = SYSTEM_PROMPT_TEMPLATE`）。

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_multi_agent.py -v`
Expected: 7 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/multi_agent.py backend/app/services/langchain_agent.py backend/tests/test_multi_agent.py
git commit -m "feat: MultiAgentRunner 骨架——Supervisor/专家提示词与 handoff 工具"
```

---

### Task 3: 商品结构捕获 + run() 路径

**Files:**
- Modify: `backend/app/services/multi_agent.py`
- Test: `backend/tests/test_multi_agent.py`

- [ ] **Step 1: 追加失败测试到 `test_multi_agent.py`**

```python
def test_capture_product_payload_pushes_to_queue():
    runner = MultiAgentRunner()
    runner._activity_queue = queue.Queue()
    raw = json.dumps(
        {"items": [{"product_id": "p_oil", "name": "橄榄油"}], "is_error": False},
        ensure_ascii=False,
    )

    runner._capture_product_payload(raw)

    assert runner._product_payloads == [json.loads(raw)]
    assert runner._activity_queue.get() == ("product", json.loads(raw))


def test_capture_product_payload_ignores_error_string():
    runner = MultiAgentRunner()
    runner._activity_queue = queue.Queue()

    runner._capture_product_payload("Error: 单人商品推荐必须传入 member_id")

    assert runner._product_payloads == []
    assert runner._activity_queue.empty()


def test_multi_agent_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    runner = MultiAgentRunner()

    with pytest.raises(LlmConfigError, match="未配置模型 API Key"):
        runner.run([{"role": "user", "content": "报告怎么看？"}])


def test_multi_agent_run_returns_card_and_captured_products(monkeypatch):
    from langchain_core.messages import AIMessage, ToolMessage

    class FakeSupervisorAgent:
        def __init__(self, runner):
            self.runner = runner

        def invoke(self, payload):
            # 模拟导购师专家在 invoke 内部完成 mall_recommend 并捕获结构化商品
            self.runner._capture_product_payload(json.dumps(
                {"items": [{
                    "product_id": "p_x", "name": "藜麦", "reason": "高纤维",
                    "price_text": "¥39.9", "image_url": None, "image_emoji": "🌾", "score": 80,
                }], "is_error": False, "error": None},
                ensure_ascii=False,
            ))
            ai = AIMessage(content="", tool_calls=[{
                "name": "respond",
                "id": "c1",
                "args": {
                    "kind": "qa",
                    "summary_text": "推荐如下",
                    "payload": {"question_topic": "商品", "answer": "藜麦", "tips": []},
                },
            }])
            tool_msg = ToolMessage(content="ok", tool_call_id="c1", name="respond")
            return {"messages": [ai, tool_msg]}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = MultiAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeSupervisorAgent(runner))

    result = runner.run([{"role": "user", "content": "推荐点杂粮"}])

    assert result["content"] == "推荐如下"
    assert result["card"]["kind"] == "qa"
    assert result["product_recommendations"]["items"][0]["product_id"] == "p_x"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_multi_agent.py -v -k "capture or run"`
Expected: FAIL（`_capture_product_payload` 不存在）

- [ ] **Step 3: 在 `multi_agent.py` 的 MultiAgentRunner 追加实现**

```python
    # ---- 商品结构捕获 ----

    def _capture_product_payload(self, raw: str) -> None:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list) or not parsed["items"]:
            return
        self._product_payloads.append(parsed)
        if self._activity_queue is not None:
            self._activity_queue.put(("product", parsed))

    # ---- run()：商品改从专家捕获结果取 ----

    def run(self, messages):
        self._product_payloads = []
        return super().run(messages)

    def _extract_products(self, messages) -> dict | None:
        return self._product_payloads[-1] if self._product_payloads else None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_multi_agent.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/multi_agent.py backend/tests/test_multi_agent.py
git commit -m "feat: MultiAgentRunner run 路径与商品结构化捕获"
```

---

### Task 4: stream() 工作线程 + 事件队列

**Files:**
- Modify: `backend/app/services/multi_agent.py`
- Test: `backend/tests/test_multi_agent.py`

- [ ] **Step 1: 追加失败测试到 `test_multi_agent.py`**

```python
def test_multi_agent_stream_emits_activity_product_delta_card_in_order(monkeypatch):
    from langchain_core.messages import AIMessageChunk, ToolMessage
    from langchain_core.messages.tool import ToolCallChunk

    class FakeSupervisor:
        def __init__(self, runner):
            self.runner = runner

        def stream(self, payload, stream_mode):
            # 模拟 handoff 工具在工作线程里执行：专家 activity 和商品事件直接入队
            self.runner._activity_queue.put(("activity", {"agent": "meal_planner", "action": "start", "detail": "餐单规划师正在处理…"}))
            self.runner._activity_queue.put(("activity", {"agent": "meal_planner", "action": "done", "detail": "餐单规划师完成"}))
            self.runner._activity_queue.put(("product", {"items": [{"product_id": "p_oil"}]}))
            yield AIMessageChunk(
                content="",
                tool_call_chunks=[ToolCallChunk(
                    name="respond",
                    args='{"kind": "qa", "summary_text": "你好", "payload": {"question_topic": "t", "answer": "a", "tips": []}}',
                    index=0,
                    id="call_1",
                )],
            ), {}
            yield ToolMessage(content="ok", tool_call_id="call_1", name="respond"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = MultiAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeSupervisor(runner))

    events = list(runner.stream([{"role": "user", "content": "今晚吃什么"}]))

    kinds = [kind for kind, _ in events]
    assert kinds == [
        "agent_activity",  # supervisor start
        "agent_activity",  # meal_planner start
        "agent_activity",  # meal_planner done
        "product_recommendations",
        "delta",
        "card",
        "agent_activity",  # supervisor done
    ]
    activities = [payload for kind, payload in events if kind == "agent_activity"]
    assert activities[0] == {"agent": "supervisor", "action": "start", "detail": "调度中心解析意图中"}
    assert activities[1]["agent"] == "meal_planner"
    assert activities[-1] == {"agent": "supervisor", "action": "done", "detail": "调度中心完成"}
    products = [payload for kind, payload in events if kind == "product_recommendations"]
    assert products[0]["items"][0]["product_id"] == "p_oil"
    deltas = [payload for kind, payload in events if kind == "delta"]
    assert "".join(deltas) == "你好"
    cards = [payload for kind, payload in events if kind == "card"]
    assert cards[0]["kind"] == "qa"


def test_multi_agent_stream_worker_error_propagates(monkeypatch):
    class FakeSupervisor:
        def stream(self, payload, stream_mode):
            raise RuntimeError("llm down")
            yield  # noqa: 让函数成为生成器

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = MultiAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeSupervisor())

    with pytest.raises(RuntimeError, match="llm down"):
        list(runner.stream([{"role": "user", "content": "x"}]))


def test_multi_agent_stream_fallback_evidence_card_when_no_respond(monkeypatch):
    from langchain_core.messages import AIMessageChunk
    from app.schemas.agent_response import EvidenceItem
    from app.services.agent_evidence import AgentEvidenceCollector

    class FakeSupervisor:
        def stream(self, payload, stream_mode):
            yield AIMessageChunk(content="直接文本收尾"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = MultiAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeSupervisor())

    collector = AgentEvidenceCollector()
    collector.add_product(EvidenceItem(
        type="product", title="低钠盐", excerpt="契合低钠方向",
        source_id="prod_1", source_label="商城标签匹配",
    ))
    monkeypatch.setattr(runner, "_attach_evidence_collector", lambda: collector)
    runner._evidence_collector = collector

    events = list(runner.stream([{"role": "user", "content": "x"}]))

    cards = [payload for kind, payload in events if kind == "card"]
    assert len(cards) == 1
    assert cards[0]["summary_text"] == ""
    assert cards[0]["evidence"]["product_items"][0]["type"] == "product"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_multi_agent.py -v -k stream`
Expected: FAIL（stream 未覆写，无 agent_activity 事件）

- [ ] **Step 3: 在 MultiAgentRunner 追加 stream 覆写**

```python
    # ---- stream()：工作线程 + 事件队列 ----

    def stream(self, messages):
        self._ensure_api_key()
        logger.info("multi_agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        self._product_payloads = []
        self._activity_queue = queue.Queue()
        self._attach_evidence_collector()
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        log_llm_request(
            logger,
            service="multi_agent.stream",
            payload={
                "model": settings.llm_model,
                "base_url": settings.llm_base_url,
                "temperature": settings.llm_temperature,
                "timeout": settings.llm_timeout_seconds,
                "system_prompt": self._system_prompt(),
                "messages": prepared_messages,
            },
        )

        def worker():
            try:
                for chunk, _metadata in agent.stream(
                    {"messages": self._to_langchain_messages(prepared_messages)},
                    stream_mode="messages",
                ):
                    self._activity_queue.put(("chunk", chunk))
            except Exception as exc:
                logger.exception("multi_agent stream worker failed")
                self._activity_queue.put(("error", exc))
            finally:
                self._activity_queue.put(("sentinel", None))

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()

        yield ("agent_activity", {"agent": "supervisor", "action": "start", "detail": "调度中心解析意图中"})

        respond_args_state: dict[str, str] = {}
        finished_by_card = False
        while True:
            kind, payload = self._activity_queue.get()
            if kind == "sentinel":
                break
            if kind == "error":
                self._activity_queue = None
                raise payload
            if kind == "activity":
                logger.info("multi_agent stream emit agent_activity agent=%s action=%s", payload.get("agent"), payload.get("action"))
                yield ("agent_activity", payload)
                continue
            if kind == "product":
                logger.info("multi_agent stream emit product_recommendations item_count=%s", len(payload.get("items") or []))
                yield ("product_recommendations", payload)
                continue
            events, done = self._process_stream_chunk(payload, respond_args_state)
            for event in events:
                yield event
            if done:
                finished_by_card = True
                break

        if finished_by_card:
            # respond 之后抽干工作线程余量，避免线程泄漏；残余事件全部丢弃
            while True:
                drain_kind, _drain_payload = self._activity_queue.get()
                if drain_kind == "sentinel":
                    break
            self._activity_queue = None
            yield ("agent_activity", {"agent": "supervisor", "action": "done", "detail": "调度中心完成"})
            return

        logger.warning("multi_agent stream finished without card")
        fallback_card = self._fallback_evidence_card()
        if fallback_card is not None:
            logger.info("multi_agent stream emit fallback evidence card")
            yield ("card", fallback_card)
        self._activity_queue = None
        yield ("agent_activity", {"agent": "supervisor", "action": "done", "detail": "调度中心完成"})
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_multi_agent.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 回归旧协议测试**

Run: `python -m pytest tests/test_langchain_agent.py -v`
Expected: 全部 PASS（基类未受影响）

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/multi_agent.py backend/tests/test_multi_agent.py
git commit -m "feat: MultiAgentRunner 流式协作事件（工作线程+事件队列）"
```

---

### Task 5: API 依赖注入切换 + 全量回归

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 替换 runner 注入**

`backend/app/api/agent.py`：
- import 行 `from app.services.langchain_agent import LangChainAgentRunner` 改为 `from app.services.multi_agent import MultiAgentRunner`
- `get_agent_runner` 中 `return LangChainAgentRunner(` 改为 `return MultiAgentRunner(`（参数不变）

- [ ] **Step 2: 全量后端测试**

Run: `cd /Users/tiger/PycharmProjects/liangda-health/backend && python -m pytest tests -v`
Expected: 全部 PASS（`test_agent_api.py` / `test_agent_service.py` 依赖 runner 接口签名，不应受影响；若个别测试直接 patch 了 `LangChainAgentRunner`，同步改为 `MultiAgentRunner`）

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/agent.py backend/tests
git commit -m "feat: 对话链路切换到 MultiAgentRunner"
```

---

### Task 6: 删除旧 SYSTEM_PROMPT_TEMPLATE 与失效测试

**Files:**
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: 删除旧模板**

`langchain_agent.py` 删除模块级 `SYSTEM_PROMPT_TEMPLATE = """..."""` 整段（第 16~73 行附近）。`BaseAgentRunner` 的类属性改为 `SYSTEM_PROMPT_TEMPLATE = ""`（基类不承载真实提示词，真实链路由 `MultiAgentRunner.SYSTEM_PROMPT_TEMPLATE` 提供；`_build_members_block([])` 的"当前没有可用家人"断言不受影响，因为它直接测函数）。

- [ ] **Step 2: 清理 test_langchain_agent.py 中依赖旧 prompt 的测试**

删除以下测试（其断言对象已不存在；等价语义已由 `test_multi_agent.py` 的 supervisor/专家 prompt 测试覆盖）：
- `test_langchain_agent_system_prompt_prefers_daily_portions`
- `test_runner_system_prompt_includes_member_list`
- `test_runner_system_prompt_empty_when_no_members`
- `test_runner_system_prompt_includes_memory_rules`
- `test_runner_system_prompt_requires_mall_recommend_after_meal_plan`
- `test_runner_system_prompt_routes_category_product_queries_to_mall_recommend`
- `test_runner_system_prompt_requires_respond_tool`
- `test_runner_system_prompt_documents_kinds`

其余测试（协议解析、respond schema、members block、format_summary_text、证据链）全部保留。

- [ ] **Step 3: 运行两个测试文件验证**

Run: `python -m pytest tests/test_langchain_agent.py tests/test_multi_agent.py -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/langchain_agent.py backend/tests/test_langchain_agent.py
git commit -m "refactor: 删除旧单 Agent system prompt 与失效断言"
```

---

### Task 7: 前端 agent_activity 协议 + AgentTeamStrip 协作条

**Files:**
- Modify: `frontend/src/api/agent.ts`
- Create: `frontend/src/components/chat/AgentTeamStrip.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: agent.ts 增加事件协议**

`frontend/src/api/agent.ts`：

1. 在 `QuickAction` 类型定义之后新增：

```typescript
export type AgentActivityPayload = {
  agent: 'supervisor' | 'meal_planner' | 'shopping_guide' | 'report_reader';
  action: 'start' | 'done';
  detail?: string;
};
```

2. `StreamCallbacks` 增加一行：

```typescript
  onAgentActivity?: (payload: AgentActivityPayload) => void;
```

3. `handleSseEvent` 中 `if (event === 'card')` 行之后新增：

```typescript
  if (event === 'agent_activity') callbacks.onAgentActivity?.(data);
```

- [ ] **Step 2: 新建 `frontend/src/components/chat/AgentTeamStrip.tsx`**

```tsx
import type { AgentActivityPayload } from '../../api/agent';

export type TeamAgentKey = AgentActivityPayload['agent'];

export type TeamAgentState = {
  status: 'idle' | 'working' | 'done';
  detail: string;
};

export type TeamState = Record<TeamAgentKey, TeamAgentState>;

export const INITIAL_TEAM_STATE: TeamState = {
  supervisor: { status: 'idle', detail: '' },
  meal_planner: { status: 'idle', detail: '' },
  shopping_guide: { status: 'idle', detail: '' },
  report_reader: { status: 'idle', detail: '' }
};

const TEAM_AGENTS: { key: TeamAgentKey; label: string; emoji: string }[] = [
  { key: 'supervisor', label: '调度中心', emoji: '🧭' },
  { key: 'meal_planner', label: '餐单规划师', emoji: '🥗' },
  { key: 'shopping_guide', label: '商品导购师', emoji: '🛒' },
  { key: 'report_reader', label: '报告解读师', emoji: '📋' }
];

export function applyTeamActivity(state: TeamState, payload: AgentActivityPayload): TeamState {
  return {
    ...state,
    [payload.agent]: {
      status: payload.action === 'start' ? 'working' : 'done',
      detail: payload.detail ?? ''
    }
  };
}

export function AgentTeamStrip({ team }: { team: TeamState }) {
  const activeDetail = TEAM_AGENTS.map(({ key }) => team[key])
    .filter((item) => item.status === 'working')
    .map((item) => item.detail)
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="agent-team-strip">
      <div className="agent-team-nodes">
        {TEAM_AGENTS.map(({ key, label, emoji }) => (
          <span key={key} className={`agent-team-node agent-team-node-${team[key].status}`}>
            <span className="agent-team-emoji">{emoji}</span>
            <span className="agent-team-label">{label}</span>
            {team[key].status === 'done' && <span className="agent-team-check">✓</span>}
          </span>
        ))}
      </div>
      {activeDetail && <div className="agent-team-detail">{activeDetail}</div>}
    </div>
  );
}
```

- [ ] **Step 3: ChatPage.tsx 接入协作条**

1. import 区新增：

```typescript
import { AgentTeamStrip, INITIAL_TEAM_STATE, applyTeamActivity } from '../components/chat/AgentTeamStrip';
import type { TeamState } from '../components/chat/AgentTeamStrip';
```

2. `ChatPage` 组件 state 区（`modalState` 之后）新增：

```typescript
  const [teamState, setTeamState] = useState<TeamState>(INITIAL_TEAM_STATE);
  const [teamVisible, setTeamVisible] = useState(false);
```

3. `handleSend` 中 `setSendError(null);` 之后新增：

```typescript
    setTeamState(INITIAL_TEAM_STATE);
    setTeamVisible(true);
```

4. `sendMutation` 回调中，`onCard` 之后新增：

```typescript
        onAgentActivity: (payload) => {
          setTeamState((prev) => applyTeamActivity(prev, payload));
        },
```

5. `onAssistantDone` 回调体末尾新增（流式结束 1.5 秒后淡出隐藏）：

```typescript
          setTimeout(() => setTeamVisible(false), 1500);
```

6. `onError` 回调体开头新增 `setTeamVisible(false);`。

7. 渲染区：`<MessageList` 之前新增：

```tsx
          {teamVisible && <AgentTeamStrip team={teamState} />}
```

- [ ] **Step 4: styles.css 追加样式（文件末尾）**

```css
/* 多 Agent 协作条：流式回复期间展示调度与专家工作进度 */
.agent-team-strip {
  padding: 8px 16px 0;
}
.agent-team-nodes {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.agent-team-node {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  color: #94a3b8;
  font-size: 12px;
  background: #fff;
  transition: all 0.3s ease;
}
.agent-team-node-working {
  color: #2563eb;
  border-color: #93c5fd;
  background: #eff6ff;
  animation: agent-team-pulse 1.2s ease-in-out infinite;
}
.agent-team-node-done {
  color: #16a34a;
  border-color: #bbf7d0;
  background: #f0fdf4;
}
.agent-team-check {
  font-weight: 700;
}
.agent-team-detail {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}
@keyframes agent-team-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
```

- [ ] **Step 5: 前端构建验证**

Run: `cd /Users/tiger/PycharmProjects/liangda-health/frontend && npm run build`
Expected: 构建成功无类型错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/agent.ts frontend/src/components/chat/AgentTeamStrip.tsx frontend/src/pages/ChatPage.tsx frontend/src/styles.css
git commit -m "feat: 前端多 Agent 协作条（agent_activity 事件）"
```

---

### Task 8: 端到端验收

**Files:** 无代码改动（验证为主）

- [ ] **Step 1: 全量后端测试**

Run: `cd /Users/tiger/PycharmProjects/liangda-health/backend && python -m pytest tests -v`
Expected: 全部 PASS

- [ ] **Step 2: 前端构建**

Run: `cd /Users/tiger/PycharmProjects/liangda-health/frontend && npm run build`
Expected: 构建成功

- [ ] **Step 3: 手动验收（启动前后端后逐项检查）**

启动：后端 `python -m uvicorn app.main:app`（backend 目录），前端 `npm run dev`（frontend 目录）。

1. 发送「今晚全家吃什么」：协作条依次点亮 🧭 调度中心 → 🥗 餐单规划师 → 🛒 商品导购师；最终出现餐单卡片 + 商品卡片；打字机效果不中断
2. 发送报告相关问题（如「爸爸的体检报告有什么要注意」）：协作条点亮 📋 报告解读师；证据链 tab 正常展示
3. 发送「推荐一款适合全家人的油」：只点亮 🛒 商品导购师（不经过餐单规划师）
4. 刷新页面：消息与卡片正常回显（协作条不出现，符合"不持久化"设计）

- [ ] **Step 4: 如有修复则提交，最后打 tag 式提交收尾**

```bash
git add -A
git commit -m "chore: 多 Agent 架构验收修复" # 仅当有改动时
```
