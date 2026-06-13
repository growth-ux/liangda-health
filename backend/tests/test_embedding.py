from http import HTTPStatus

from app.services.embedding import DashScopeEmbeddingService


def test_dashscope_embedding_service_calls_text_embedding_and_returns_vectors():
    calls = []

    def fake_call(model, input):
        calls.append((model, input))
        return {
            "status_code": HTTPStatus.OK,
            "output": {
                "embeddings": [
                    {"text_index": 0, "embedding": [0.1, 0.2]},
                    {"text_index": 1, "embedding": [0.3, 0.4]},
                ]
            },
        }

    service = DashScopeEmbeddingService(
        model="text-embedding-v3",
        api_key="secret",
        call=fake_call,
    )

    assert service.embed_many(["骨密度", "血糖"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert calls == [("text-embedding-v3", ["骨密度", "血糖"])]


def test_dashscope_embedding_service_requires_api_key():
    service = DashScopeEmbeddingService(model="text-embedding-v3")

    try:
        service.embed("骨密度")
    except RuntimeError as exc:
        assert str(exc) == "未配置 DashScope Embedding API Key"
    else:
        raise AssertionError("expected RuntimeError")
