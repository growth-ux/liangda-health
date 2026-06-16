import hashlib

from langchain.embeddings.base import Embeddings
from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class LiangdaTestEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        return [byte / 255 for byte in digest[:10]]


class LiangdaTestChatModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "liangda-test-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='{"memory": []}'))])


def test_mem0_real_memory_add_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("MEM0_DIR", str(tmp_path / "mem0-home"))
    monkeypatch.setenv("MEM0_TELEMETRY", "false")
    from mem0 import Memory
    import mem0.memory.main as mem0_main

    monkeypatch.setattr(mem0_main, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(mem0_main, "mem0_dir", str(tmp_path / "mem0-home"))

    config = {
        "llm": {
            "provider": "langchain",
            "config": {"model": LiangdaTestChatModel()},
        },
        "embedder": {
            "provider": "langchain",
            "config": {
                "model": LiangdaTestEmbeddings(),
                "embedding_dims": 10,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "liangda_memory_test",
                "embedding_model_dims": 10,
                "path": str(tmp_path / "qdrant"),
            },
        },
        "history_db_path": str(tmp_path / "history.db"),
    }
    memory = Memory.from_config(config)

    add_result = memory.add("爸爸不喜欢鱼", user_id="test_family", infer=False)
    search_result = memory.search("爸爸不喜欢鱼", filters={"user_id": "test_family"}, top_k=3, threshold=0.0)

    assert add_result["results"][0]["event"] == "ADD"
    assert add_result["results"][0]["memory"] == "爸爸不喜欢鱼"
    assert search_result["results"]
    assert search_result["results"][0]["memory"] == "爸爸不喜欢鱼"
