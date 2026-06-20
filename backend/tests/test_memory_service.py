from types import SimpleNamespace

from app.core.config import settings
from app.services.memory_service import MemoryService, _mem0_config


def test_mem0_dependency_is_installed():
    import mem0

    assert hasattr(mem0, "Memory")


class FakeMem0Client:
    def __init__(self, search_result=None):
        self.add_calls = []
        self.search_calls = []
        self.get_all_calls = []
        self.search_result = search_result or []

    def add(self, messages, user_id=None, metadata=None, infer=True, prompt=None):
        self.add_calls.append(
            {
                "messages": messages,
                "user_id": user_id,
                "metadata": metadata,
                "infer": infer,
                "prompt": prompt,
            }
        )
        return {"status": "ok"}

    def search(self, query, top_k=5, filters=None):
        self.search_calls.append(
            {
                "query": query,
                "top_k": top_k,
                "filters": filters,
            }
        )
        return self.search_result

    def get_all(self, filters=None, top_k=20):
        self.get_all_calls.append(
            {
                "filters": filters,
                "top_k": top_k,
            }
        )
        return self.search_result


def _members():
    return [
        SimpleNamespace(member_id="mem_dad", name="李建国", relation="爸爸"),
        SimpleNamespace(member_id="mem_mom", name="王丽", relation="妈妈"),
    ]


def test_memory_service_adds_member_message_with_member_id_as_user_id():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("爸爸不喜欢鱼")

    assert client.add_calls[0]["user_id"] == "mem_dad"
    assert client.add_calls[0]["messages"][0]["role"] == "user"
    assert "爸爸不喜欢鱼" in client.add_calls[0]["messages"][0]["content"]
    assert "记忆归属：mem_dad" in client.add_calls[0]["messages"][0]["content"]
    assert "记忆内容必须使用简体中文" in client.add_calls[0]["messages"][0]["content"]
    assert "memory 字段必须使用简体中文" in client.add_calls[0]["prompt"]
    assert client.add_calls[0]["infer"] is True
    assert client.add_calls[0]["metadata"] == {
        "source": "agent_user_message",
        "scope": "member",
        "member_id": "mem_dad",
    }


def test_memory_service_adds_family_message_with_default_family_user_id():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("我全家都不喜欢吃鱼")

    assert client.add_calls[0]["user_id"] == "default_family"
    assert client.add_calls[0]["metadata"] == {"source": "agent_user_message", "scope": "family"}


def test_memory_service_skips_ambiguous_message_without_owner():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("不喜欢吃鱼")

    assert client.add_calls == []


def test_memory_service_skips_one_off_recommendation_request():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("用户希望为全家推荐一款适合的食用油")

    assert client.add_calls == []


def test_memory_service_skips_health_fact_risk_question():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("用户关注爸爸的血脂情况，担心其血脂偏高是否需要干预，希望了解相关健康风险")

    assert client.add_calls == []


def test_memory_service_skips_goal_like_message():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("爸爸最近想控糖")

    assert client.add_calls == []


def test_memory_service_skips_preference_question_what_does_dad_not_eat():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("爸爸不喜欢吃什么")

    assert client.add_calls == []


def test_memory_service_skips_preference_question_what_does_mom_like():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("妈妈喜欢什么水果")

    assert client.add_calls == []


def test_memory_service_skips_avoidance_question_what_is_dad_allergic_to():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("爸爸对什么过敏")

    assert client.add_calls == []


def test_memory_service_skips_preference_question_can_dad_eat_seafood():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", member_provider=_members, enabled=True)

    service.add_from_user_message("爸爸可以吃海鲜吗")

    assert client.add_calls == []


def test_memory_service_searches_and_formats_results():
    client = FakeMem0Client(
        search_result=[
            {"memory": "爸爸不喜欢鱼", "metadata": {"memory_type": "avoidance", "member_id": "mem_dad"}},
            {"text": "妈妈最近想控糖", "metadata": {"memory_type": "goal", "member_id": "mem_mom"}},
        ]
    )
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    items = service.search("爸爸 饮食 排斥", member_id="mem_dad", limit=3)
    text = service.search_text("爸爸 饮食 排斥", member_id="mem_dad", limit=3)

    assert client.search_calls[0]["query"] == "爸爸 饮食 排斥"
    assert client.search_calls[0]["top_k"] == 3
    assert client.search_calls[0]["filters"] == {"user_id": "mem_dad"}
    assert items[0].content == "爸爸不喜欢鱼"
    assert items[0].memory_type == "avoidance"
    assert "[avoidance] 爸爸不喜欢鱼" in text
    assert "[goal] 妈妈最近想控糖" in text


def test_memory_service_dedupes_similar_search_results():
    client = FakeMem0Client(
        search_result=[
            {
                "memory": "用户关注父亲的血脂情况，担心其血脂偏高是否需要干预，希望了解相关健康风险，且父亲对鱼有回避倾向，不喜欢吃鱼。",
                "metadata": {"memory_type": "goal", "member_id": "mem_dad"},
            },
            {
                "memory": "用户关注父亲最近的血脂情况，担心其血脂偏高是否需要干预，且父亲对鱼有回避倾向，不喜欢吃鱼，因此晚餐安排中需避免鱼类食材。",
                "metadata": {"memory_type": "goal", "member_id": "mem_dad"},
            },
            {
                "memory": "爸爸最近想控糖",
                "metadata": {"memory_type": "goal", "member_id": "mem_dad"},
            },
        ]
    )
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    items = service.search("爸爸 血脂 晚餐", member_id="mem_dad", limit=5)
    text = service.search_text("爸爸 血脂 晚餐", member_id="mem_dad", limit=5)

    assert len(items) == 2
    assert "爸爸最近想控糖" in text
    assert text.count("血脂情况") + text.count("血脂偏高是否需要干预") >= 1


def test_memory_service_searches_family_memory_when_member_id_missing():
    client = FakeMem0Client(search_result=[{"memory": "全家不喜欢鱼"}])
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    service.search("全家 饮食 排斥")

    assert client.search_calls[0]["filters"] == {"user_id": "default_family"}


def test_memory_service_lists_profile_memories_by_member_without_similarity_query():
    client = FakeMem0Client(
        search_result=[
            {"memory": "爸爸不喜欢鱼", "metadata": {"memory_type": "avoidance", "member_id": "mem_dad"}},
            {"memory": "爸爸最近想控糖", "metadata": {"memory_type": "goal", "member_id": "mem_dad"}},
        ]
    )
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    items = service.list_profile_memories(member_id="mem_dad", limit=50)

    assert client.get_all_calls == [{"filters": {"user_id": "mem_dad"}, "top_k": 50}]
    assert client.search_calls == []
    assert [item.content for item in items] == ["爸爸不喜欢鱼", "爸爸最近想控糖"]
    assert [item.memory_type for item in items] == ["avoidance", "goal"]


def test_memory_service_lists_profile_memories_for_family_owner():
    client = FakeMem0Client(search_result=[{"memory": "全家周末在家做饭"}])
    service = MemoryService(client=client, family_user_id="default_family", enabled=True)

    service.list_profile_memories(limit=30)

    assert client.get_all_calls == [{"filters": {"user_id": "default_family"}, "top_k": 30}]


def test_memory_service_disabled_is_noop():
    client = FakeMem0Client()
    service = MemoryService(client=client, family_user_id="default_family", enabled=False)

    service.add_from_user_message("爸爸不喜欢鱼")
    items = service.search("爸爸 饮食 排斥")
    profile_items = service.list_profile_memories(member_id="mem_dad")

    assert client.add_calls == []
    assert client.search_calls == []
    assert items == []
    assert profile_items == []


def test_memory_service_disables_mem0_telemetry_before_import(monkeypatch):
    monkeypatch.delenv("MEM0_TELEMETRY", raising=False)
    monkeypatch.delenv("MEM0_DIR", raising=False)
    service = MemoryService(client=FakeMem0Client())

    assert service._get_client() is not None
    import os

    assert os.environ["MEM0_TELEMETRY"] == "false"
    assert os.environ["MEM0_DIR"] == str(settings.memory_dir)


def test_mem0_config_uses_dashscope_openai_compatible_llm_and_embedding(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(settings, "llm_api_key", "llm-key")
    monkeypatch.setattr(settings, "llm_model", "qwen-plus")
    monkeypatch.setattr(settings, "embedding_api_key", "embedding-key")
    monkeypatch.setattr(settings, "embedding_model", "text-embedding-v3")
    monkeypatch.setattr(settings, "embedding_dimension", 1024)
    monkeypatch.setattr(settings, "milvus_uri", "http://localhost:19530")
    monkeypatch.setattr(settings, "milvus_token", None)
    monkeypatch.setattr(settings, "memory_milvus_collection", "agent_memories_vector")
    monkeypatch.setattr(settings, "memory_history_db_path", settings.memory_dir / "history.db")

    config = _mem0_config()

    assert config["llm"]["provider"] == "openai"
    assert config["llm"]["config"]["model"] == "qwen-plus"
    assert config["llm"]["config"]["api_key"] == "llm-key"
    assert config["llm"]["config"]["openai_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config["embedder"]["provider"] == "openai"
    assert config["embedder"]["config"]["model"] == "text-embedding-v3"
    assert config["embedder"]["config"]["api_key"] == "embedding-key"
    assert config["embedder"]["config"]["openai_base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config["embedder"]["config"]["embedding_dims"] == 1024
    assert config["vector_store"]["provider"] == "milvus"
    assert config["vector_store"]["config"]["url"] == "http://localhost:19530"
    assert config["vector_store"]["config"]["token"] == ""
    assert config["vector_store"]["config"]["collection_name"] == "agent_memories_vector"
    assert config["vector_store"]["config"]["embedding_model_dims"] == 1024
    assert config["vector_store"]["config"]["metric_type"] == "COSINE"
    assert config["history_db_path"] == str(settings.memory_dir / "history.db")
    assert "preference、avoidance、marketing_feedback" in config["custom_instructions"]
    assert "不要记录健康禁忌" in config["custom_instructions"]
    assert "不要记录长期目标、阶段目标、照护意图" in config["custom_instructions"]
    assert "memory 字段必须使用简体中文" in config["custom_instructions"]
