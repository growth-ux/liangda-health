"""Context Summarization：把多轮对话中的旧消息压缩为会话级摘要。

当消息数超过阈值时，把较早的消息用 LLM 生成一段简短摘要，
替换原始消息列表，减少传入 Agent 的 token 消耗。
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "请用2-3句话总结以下对话的关键信息：用户问了什么、讨论了什么主题、"
    "有什么重要约束或结论。只输出摘要，不要输出其他内容。限100字以内。"
)

MAX_SUMMARY_CHARS = 200


class SessionSummarizer:
    """会话摘要器：超过 recent_keep 条的消息会被压缩为一条 system 摘要。"""

    def __init__(self, recent_keep: int = 4, client=None):
        self.recent_keep = recent_keep
        self._client = client

    def summarize(self, messages: list[dict[str, str]]) -> str:
        """把一组消息压缩成一段摘要文本。"""
        if not messages:
            return ""

        client = self._get_client()
        if client is not None:
            try:
                return self._llm_summarize(client, messages)
            except Exception:
                logger.exception("session_summarizer llm_summarize failed")

        return self._fallback_summarize(messages)

    def _llm_summarize(self, client, messages: list[dict[str, str]]) -> str:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": self._format_messages(messages)},
            ],
            temperature=0.3,
            max_tokens=200,
            timeout=15,
        )
        summary = response.choices[0].message.content or ""
        summary = summary.strip()
        logger.info(
            "session_summarizer llm_summarize done msg_count=%s summary_chars=%s",
            len(messages),
            len(summary),
        )
        return summary[:MAX_SUMMARY_CHARS]

    def _fallback_summarize(self, messages: list[dict[str, str]]) -> str:
        """LLM 不可用时的规则化降级：取每条消息前 N 个字拼接。"""
        parts = []
        for msg in messages:
            role_label = "用户" if msg["role"] == "user" else "助手"
            preview = msg["content"][:50].replace("\n", " ")
            parts.append(f"{role_label}：{preview}")
        summary = "；".join(parts)
        logger.info(
            "session_summarizer fallback_summarize done msg_count=%s summary_chars=%s",
            len(messages),
            len(summary),
        )
        return summary[:MAX_SUMMARY_CHARS]

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not settings.llm_api_key:
            return None
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
            return self._client
        except Exception:
            logger.exception("session_summarizer failed to create OpenAI client")
            return None

    @staticmethod
    def _format_messages(messages: list[dict[str, str]]) -> str:
        lines = []
        for msg in messages:
            role_label = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role_label}：{msg['content']}")
        return "\n".join(lines)
