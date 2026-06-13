import hashlib
import math
from collections.abc import Callable

import requests


class DeterministicEmbeddingService:
    """Small deterministic embedding for local development and tests."""

    def __init__(self, dimension: int = 64):
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for index, char in enumerate(text):
            digest = hashlib.sha256(f"{index}:{char}".encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return _normalize(vector)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class HttpEmbeddingService:
    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        post: Callable | None = None,
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.post = post or requests.post

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = self.post(
            self.endpoint,
            headers=headers,
            json={"texts": texts},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError("Embedding 响应缺少 embeddings 字段")
        return [[float(value) for value in embedding] for embedding in embeddings]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
