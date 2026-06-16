from collections.abc import Callable
from http import HTTPStatus
import logging

import dashscope

logger = logging.getLogger(__name__)


class DashScopeEmbeddingService:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        call: Callable | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.call = call or dashscope.TextEmbedding.call

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("未配置 DashScope Embedding API Key")

        total_chars = sum(len(text) for text in texts)
        logger.info(
            "embedding request start provider=dashscope model=%s text_count=%s total_chars=%s",
            self.model,
            len(texts),
            total_chars,
        )
        dashscope.api_key = self.api_key
        response = self.call(model=self.model, input=texts)
        status_code = _get_value(response, "status_code")
        if status_code != HTTPStatus.OK:
            message = (
                _get_value(response, "message")
                or _get_value(response, "code")
                or "DashScope Embedding 调用失败"
            )
            raise RuntimeError(str(message))

        output = _get_value(response, "output")
        embeddings = _get_value(output, "embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError("DashScope Embedding 响应缺少 embeddings 字段")

        vectors_by_index: dict[int, list[float]] = {}
        vectors: list[list[float]] = []
        for index, item in enumerate(embeddings):
            if isinstance(item, dict):
                embedding = item.get("embedding")
                text_index = item.get("text_index", index)
            else:
                embedding = item
                text_index = index
            if not isinstance(embedding, list):
                raise RuntimeError("DashScope Embedding 响应格式错误")
            vectors_by_index[int(text_index)] = [float(value) for value in embedding]

        for index in range(len(texts)):
            if index not in vectors_by_index:
                raise RuntimeError("DashScope Embedding 响应数量与请求文本不一致")
            vectors.append(vectors_by_index[index])
        logger.info(
            "embedding request done provider=dashscope model=%s text_count=%s vector_count=%s",
            self.model,
            len(texts),
            len(vectors),
        )
        return vectors


def _get_value(data, key: str):
    if data is None:
        return None
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)
