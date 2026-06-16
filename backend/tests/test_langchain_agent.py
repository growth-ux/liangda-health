import json

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


class FakeMallRecommendTool:
    def __init__(self):
        self.calls = []

    def recommend(self, scope, meal_plan_text, member_id=None, limit=5):
        self.calls.append((scope, meal_plan_text, member_id, limit))
        return {
            "items": [
                {
                    "product_id": "p_salt",
                    "name": "低钠盐",
                    "reason": "契合低钠方向",
                    "price_text": "¥15.9",
                    "image_url": None,
                    "image_emoji": "🧂",
                    "score": 80,
                }
            ],
            "is_error": False,
            "error": None,
        }


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


def test_langchain_agent_registers_mall_recommend_tool_returns_structured_dict(monkeypatch):
    """LangChain 工具 wrapper 把 service 的 dict 直接返回给 runner（runner 自己负责后续结构化）。"""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    mall_tool = FakeMallRecommendTool()
    runner = LangChainAgentRunner(mall_recommend_tool=mall_tool)

    tools = runner._tools()
    result = tools[0](scope="member", member_id="mem_dad", meal_plan_text="晚餐：低钠杂粮饭", limit=2)

    assert mall_tool.calls == [("member", "晚餐：低钠杂粮饭", "mem_dad", 2)]
    # 工具返回值是结构化 dict，runner 会按结构解析；不再是 "可选商品：" markdown 文本
    assert result["items"][0]["product_id"] == "p_salt"
    assert isinstance(result, dict)
    assert "可选商品" not in str(result)


def test_langchain_agent_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    runner = LangChainAgentRunner()

    with pytest.raises(LlmConfigError, match="未配置模型 API Key"):
        runner.run([{"role": "user", "content": "报告怎么看？"}])


def test_langchain_agent_stream_emits_summary_text_deltas_from_respond_tool_call(monkeypatch):
    """LLM 调 respond 工具时，summary_text 字段在 tool_call_chunks 里逐渐生成，stream() 把它的 token 作为 delta 发出。"""
    from langchain_core.messages import AIMessageChunk
    from langchain_core.messages.tool import ToolCallChunk

    class FakeAgent:
        def stream(self, payload, stream_mode):
            # 第一次 chunk：开始 tool call，args 是 '{"kind": "qa", "summary_text": "你'
            chunk1 = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    ToolCallChunk(name="respond", args='{"kind": "qa", "summary_text": "你', index=0, id="call_1"),
                ],
            )
            yield chunk1, {}
            # 第二次 chunk：args 增加 '好"，payload: {...}'
            chunk2 = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    ToolCallChunk(name="respond", args='好", "payload": {"question_topic": "t", "answer": "a", "tips": []}}', index=0, id="call_1"),
                ],
            )
            yield chunk2, {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    deltas = [p for k, p in runner.stream([{"role": "user", "content": "x"}]) if k == "delta"]
    assert "".join(deltas) == "你好"


def test_langchain_agent_stream_emits_structured_events(monkeypatch):
    from langchain_core.messages import AIMessageChunk, ToolMessage

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield AIMessageChunk(content="首先，"), {}
            # kb_search 工具结果：不是 mall_recommend，应当被忽略（不进 delta 也不进 product_recommendations）
            yield ToolMessage(
                content="[报告片段 1]\n文档：体检报告\n页码：3\n内容：谷丙转氨酶",
                tool_call_id="call_1",
                name="kb_search",
            ), {}
            # mall_recommend 工具结果：JSON 字符串，应当产出 product_recommendations 事件
            yield ToolMessage(
                content=json.dumps(
                    {
                        "items": [
                            {
                                "product_id": "p_oil",
                                "name": "低芥酸菜籽油",
                                "reason": "契合少油方向",
                                "price_text": "¥69.9",
                                "image_url": None,
                                "image_emoji": "🫒",
                                "score": 80,
                            }
                        ],
                        "is_error": False,
                        "error": None,
                    },
                    ensure_ascii=False,
                ),
                tool_call_id="call_2",
                name="mall_recommend",
            ), {}
            yield AIMessageChunk(content="爸爸报告里的转氨酶正常。"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "今晚做什么适合全家"}]))

    deltas = [payload for kind, payload in events if kind == "delta"]
    product_events = [payload for kind, payload in events if kind == "product_recommendations"]

    assert deltas == ["首先，", "爸爸报告里的转氨酶正常。"]
    assert "报告片段" not in "".join(deltas)
    assert len(product_events) == 1
    assert product_events[0]["items"][0]["product_id"] == "p_oil"


def test_langchain_agent_stream_skips_mall_recommend_error_payload(monkeypatch):
    """mall_recommend 返回的 "Error: ..." 字符串无法被解析为 JSON，不应产生 product_recommendations 事件。"""
    from langchain_core.messages import AIMessageChunk, ToolMessage

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield ToolMessage(
                content="Error: 单人商品推荐必须传入 member_id",
                tool_call_id="call_1",
                name="mall_recommend",
            ), {}
            yield AIMessageChunk(content="暂时无法推荐商品。"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "给我爸爸推荐点商品"}]))

    product_events = [payload for kind, payload in events if kind == "product_recommendations"]
    assert product_events == []
    deltas = [payload for kind, payload in events if kind == "delta"]
    assert deltas == ["暂时无法推荐商品。"]


def test_langchain_agent_run_extracts_product_recommendations(monkeypatch):
    """run() 返回的 dict 应包含 product_recommendations 字段，从 messages 里解析 mall_recommend ToolMessage。"""
    from langchain_core.messages import AIMessage, ToolMessage

    class FakeAgent:
        def invoke(self, payload):
            mall_payload = json.dumps(
                {
                    "items": [
                        {
                            "product_id": "p_x",
                            "name": "藜麦",
                            "reason": "高纤维",
                            "price_text": "¥39.9",
                            "image_url": None,
                            "image_emoji": "🌾",
                            "score": 80,
                        }
                    ],
                    "is_error": False,
                    "error": None,
                },
                ensure_ascii=False,
            )
            respond_payload = json.dumps(
                {
                    "kind": "qa",
                    "summary_text": "全家晚餐建议...",
                    "payload": {"question_topic": "晚餐", "answer": "清淡为主", "tips": []},
                },
                ensure_ascii=False,
            )
            return {
                "messages": [
                    ToolMessage(content=mall_payload, tool_call_id="call_1", name="mall_recommend"),
                    ToolMessage(content=respond_payload, tool_call_id="call_2", name="respond"),
                    AIMessage(content="全家晚餐建议..."),
                ]
            }

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    result = runner.run([{"role": "user", "content": "今晚做什么适合全家"}])

    assert result["content"] == "全家晚餐建议..."
    assert result["product_recommendations"]["items"][0]["product_id"] == "p_x"


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


def test_runner_system_prompt_requires_mall_recommend_after_meal_plan():
    runner = LangChainAgentRunner()

    prompt = runner._system_prompt()

    assert "mall_recommend" in prompt
    assert "meal_plan 工具返回的餐单文本" in prompt
    # 关键：商品卡片由系统自动附加，LLM 不再把商品名写入文本
    assert "不要" in prompt
    assert "写进自己的文本回复" in prompt


def test_langchain_agent_registers_respond_tool(monkeypatch):
    """respond 工具的 schema 来自 StructuredResponse.model_json_schema()，且必含 kind/summary_text/payload。"""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()

    tools = runner._tools()
    respond = next(t for t in tools if t.name == "respond")

    # 工具存在
    assert respond is not None
    # 工具参数 schema 来自 StructuredResponse
    params = respond.args
    assert "kind" in params
    assert "summary_text" in params
    assert "payload" in params
    # kind 是枚举
    assert set(params["kind"]["enum"]) == {
        "meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"
    }


def test_langchain_agent_respond_tool_callable(monkeypatch):
    """respond 工具被 LLM 调用时直接返回 'ok'（payload 在 tool_call args 里，不在 result 里）。"""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()

    tools = runner._tools()
    respond = next(t for t in tools if t.name == "respond")

    result = respond.invoke(
        {
            "kind": "qa",
            "summary_text": "你好",
            "payload": {"question_topic": "测试", "answer": "测试回答", "tips": []},
        }
    )
    assert result == "ok"


def test_langchain_agent_stream_emits_card_event_for_respond(monkeypatch):
    """respond 工具返回后，stream() 产出 ('card', StructuredResponse-like dict) 事件。"""
    from langchain_core.messages import AIMessageChunk, ToolMessage

    card_args = {
        "kind": "qa",
        "summary_text": "你好",
        "payload": {"question_topic": "早餐", "answer": "高蛋白", "tips": []},
    }
    import json

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield AIMessageChunk(content="先回一句"), {}
            yield ToolMessage(
                content=json.dumps(card_args, ensure_ascii=False),
                tool_call_id="call_1",
                name="respond",
            ), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "早餐吃什么"}]))
    card_events = [p for k, p in events if k == "card"]
    deltas = [p for k, p in events if k == "delta"]

    assert len(card_events) == 1
    assert card_events[0]["kind"] == "qa"
    assert card_events[0]["payload"]["answer"] == "高蛋白"
    # 现有 delta 仍正常
    assert deltas == ["先回一句"]


def test_langchain_agent_stream_raises_on_invalid_respond_payload(monkeypatch):
    """respond 工具的 ToolMessage 解析失败抛 ResponseSchemaError。"""
    from langchain_core.messages import ToolMessage
    from app.services.langchain_agent import ResponseSchemaError

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield ToolMessage(
                content='{"kind": "nonsense", "summary_text": "x", "payload": {}}',
                tool_call_id="call_1",
                name="respond",
            ), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    with pytest.raises(ResponseSchemaError):
        list(runner.stream([{"role": "user", "content": "x"}]))


def test_langchain_agent_stream_drops_aimessage_after_respond(monkeypatch):
    """LLM 调了 respond 之后又发普通 AIMessage 文字，stream() 丢弃并 warn。"""
    from langchain_core.messages import AIMessageChunk, ToolMessage
    import json

    card_args = {
        "kind": "qa",
        "summary_text": "s",
        "payload": {"question_topic": "q", "answer": "a", "tips": []},
    }

    class FakeAgent:
        def stream(self, payload, stream_mode):
            yield ToolMessage(
                content=json.dumps(card_args, ensure_ascii=False),
                tool_call_id="call_1",
                name="respond",
            ), {}
            # 绕过工具直接说话 → 应被丢弃
            yield AIMessageChunk(content="这段不该给用户看到"), {}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    events = list(runner.stream([{"role": "user", "content": "x"}]))
    deltas = [p for k, p in events if k == "delta"]
    assert deltas == []


def test_langchain_agent_run_extracts_card(monkeypatch):
    """run() 同步路径应从 respond ToolMessage 提取 card 字段，校验失败抛 ResponseSchemaError。"""
    from langchain_core.messages import AIMessage, ToolMessage
    from app.services.langchain_agent import ResponseSchemaError
    import json

    card_args = {
        "kind": "qa",
        "summary_text": "你好",
        "payload": {"question_topic": "早餐", "answer": "高蛋白", "tips": []},
    }

    class FakeAgent:
        def invoke(self, payload):
            return {
                "messages": [
                    ToolMessage(
                        content=json.dumps(card_args, ensure_ascii=False),
                        tool_call_id="call_1",
                        name="respond",
                    ),
                    AIMessage(content="已生成回复"),
                ]
            }

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    result = runner.run([{"role": "user", "content": "早餐"}])
    assert result["card"] is not None
    assert result["card"]["kind"] == "qa"
    assert result["card"]["payload"]["answer"] == "高蛋白"


def test_langchain_agent_run_raises_when_no_respond(monkeypatch):
    """run() 路径 LLM 没调 respond 抛 ResponseSchemaError。"""
    from langchain_core.messages import AIMessage
    from app.services.langchain_agent import ResponseSchemaError

    class FakeAgent:
        def invoke(self, payload):
            return {"messages": [AIMessage(content="直接说话没用")]}

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    with pytest.raises(ResponseSchemaError):
        runner.run([{"role": "user", "content": "x"}])


def test_langchain_agent_run_raises_on_invalid_respond_payload(monkeypatch):
    """respond ToolMessage 存在但 payload 不合法时，run() 抛 ResponseSchemaError。"""
    from langchain_core.messages import ToolMessage
    from app.services.langchain_agent import ResponseSchemaError

    class FakeAgent:
        def invoke(self, payload):
            return {
                "messages": [
                    ToolMessage(
                        content='{"kind":"bogus"}',
                        tool_call_id="c1",
                        name="respond",
                    ),
                ]
            }

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    runner = LangChainAgentRunner()
    monkeypatch.setattr(runner, "_agent", lambda: FakeAgent())

    with pytest.raises(ResponseSchemaError):
        runner.run([{"role": "user", "content": "x"}])


def test_runner_system_prompt_requires_respond_tool():
    """system_prompt 必须明确要求 LLM 调用 respond 工具才算完成回复。"""
    runner = LangChainAgentRunner()
    prompt = runner._system_prompt()
    assert "respond" in prompt
    assert "必须调用" in prompt or "只能通过" in prompt


def test_runner_system_prompt_documents_kinds():
    """system_prompt 必须列出 5 个 kind 的选择规则。"""
    runner = LangChainAgentRunner()
    prompt = runner._system_prompt()
    for kind in ["meal_plan", "qa", "greeting", "kb_interpretation", "general_advice"]:
        assert kind in prompt
