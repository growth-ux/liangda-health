from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.notice import Notice


class SqlAlchemyNoticeRepository:
    def __init__(self, db: Session):
        self.db = db

    def exists_dedupe_key(self, dedupe_key: str) -> bool:
        return self.db.query(Notice.id).filter(Notice.dedupe_key == dedupe_key).first() is not None

    def has_any_notice(self) -> bool:
        return self.db.query(Notice.id).first() is not None

    def create_notice(
        self,
        *,
        category: str,
        level: str,
        title: str,
        description: str,
        source: str,
        dedupe_key: str,
        member_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        action_text: str | None = None,
        secondary_action: str | None = None,
        created_at: datetime | None = None,
    ) -> Notice:
        notice = Notice(
            notice_id=f"not_{uuid4().hex}",
            category=category,
            level=level,
            title=title,
            description=description,
            source=source,
            member_id=member_id,
            target_type=target_type,
            target_id=target_id,
            action_text=action_text,
            secondary_action=secondary_action,
            status="unread",
            dedupe_key=dedupe_key,
            created_at=created_at or datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(notice)
        return notice

    def list_notices(self, category: str | None = None) -> list[Notice]:
        query = self.db.query(Notice)
        if category:
            query = query.filter(Notice.category == category)
        return query.order_by(Notice.created_at.desc(), Notice.id.desc()).all()

    def get_notice(self, notice_id: str) -> Notice | None:
        return self.db.query(Notice).filter(Notice.notice_id == notice_id).one_or_none()

    def count_by_category(self, category: str | None = None) -> int:
        query = self.db.query(Notice)
        if category:
            query = query.filter(Notice.category == category)
        return query.count()

    def unread_count(self) -> int:
        return self.db.query(Notice).filter(Notice.status == "unread").count()

    def update_status(self, notice_id: str, status: str) -> Notice | None:
        notice = self.get_notice(notice_id)
        if notice is None:
            return None
        notice.status = status
        notice.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def mark_all_read(self) -> int:
        notices = self.db.query(Notice).filter(Notice.status == "unread").all()
        now = datetime.utcnow()
        for notice in notices:
            notice.status = "read"
            notice.updated_at = now
        self.db.commit()
        return len(notices)
