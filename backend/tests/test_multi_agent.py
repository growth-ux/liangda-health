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
