from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.kb import get_embedding_service, get_vector_store
from app.db.session import get_db
from app.repositories.agent_repository import SqlAlchemyAgentRepository
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
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
from app.services.agent_tools import KbSearchTool, MealPlanTool, MemorySearchTool
from app.services.langchain_agent import LangChainAgentRunner
from app.services.meal_plan_service import MealPlanService
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/api/agent", tags=["agent"])


def get_memory_service(db: Session = Depends(get_db)):
    member_repository = SqlAlchemyMemberRepository(db)
    return MemoryService(member_provider=member_repository.list_members)


def get_agent_runner(
    db: Session = Depends(get_db),
    memory_service: MemoryService = Depends(get_memory_service),
):
    member_repository = SqlAlchemyMemberRepository(db)

    def member_provider():
        members = member_repository.list_members()
        return [
            type("M", (), {
                "member_id": m.member_id,
                "name": m.name,
                "relation": m.relation,
            })()
            for m in members
        ]

    return LangChainAgentRunner(
        kb_tool=KbSearchTool(
            repository=SqlAlchemyKbRepository(db),
            allowed_member_ids=[m.member_id for m in member_provider()],
            embedding_service_factory=get_embedding_service,
            vector_store_factory=get_vector_store,
        ),
        meal_plan_tool=MealPlanTool(
            service=MealPlanService(db, memory_service=memory_service),
            allowed_member_ids=[m.member_id for m in member_provider()],
        ),
        memory_tool=MemorySearchTool(memory_service),
        member_provider=member_provider,
    )


def get_agent_service(
    db: Session = Depends(get_db),
    runner=Depends(get_agent_runner),
    memory_service: MemoryService = Depends(get_memory_service),
) -> AgentService:
    return AgentService(
        repository=SqlAlchemyAgentRepository(db),
        runner=runner,
        memory_service=memory_service,
    )


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
    return [
        QuickActionItem(label="给全家安排今天一日三餐", action="meal_plan_family_day"),
        QuickActionItem(label="给爸爸出点生活习惯建议", action="father_lifestyle_advice"),
        QuickActionItem(label="推荐一款适合全家人的油", action="family_oil_recommendation"),
        QuickActionItem(label="今晚做什么适合全家", action="meal_plan_family_dinner"),
    ]


def _message_content(request: AgentMessageSendRequest) -> str:
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    return content
