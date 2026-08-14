import json
import queue

import pytest

from app.core.config import settings
from app.services.agent.langchain_agent import LlmConfigError
from app.services.agent.multi_agent import (
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
    assert "调用了 ask_meal_planner" in prompt
    assert "respond.kind 必须是 meal_plan" in prompt


def test_expert_prompts_focus_on_own_domain():
    runner = MultiAgentRunner()

    meal = runner._expert_prompt(MEAL_PLANNER_PROMPT_TEMPLATE)
    assert "memory_search" in meal and "meal_plan" in meal

    shop = runner._expert_prompt(SHOPPING_GUIDE_PROMPT_TEMPLATE)
    assert "mall_recommend" in shop

    report = runner._expert_prompt(REPORT_READER_PROMPT_TEMPLATE)
    assert "report_facts" in report


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
        "delta",
        "card",
        "product_recommendations",  # 延迟到 card 之后再推送
        "agent_activity",  # supervisor done
    ]
    activities = [payload for kind, payload in events if kind == "agent_activity"]
    assert activities[0]["agent"] == "supervisor"
    assert activities[0]["action"] == "start"
    assert activities[0]["user_query"] == "今晚吃什么"
    assert activities[1]["agent"] == "meal_planner"
    assert activities[-1]["agent"] == "supervisor"
    assert activities[-1]["action"] == "done"
    assert "elapsed_seconds" in activities[-1]
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
    from app.services.agent.agent_evidence import AgentEvidenceCollector

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
