from datetime import datetime

from fastapi.testclient import TestClient

from app.api.agent import get_agent_runner
from app.core.config import settings
from app.db.session import get_db
from app.main import create_app


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, messages):
        self.calls.append(messages)
        return {
            "content": "建议先查看最近报告里的血压和睡眠相关指标。",
            "token_prompt": 12,
            "token_completion": 8,
            "model_name": "qwen-plus",
        }

    def stream(self, messages):
        self.calls.append(messages)
        yield "建议"
        yield "先查看"
        yield "报告"


def make_client(db_session, runner=None):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    if runner is not None:
        app.dependency_overrides[get_agent_runner] = lambda: runner
    return TestClient(app)


def test_agent_session_lifecycle(db_session):
    client = make_client(db_session, FakeRunner())

    create_response = client.post("/api/agent/sessions", json={"title": "健康报告咨询"})
    list_response = client.get("/api/agent/sessions")

    assert create_response.status_code == 200
    assert create_response.json()["title"] == "健康报告咨询"
    assert create_response.json()["session_id"].startswith("sess_")
    assert list_response.status_code == 200
    assert list_response.json()[0]["title"] == "健康报告咨询"
    assert list_response.json()[0]["preview"] == ""


def test_agent_send_message_saves_user_and_assistant_messages(db_session):
    runner = FakeRunner()
    client = make_client(db_session, runner)
    session_id = client.post("/api/agent/sessions", json={"title": "新对话"}).json()["session_id"]

    response = client.post(
        f"/api/agent/sessions/{session_id}/messages:send",
        json={"content": "我妈这份报告有什么异常？"},
    )
    messages_response = client.get(f"/api/agent/sessions/{session_id}/messages")

    assert response.status_code == 200
    assert response.json()["user_message"]["role"] == "user"
    assert response.json()["assistant_message"]["content"] == "建议先查看最近报告里的血压和睡眠相关指标。"
    assert messages_response.status_code == 200
    assert [item["role"] for item in messages_response.json()["items"]] == ["user", "assistant"]
    assert runner.calls[0][-1]["content"] == "我妈这份报告有什么异常？"


def test_agent_stream_message_emits_events_and_saves_full_assistant_message(db_session):
    client = make_client(db_session, FakeRunner())
    session_id = client.post("/api/agent/sessions", json={"title": "新对话"}).json()["session_id"]

    with client.stream(
        "POST",
        f"/api/agent/sessions/{session_id}/messages:stream",
        json={"content": "血压偏高怎么办？"},
    ) as response:
        body = "".join(response.iter_text())

    messages = client.get(f"/api/agent/sessions/{session_id}/messages").json()["items"]
    assert response.status_code == 200
    assert "event: user_message" in body
    assert "event: assistant_start" in body
    assert body.index("event: user_message") < body.index("event: assistant_start") < body.index("event: delta")
    assert "event: assistant_done" in body
    assert "event: done" in body
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "建议先查看报告"


def test_agent_send_requires_llm_api_key_when_using_default_runner(db_session, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    client = make_client(db_session)
    session_id = client.post("/api/agent/sessions", json={"title": "新对话"}).json()["session_id"]

    response = client.post(
        f"/api/agent/sessions/{session_id}/messages:send",
        json={"content": "报告怎么看？"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "未配置模型 API Key"


def test_agent_send_rejects_blank_content(db_session):
    client = make_client(db_session, FakeRunner())
    session_id = client.post("/api/agent/sessions", json={"title": "新对话"}).json()["session_id"]

    response = client.post(
        f"/api/agent/sessions/{session_id}/messages:send",
        json={"content": "   "},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "消息内容不能为空"


def test_agent_messages_returns_404_for_missing_session(db_session):
    client = make_client(db_session, FakeRunner())

    response = client.get("/api/agent/sessions/sess_missing/messages")

    assert response.status_code == 404
    assert response.json()["detail"] == "会话不存在"
