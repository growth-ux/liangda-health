import json
import uuid
from collections.abc import Iterable

from fastapi import HTTPException

from app.repositories.agent_repository import SqlAlchemyAgentRepository
from app.services.langchain_agent import LlmConfigError


class AgentService:
    def __init__(self, repository: SqlAlchemyAgentRepository, runner):
        self.repository = repository
        self.runner = runner

    def create_session(self, title: str):
        return self.repository.create_session(session_id=f"sess_{uuid.uuid4().hex[:16]}", title=title)

    def list_sessions(self):
        items = []
        for session in self.repository.list_sessions():
            latest = self.repository.get_latest_message(session.session_id)
            items.append(
                {
                    "session_id": session.session_id,
                    "title": session.title,
                    "preview": latest.content[:80] if latest is not None else "",
                    "updated_at": session.updated_at,
                }
            )
        return items

    def list_messages(self, session_id: str):
        self._require_session(session_id)
        return self.repository.list_messages(session_id)

    def send_message(self, session_id: str, content: str):
        session = self._require_session(session_id)
        user_message = self._save_user_message(session_id, content)
        try:
            result = self.runner.run(self._history(session_id))
        except LlmConfigError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="模型调用失败") from exc

        assistant_message = self.repository.save_message(
            message_id=f"msg_{uuid.uuid4().hex[:16]}",
            session_id=session_id,
            role="assistant",
            content=str(result["content"]),
            token_prompt=result.get("token_prompt"),
            token_completion=result.get("token_completion"),
            model_name=result.get("model_name"),
        )
        self._refresh_title(session.session_id, session.title, content)
        return user_message, assistant_message

    def stream_message(self, session_id: str, content: str) -> Iterable[str]:
        session = self._require_session(session_id)
        user_message = self._save_user_message(session_id, content)
        assistant_id = f"msg_{uuid.uuid4().hex[:16]}"
        yield self._event(
            "user_message",
            {
                "message_id": user_message.message_id,
                "session_id": user_message.session_id,
                "role": user_message.role,
                "content": user_message.content,
            },
        )
        yield self._event("assistant_start", {"message_id": assistant_id, "role": "assistant"})

        chunks = []
        try:
            for delta in self.runner.stream(self._history(session_id)):
                chunks.append(delta)
                yield self._event("delta", {"content": delta})
        except LlmConfigError as exc:
            yield self._event("error", {"message": str(exc)})
            return
        except Exception:
            yield self._event("error", {"message": "模型调用失败"})
            return

        content_done = "".join(chunks)
        assistant_message = self.repository.save_message(
            message_id=assistant_id,
            session_id=session_id,
            role="assistant",
            content=content_done,
        )
        self._refresh_title(session.session_id, session.title, content)
        yield self._event(
            "assistant_done",
            {
                "message_id": assistant_message.message_id,
                "session_id": assistant_message.session_id,
                "role": assistant_message.role,
                "content": assistant_message.content,
            },
        )
        yield self._event("done", {})

    def _require_session(self, session_id: str):
        session = self.repository.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session

    def _save_user_message(self, session_id: str, content: str):
        return self.repository.save_message(
            message_id=f"msg_{uuid.uuid4().hex[:16]}",
            session_id=session_id,
            role="user",
            content=content,
        )

    def _history(self, session_id: str):
        return [
            {"role": message.role, "content": message.content}
            for message in self.repository.list_recent_messages(session_id, limit=8)
        ]

    def _event(self, event: str, data: dict[str, object]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _refresh_title(self, session_id: str, current_title: str, content: str) -> None:
        if current_title != "新对话":
            return
        title = content.strip().replace("\n", " ")[:24] or "新对话"
        self.repository.update_session_title(session_id, title)
