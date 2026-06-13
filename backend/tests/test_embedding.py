from app.services.embedding import DeterministicEmbeddingService
from app.services.embedding import HttpEmbeddingService


def test_deterministic_embedding_has_expected_dimension_and_is_stable():
    service = DeterministicEmbeddingService(dimension=8)

    first = service.embed("骨密度异常")
    second = service.embed("骨密度异常")

    assert len(first) == 8
    assert first == second
    assert any(value != 0 for value in first)


def test_http_embedding_service_posts_texts_and_returns_vectors():
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return FakeResponse()

    service = HttpEmbeddingService(
        endpoint="https://embedding.example/v1/embed",
        api_key="secret",
        post=fake_post,
    )

    assert service.embed_many(["骨密度", "血糖"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert calls == [
        (
            "https://embedding.example/v1/embed",
            {"Authorization": "Bearer secret"},
            {"texts": ["骨密度", "血糖"]},
            60,
        )
    ]
