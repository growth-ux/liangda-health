from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.kb import get_embedding_service, get_vector_store
from app.db.session import get_db
from app.repositories.agent_repository import SqlAlchemyAgentRepository
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.schemas.agent import (
    AgentMessageSendRequest,
    AgentMessagesResponse,
    AgentSendResponse,
    AgentSessionCreate,
    AgentSessionCreateResponse,
    AgentSessionListItem,
    QuickActionItem,
)
from app.services.agent_service import AgentService
from app.services.agent_tools import KbSearchTool
from app.services.langchain_agent import LangChainAgentRunner

router = APIRouter(prefix="/api/agent", tags=["agent"])


def get_agent_runner(
    db: Session = Depends(get_db),
    embedding_service=Depends(get_embedding_service),
    vector_store=Depends(get_vector_store),
):
    return LangChainAgentRunner(
        kb_tool=KbSearchTool(
            repository=SqlAlchemyKbRepository(db),
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
    )


def get_agent_service(
    db: Session = Depends(get_db),
    runner=Depends(get_agent_runner),
) -> AgentService:
    return AgentService(repository=SqlAlchemyAgentRepository(db), runner=runner)


@router.get("/sessions", response_model=list[AgentSessionListItem])
def list_sessions(service: AgentService = Depends(get_agent_service)):
    return service.list_sessions()


@router.post("/sessions", response_model=AgentSessionCreateResponse)
def create_session(request: AgentSessionCreate, service: AgentService = Depends(get_agent_service)):
    return service.create_session(title=request.title)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, service: AgentService = Depends(get_agent_service)):
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "ok"}


@router.get("/sessions/{session_id}/messages", response_model=AgentMessagesResponse)
def list_messages(session_id: str, service: AgentService = Depends(get_agent_service)):
    return AgentMessagesResponse(items=service.list_messages(session_id))


@router.post("/sessions/{session_id}/messages:send", response_model=AgentSendResponse)
def send_message(
    session_id: str,
    request: AgentMessageSendRequest,
    service: AgentService = Depends(get_agent_service),
):
    content = _message_content(request)
    user_message, assistant_message = service.send_message(session_id=session_id, content=content)
    return AgentSendResponse(user_message=user_message, assistant_message=assistant_message)


@router.post("/sessions/{session_id}/messages:stream")
def stream_message(
    session_id: str,
    request: AgentMessageSendRequest,
    service: AgentService = Depends(get_agent_service),
):
    return StreamingResponse(
        service.stream_message(session_id=session_id, content=_message_content(request)),
        media_type="text/event-stream",
    )


@router.get("/quick-actions", response_model=list[QuickActionItem])
def list_quick_actions():
    return []


def _message_content(request: AgentMessageSendRequest) -> str:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    return content
