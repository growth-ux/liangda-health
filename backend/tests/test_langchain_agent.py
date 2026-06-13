import pytest

from app.core.config import settings
from app.services.langchain_agent import LangChainAgentRunner, LlmConfigError


class FakeKbTool:
    def __init__(self):
        self.queries = []

    def search(self, query, top_k=5):
        self.queries.append(query)
        return "[报告片段 1]\n文档：体检报告\n页码：1\n内容：血压偏高"


def test_langchain_agent_registers_kb_search_tool(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    kb_tool = FakeKbTool()
    runner = LangChainAgentRunner(kb_tool=kb_tool)

    tools = runner._tools()
    result = tools[0]("这份报告有什么异常？", top_k=3)

    assert kb_tool.queries == ["这份报告有什么异常？"]
    assert "血压偏高" in result


def test_langchain_agent_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    runner = LangChainAgentRunner()

    with pytest.raises(LlmConfigError, match="未配置模型 API Key"):
        runner.run([{"role": "user", "content": "报告怎么看？"}])


def test_langchain_agent_does_not_duplicate_system_prompt():
    runner = LangChainAgentRunner()

    messages = runner._to_langchain_messages([{"role": "user", "content": "报告怎么看？"}])

    assert len(messages) == 1
    assert messages[0].content == "报告怎么看？"


def test_langchain_agent_appends_kb_context_to_latest_user_message():
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
    assert "可参考的报告上下文" in messages[-1]["content"]
    assert "血压偏高" in messages[-1]["content"]
