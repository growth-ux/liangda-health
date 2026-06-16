from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.agent import AgentMessage, AgentSession


class SqlAlchemyAgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, session_id: str, title: str) -> AgentSession:
        now = utc_now()
        session = AgentSession(
            session_id=session_id,
            title=title,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self) -> list[AgentSession]:
        return self.db.query(AgentSession).order_by(AgentSession.updated_at.desc()).all()

    def get_session(self, session_id: str) -> AgentSession | None:
        return self.db.query(AgentSession).filter(AgentSession.session_id == session_id).one_or_none()

    def list_messages(self, session_id: str) -> list[AgentMessage]:
        return (
            self.db.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.asc(), AgentMessage.id.asc())
            .all()
        )

    def list_recent_messages(self, session_id: str, limit: int = 8) -> list[AgentMessage]:
        messages = (
            self.db.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(messages))

    def get_latest_message(self, session_id: str) -> AgentMessage | None:
        return (
            self.db.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .first()
        )

    def save_message(
        self,
        message_id: str,
        session_id: str,
        role: str,
        content: str,
        status: str = "done",
        product_recommendations: str | None = None,
        token_prompt: int | None = None,
        token_completion: int | None = None,
        model_name: str | None = None,
    ) -> AgentMessage:
        message = AgentMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            status=status,
            product_recommendations=product_recommendations,
            token_prompt=token_prompt,
            token_completion=token_completion,
            model_name=model_name,
            created_at=utc_now(),
        )
        self.db.add(message)
        session = self.get_session(session_id)
        if session is not None:
            session.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(message)
        return message

    def update_session_title(self, session_id: str, title: str) -> None:
        session = self.get_session(session_id)
        if session is None:
            return
        session.title = title
        session.updated_at = utc_now()
        self.db.commit()

    def delete_session(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        self.db.query(AgentMessage).filter(AgentMessage.session_id == session_id).delete()
        self.db.delete(session)
        self.db.commit()
        return True
