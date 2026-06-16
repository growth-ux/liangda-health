import pytest

from app.core.config import settings
from app.services.langchain_agent import (
    LangChainAgentRunner,
    LlmConfigError,
    _build_members_block,
)


class FakeKbTool:
    def __init__(self):
        self.queries = []

    def search(self, query, member_id=None, top_k=5):
        self.queries.append((query, member_id, top_k))
        return "[报告片段 1]\n文档：体检报告\n页码：1\n内容：血压偏高"


class FakeMealPlanTool:
    def __init__(self):
        self.calls = []

    def build(self, scope, member_id=None, goal=None, meal_type="day"):
        self.calls.append((scope, member_id, goal, meal_type))
        return "早餐：燕麦牛奶\n午餐：杂粮饭\n晚餐：豆腐青菜"


class FakeMemoryTool:
    def __init__(self):
        self.calls = []

    def search(self, query, member_id=None, limit=5):
        self.calls.append((query, member_id, limit))
        return "[avoidance] 爸爸不喜欢鱼"


class FakeMember:
    def __init__(self, member_id, name, relation):
        self.member_id = member_id
        self.name = name
        self.relation = relation


def test_langchain_agent_registers_kb_search_tool(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    kb_tool = FakeKbTool()
    runner = LangChainAgentRunner(kb_tool=kb_tool)

    tools = runner._tools()
    result = tools[0]("这份报告有什么异常？", member_id="mem_1", top_k=3)

    assert kb_tool.queries == [("这份报告有什么异常？", "mem_1", 3)]
    assert "血压偏高" in result


def test_langchain_agent_registers_meal_plan_tool(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    meal_plan_tool = FakeMealPlanTool()
    runner = LangChainAgentRunner(meal_plan_tool=meal_plan_tool)

    tools = runner._tools()
    result = tools[0](scope="family", member_id=None, goal="清淡", meal_type="day")

    assert meal_plan_tool.calls == [("family", None, "清淡", "day")]
    assert "早餐" in result


def test_langchain_agent_registers_memory_search_tool(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    memory_tool = FakeMemoryTool()
    runner = LangChainAgentRunner(memory_tool=memory_tool)

    tools = runner._tools()
    result = tools[0](query="爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert memory_tool.calls == [("爸爸 饮食 排斥", "mem_dad", 3)]
    assert "爸爸不喜欢鱼" in result


def test_langchain_agent_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    runner = LangChainAgentRunner()

    with pytest.raises(LlmConfigError, match="未配置模型 API Key"):
        runner.run([{"role": "user", "content": "报告怎么看？"}])


def test_langchain_agent_stream_skips_tool_messages(monkeypatch):
    from langchain_core.messages import AIMessageChunk, ToolMessage

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield AIMessageChunk(content="首先，"), {}
            yield ToolMessage(
                content="[报告片段 1]\n文档：体检报告\n页码：3\n内容：谷丙转氨酶",
                tool_call_id="call_1",
            ), {}
            yield AIMessageChunk(content="爸爸报告里的转氨酶正常。"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    chunks = list(runner.stream([{"role": "user", "content": "爸爸报告里能不能吃鱼？"}]))

    assert chunks == ["首先，", "爸爸报告里的转氨酶正常。"]
    assert "报告片段" not in "".join(chunks)


def test_langchain_agent_does_not_duplicate_system_prompt():
    runner = LangChainAgentRunner()

    messages = runner._to_langchain_messages([{"role": "user", "content": "报告怎么看？"}])

    assert len(messages) == 1
    assert messages[0].content == "报告怎么看？"


def test_langchain_agent_kb_context_is_noop_now_that_llm_drives_search():
    """_append_kb_context is a no-op; the LLM now calls kb_search as a tool with member_id."""
    kb_tool = FakeKbTool()
    runner = LangChainAgentRunner(kb_tool=kb_tool)

    messages = runner._append_kb_context(
        [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，我可以帮你看健康报告。"},
            {"role": "user", "content": "这份报告有什么异常？"},
        ]
    )

    assert messages[0]["content"] == "你好"
    assert "可参考的报告上下文" not in messages[-1]["content"]
    assert kb_tool.queries == []


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
    assert "家庭健康智能营销 Agent" in prompt
    assert "餐单建议" in prompt
    assert "商品推荐" in prompt


def test_runner_system_prompt_empty_when_no_members():
    runner = LangChainAgentRunner(member_provider=lambda: [])

    prompt = runner._system_prompt()

    assert "当前没有可用家人" in prompt


def test_runner_system_prompt_includes_memory_rules():
    runner = LangChainAgentRunner()

    prompt = runner._system_prompt()

    assert "memory_search" in prompt
    assert "记忆只能用于个性化表达" in prompt
    assert "不能覆盖过敏" in prompt
