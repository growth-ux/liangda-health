import json

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
        yield ("delta", "收到")


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


def test_agent_service_stream_emits_product_recommendations_sse(db_session):
    """mall_recommend 工具结果应作为独立 SSE 事件发出，assistant 消息写入结构化字段。"""

    class StructuredRunner:
        def run(self, messages):
            return {"content": "ok"}

        def stream(self, messages):
            yield ("delta", "先看餐单。")
            yield (
                "product_recommendations",
                {
                    "items": [
                        {
                            "product_id": "p_oil",
                            "name": "低芥酸菜籽油",
                            "reason": "契合少油",
                            "price_text": "¥69.9",
                            "image_url": None,
                            "image_emoji": "🫒",
                            "score": 80,
                        }
                    ],
                    "is_error": False,
                    "error": None,
                },
            )
            yield ("delta", "推荐就放在下方卡片。")

    service = AgentService(SqlAlchemyAgentRepository(db_session), StructuredRunner())
    session = service.create_session("新对话")

    events = "".join(service.stream_message(session.session_id, "今晚做什么适合全家"))

    assert "event: product_recommendations" in events
    assert '"product_id": "p_oil"' in events
    assert "event: assistant_done" in events
    # assistant_done 也应携带 product_recommendations
    assert '"product_recommendations"' in events

    # DB 写入验证
    repo = SqlAlchemyAgentRepository(db_session)
    messages = repo.list_messages(session.session_id)
    assistant_messages = [m for m in messages if m.role == "assistant"]
    assert len(assistant_messages) == 1
    stored = json.loads(assistant_messages[0].product_recommendations)
    assert stored[0]["product_id"] == "p_oil"


def test_agent_service_stream_omits_product_recommendations_when_no_match(db_session):
    """runner 没产出 product_recommendations 事件时，assistant 消息应保持 product_recommendations 为 NULL。"""

    class PlainRunner:
        def run(self, messages):
            return {"content": "ok"}

        def stream(self, messages):
            yield ("delta", "只有文字，没有商品。")

    service = AgentService(SqlAlchemyAgentRepository(db_session), PlainRunner())
    session = service.create_session("新对话")

    events = "".join(service.stream_message(session.session_id, "妈妈最近睡眠不好"))

    assert "event: product_recommendations" not in events
    assert "event: assistant_done" in events

    repo = SqlAlchemyAgentRepository(db_session)
    messages = repo.list_messages(session.session_id)
    assistant_messages = [m for m in messages if m.role == "assistant"]
    assert assistant_messages[0].product_recommendations is None


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