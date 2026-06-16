from app.repositories.agent_repository import SqlAlchemyAgentRepository
from app.services.agent_service import AgentService
from app.services.langchain_agent import LlmConfigError


class StaticRunner:
    def run(self, messages):
        return {
            "content": f"收到：{messages[-1]['content']}",
            "token_prompt": 3,
            "token_completion": 4,
            "model_name": "qwen-plus",
        }

    def stream(self, messages):
        yield "收到"


class MissingKeyRunner:
    def run(self, messages):
        raise LlmConfigError("未配置模型 API Key")

    def stream(self, messages):
        raise LlmConfigError("未配置模型 API Key")


class FakeMemoryService:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def add_from_user_message(self, content, member_id=None):
        self.calls.append((content, member_id))
        if self.fail:
            raise RuntimeError("memory failed")


def test_agent_service_creates_session_and_lists_preview(db_session):
    service = AgentService(SqlAlchemyAgentRepository(db_session), StaticRunner())
    session = service.create_session("新对话")

    user_message, assistant_message = service.send_message(session.session_id, "报告怎么看？")
    sessions = service.list_sessions()

    assert user_message.role == "user"
    assert assistant_message.content == "收到：报告怎么看？"
    assert assistant_message.token_prompt == 3
    assert assistant_message.token_completion == 4
    assert assistant_message.model_name == "qwen-plus"
    assert sessions[0]["session_id"] == session.session_id
    assert sessions[0]["title"] == "报告怎么看？"
    assert sessions[0]["preview"] == "收到：报告怎么看？"


def test_agent_service_maps_missing_api_key_to_http_error(db_session):
    service = AgentService(SqlAlchemyAgentRepository(db_session), MissingKeyRunner())
    session = service.create_session("健康咨询")

    try:
        service.send_message(session.session_id, "报告怎么看？")
    except Exception as exc:
        assert exc.status_code == 500
        assert exc.detail == "未配置模型 API Key"
    else:
        raise AssertionError("expected missing API key error")


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
