"""Context Summarization 单测：SessionSummarizer + AgentService._history() 集成。"""
from unittest.mock import MagicMock

import pytest

from app.services.session_summarizer import SessionSummarizer


# ── SessionSummarizer ─────────────────────────────────────


def test_summarizer_returns_empty_for_no_messages():
    summarizer = SessionSummarizer(client=MagicMock())
    assert summarizer.summarize([]) == ""


def test_summarizer_llm_path():
    """LLM 可用时走 LLM 摘要路径。"""
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="用户讨论了爸爸的晚餐安排和低钠调味推荐。"))]
    )

    summarizer = SessionSummarizer(recent_keep=2, client=fake_client)
    messages = [
        {"role": "user", "content": "爸爸今晚吃什么"},
        {"role": "assistant", "content": "建议清蒸鱼配蔬菜"},
        {"role": "user", "content": "推荐低钠酱油"},
        {"role": "assistant", "content": "推荐六月鲜低钠酱油"},
    ]

    result = summarizer.summarize(messages)

    assert "晚餐" in result or "低钠" in result
    fake_client.chat.completions.create.assert_called_once()


def test_summarizer_fallback_when_no_client():
    """LLM 不可用时走规则化降级。"""
    summarizer = SessionSummarizer(recent_keep=2)
    # 强制 _get_client 返回 None
    summarizer._get_client = lambda: None

    messages = [
        {"role": "user", "content": "爸爸今晚吃什么"},
        {"role": "assistant", "content": "建议清蒸鱼配蔬菜"},
    ]

    result = summarizer.summarize(messages)

    assert "用户" in result
    assert "助手" in result
    assert len(result) > 0


def test_summarizer_fallback_when_llm_raises():
    """LLM 抛异常时降级到规则化摘要。"""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("llm timeout")

    summarizer = SessionSummarizer(recent_keep=2, client=fake_client)
    messages = [
        {"role": "user", "content": "全家早餐吃什么"},
        {"role": "assistant", "content": "燕麦牛奶和水果"},
    ]

    result = summarizer.summarize(messages)

    assert "用户" in result  # fallback 格式包含角色标签
    assert len(result) > 0


def test_summarizer_truncates_long_summary():
    """摘要超过 MAX_SUMMARY_CHARS 时被截断。"""
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="x" * 500))]
    )

    summarizer = SessionSummarizer(client=fake_client)
    result = summarizer.summarize([{"role": "user", "content": "hello"}])

    assert len(result) <= 200


# ── AgentService._history() 集成 ─────────────────────────


class FakeMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class FakeRepository:
    def __init__(self, messages):
        self._messages = messages

    def list_recent_messages(self, session_id, limit=8):
        return self._messages[-limit:]

    def get_session(self, session_id):
        return type("Session", (), {"session_id": session_id, "title": "test", "updated_at": None})()


def test_history_no_summarization_when_few_messages():
    """消息数 <= recent_keep 时不触发摘要，直接返回。"""
    from app.services.agent_service import AgentService

    messages = [
        FakeMessage("user", "你好"),
        FakeMessage("assistant", "你好，有什么可以帮您"),
    ]
    repo = FakeRepository(messages)
    summarizer = SessionSummarizer(recent_keep=4, client=MagicMock())
    service = AgentService(repository=repo, runner=None, session_summarizer=summarizer)

    history = service._history("sess_1")

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_history_summarizes_older_messages():
    """消息数 > recent_keep 时旧消息被压缩为摘要。"""
    from app.services.agent_service import AgentService

    messages = [
        FakeMessage("user", "爸爸今晚吃什么"),
        FakeMessage("assistant", "建议清蒸鱼"),
        FakeMessage("user", "配什么菜"),
        FakeMessage("assistant", "蒜蓉西兰花"),
        FakeMessage("user", "推荐低钠酱油"),
        FakeMessage("assistant", "推荐六月鲜"),
    ]
    repo = FakeRepository(messages)

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="用户讨论了爸爸晚餐安排"))]
    )
    summarizer = SessionSummarizer(recent_keep=4, client=fake_client)
    service = AgentService(repository=repo, runner=None, session_summarizer=summarizer)

    history = service._history("sess_1")

    # 第 1 条应该是 system 摘要
    assert history[0]["role"] == "system"
    assert "摘要" in history[0]["content"]
    assert "晚餐" in history[0]["content"]
    # 后面 4 条是最近消息
    assert len(history) == 5
    assert history[1]["content"] == "配什么菜"


def test_history_no_summarizer_returns_all():
    """没有 summarizer 时直接返回所有消息。"""
    from app.services.agent_service import AgentService

    messages = [FakeMessage("user", f"消息{i}") for i in range(10)]
    repo = FakeRepository(messages)
    service = AgentService(repository=repo, runner=None, session_summarizer=None)

    history = service._history("sess_1")

    assert len(history) == 10
    assert all(h["role"] == "user" for h in history)


def test_history_summarizer_skips_when_summary_empty():
    """摘要返回空字符串时不做替换，直接返回全部消息。"""
    from app.services.agent_service import AgentService

    messages = [FakeMessage("user", f"消息{i}") for i in range(6)]
    repo = FakeRepository(messages)

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=""))]
    )
    summarizer = SessionSummarizer(recent_keep=4, client=fake_client)
    service = AgentService(repository=repo, runner=None, session_summarizer=summarizer)

    history = service._history("sess_1")

    # 摘要为空，应该返回全部消息而不插入空的 system 消息
    assert len(history) == 6
    assert all(h["role"] == "user" for h in history)
