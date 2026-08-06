"""集团运营 Agent API 路由：/api/ops-agent/。"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.agent_repository import SqlAlchemyAgentRepository
from app.services.langchain_agent import LlmConfigError
from app.services.ops_agent import OpsAgentRunner
from app.services.ops_agent_tools import OpsAgentTools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ops-agent", tags=["ops-agent"])

SESSION_PREFIX = "ops_sess_"


class OpsMessageRequest(BaseModel):
    content: str


class OpsSessionCreate(BaseModel):
    title: str = "运营分析"


class OpsSessionItem(BaseModel):
    session_id: str
    title: str
    preview: str
    updated_at: str


class OpsMessageItem(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str


def _get_runner() -> OpsAgentRunner:
    return OpsAgentRunner(ops_tools=OpsAgentTools())


def _get_repo(db: Session = Depends(get_db)) -> SqlAlchemyAgentRepository:
    return SqlAlchemyAgentRepository(db)


@router.post("/sessions")
def create_session(request: OpsSessionCreate, repo: SqlAlchemyAgentRepository = Depends(_get_repo)):
    session_id = f"{SESSION_PREFIX}{uuid.uuid4().hex[:16]}"
    session = repo.create_session(session_id=session_id, title=request.title)
    return {"session_id": session.session_id, "title": session.title, "created_at": str(session.created_at)}


@router.get("/sessions")
def list_sessions(repo: SqlAlchemyAgentRepository = Depends(_get_repo)):
    all_sessions = repo.list_sessions()
    ops_sessions = [s for s in all_sessions if s.session_id.startswith(SESSION_PREFIX)]
    return [
        {
            "session_id": s.session_id,
            "title": s.title,
            "preview": (repo.get_latest_message(s.session_id).content[:80] if repo.get_latest_message(s.session_id) else ""),
            "updated_at": str(s.updated_at),
        }
        for s in ops_sessions
    ]


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: str, repo: SqlAlchemyAgentRepository = Depends(_get_repo)):
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = repo.list_messages(session_id)
    return {
        "items": [
            {
                "message_id": m.message_id,
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "created_at": str(m.created_at),
            }
            for m in messages
        ]
    }


@router.post("/sessions/{session_id}/messages:stream")
def stream_message(
    session_id: str,
    request: OpsMessageRequest,
    runner: OpsAgentRunner = Depends(_get_runner),
    repo: SqlAlchemyAgentRepository = Depends(_get_repo),
):
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # 保存用户消息
    user_msg = repo.save_message(
        message_id=f"ops_msg_{uuid.uuid4().hex[:16]}",
        session_id=session_id,
        role="user",
        content=content,
    )

    # 构建历史
    history = [
        {"role": m.role, "content": m.content}
        for m in repo.list_recent_messages(session_id, limit=10)
    ]

    # 刷新标题
    if session.title == "运营分析":
        repo.update_session_title(session_id, content[:24].replace("\n", " "))

    def _event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        yield _event("user_message", {
            "message_id": user_msg.message_id,
            "session_id": user_msg.session_id,
            "role": "user",
            "content": user_msg.content,
        })
        assistant_id = f"ops_msg_{uuid.uuid4().hex[:16]}"
        yield _event("assistant_start", {"message_id": assistant_id, "role": "assistant"})

        delta_chunks: list[str] = []
        try:
            for event_type, payload in runner.stream(history):
                if event_type == "delta":
                    text = str(payload) if payload is not None else ""
                    if text:
                        delta_chunks.append(text)
                        yield _event("delta", {"content": text})
        except LlmConfigError as exc:
            logger.warning("ops_agent stream llm config error: %s", exc)
            yield _event("error", {"message": str(exc)})
            return
        except Exception:
            logger.exception("ops_agent stream failed for session=%s", session_id)
            yield _event("error", {"message": "模型调用失败"})
            return

        content_done = "".join(delta_chunks)
        assistant_msg = repo.save_message(
            message_id=assistant_id,
            session_id=session_id,
            role="assistant",
            content=content_done,
        )
        yield _event("assistant_done", {
            "message_id": assistant_msg.message_id,
            "session_id": assistant_msg.session_id,
            "role": "assistant",
            "content": assistant_msg.content,
        })
        yield _event("done", {})

    return StreamingResponse(generate(), media_type="text/event-stream")
