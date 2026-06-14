from collections.abc import Iterable

from app.core.config import settings


SYSTEM_PROMPT_TEMPLATE = """你是粮达健康的家庭健康 Agent 管家。
你可以基于用户上传的健康报告和用户当前问题提供健康建议。

要求：
1. 用简体中文回答。
2. 不做诊断，不替代医生。
3. 对异常指标给出就医提醒。
4. 如果引用报告内容，说明来自哪份报告或页码。
5. 回答要像管家，简洁、具体、可执行。
6. 当信息不足时，直接说明还缺什么信息。
7. 检索用户报告时必须调用 kb_search 工具，并显式传入 member_id。
   不要在不知道是哪位家人的情况下盲猜。
{members_block}
9. 跨家人对比问题（"全家血脂怎么样"）需要分别对每位家人调用 kb_search，然后合成答案。
"""


def _build_members_block(members: list) -> str:
    if not members:
        return "8. 当前没有可用家人，无法检索报告。\n"
    lines = ["8. 当前可用家人列表："]
    for index, member in enumerate(members, start=1):
        member_id = member.member_id if hasattr(member, "member_id") else member["member_id"]
        name = member.name if hasattr(member, "name") else member["name"]
        relation = member.relation if hasattr(member, "relation") else member.get("relation", "")
        lines.append(f"   {index}. {name}（member_id={member_id}，{relation}）")
    lines.append('   如果用户问"爸爸"对应到相应的家人，以此类推。')
    lines.append('   如果指代不明（如"他/她"无上下文），必须先反问"您说的\'他/她\'是指哪位家人？"，不要主动猜测。')
    return "\n".join(lines) + "\n"


class LlmConfigError(Exception):
    pass


class LangChainAgentRunner:
    def __init__(self, kb_tool=None, member_provider=None):
        self.kb_tool = kb_tool
        self.member_provider = member_provider or (lambda: [])

    def _system_prompt(self) -> str:
        members = self.member_provider()
        return SYSTEM_PROMPT_TEMPLATE.format(members_block=_build_members_block(members))

    def _ensure_api_key(self) -> None:
        if not settings.llm_api_key:
            raise LlmConfigError("未配置模型 API Key")

    def _append_kb_context(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        # LLM now drives KB search via the kb_search tool (with explicit member_id).
        # This auto-injection path is retained as a no-op for backward compatibility.
        return messages

    def run(self, messages: list[dict[str, str]]) -> dict[str, object]:
        self._ensure_api_key()
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        response = agent.invoke({"messages": self._to_langchain_messages(prepared_messages)})
        response_message = response["messages"][-1]
        token_usage = (
            response_message.response_metadata.get("token_usage", {})
            if response_message.response_metadata
            else {}
        )
        return {
            "content": _content_to_text(response_message.content),
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
        }

    def stream(self, messages: list[dict[str, str]]) -> Iterable[str]:
        self._ensure_api_key()
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(prepared_messages)},
            stream_mode="messages",
        ):
            content = getattr(chunk, "content", "")
            text = _content_to_text(content)
            if text:
                yield text

    def _agent(self):
        from langchain.agents import create_agent

        return create_agent(
            model=self._model(),
            tools=self._tools(),
            system_prompt=self._system_prompt(),
        )

    def _tools(self):
        if self.kb_tool is None:
            return []

        def kb_search(query: str, member_id: str, top_k: int = 5) -> str:
            """检索指定家人的健康报告片段。"""
            return self.kb_tool.search(query=query, member_id=member_id, top_k=top_k)

        return [kb_search]

    def _model(self):
        from langchain.chat_models import init_chat_model

        return init_chat_model(
            model=settings.llm_model,
            model_provider="openai",
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )

    def _to_langchain_messages(self, messages: list[dict[str, str]]):
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        result = []
        for message in messages:
            if message["role"] == "assistant":
                result.append(AIMessage(content=message["content"]))
            elif message["role"] == "system":
                result.append(SystemMessage(content=message["content"]))
            else:
                result.append(HumanMessage(content=message["content"]))
        return result


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content) if content is not None else ""
