import json
from collections import defaultdict
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.kb import KbDocument
from app.models.member import Member
from app.schemas.member import (
    MemberCreateRequest,
    MemberDetail,
    MemberDocumentItem,
    MemberListItem,
    MemberUpdateRequest,
)


class SqlAlchemyMemberRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_member(self, request: MemberCreateRequest) -> MemberDetail:
        now = utc_now()
        member = Member(
            member_id=f"mem_{uuid4().hex}",
            name=request.name,
            relation=request.relation,
            gender=request.gender,
            birth_year=request.birth_year,
            phone=request.phone,
            height_cm=request.height_cm,
            weight_kg=request.weight_kg,
            health_tags=json.dumps(request.health_tags, ensure_ascii=False),
            allergies=request.allergies,
            taste_preferences=request.taste_preferences,
            created_at=now,
            updated_at=now,
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return self._to_detail(member)

    def list_members(self) -> list[MemberListItem]:
        members = self.db.query(Member).order_by(Member.created_at.desc()).all()
        member_ids = [member.member_id for member in members]
        documents_by_member = self._documents_by_member(member_ids)

        items: list[MemberListItem] = []
        for member in members:
            documents = documents_by_member.get(member.member_id, [])
            recent_documents = [
                MemberDocumentItem(
                    document_id=document.document_id,
                    file_name=document.file_name,
                    exam_date=self._to_datetime(document.exam_date),
                    status=document.status,
                )
                for document in documents[:3]
            ]
            items.append(
                MemberListItem(
                    member_id=member.member_id,
                    name=member.name,
                    relation=member.relation,
                    gender=member.gender,
                    birth_year=member.birth_year,
                    phone=member.phone,
                    height_cm=member.height_cm,
                    weight_kg=member.weight_kg,
                    allergies=member.allergies,
                    taste_preferences=member.taste_preferences,
                    created_at=member.created_at,
                    updated_at=member.updated_at,
                    report_count=len(documents),
                    recent_documents=recent_documents,
                    health_tags_raw=member.health_tags,
                )
            )
        return items

    def get_member(self, member_id: str) -> Member | None:
        return self.db.query(Member).filter(Member.member_id == member_id).one_or_none()

    def get_member_detail(self, member_id: str) -> MemberDetail | None:
        member = self.get_member(member_id)
        if member is None:
            return None
        return self._to_detail(member)

    def update_member(self, member_id: str, request: MemberUpdateRequest) -> MemberDetail | None:
        member = self.get_member(member_id)
        if member is None:
            return None

        member.name = request.name
        member.relation = request.relation
        member.gender = request.gender
        member.birth_year = request.birth_year
        member.phone = request.phone
        member.height_cm = request.height_cm
        member.weight_kg = request.weight_kg
        member.health_tags = json.dumps(request.health_tags, ensure_ascii=False)
        member.allergies = request.allergies
        member.taste_preferences = request.taste_preferences
        member.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(member)
        return self._to_detail(member)

    def delete_member(self, member_id: str) -> Member | None:
        member = self.get_member(member_id)
        if member is None:
            return None
        referenced = (
            self.db.query(KbDocument)
            .filter(KbDocument.member_id == member_id)
            .first()
        )
        if referenced is not None:
            return None  # 拒绝删除
        self.db.delete(member)
        self.db.commit()
        return member

    def list_documents(self, member_id: str) -> list[KbDocument]:
        return (
            self.db.query(KbDocument)
            .filter(KbDocument.member_id == member_id)
            .order_by(KbDocument.created_at.desc())
            .all()
        )

    def count_documents(self, member_id: str) -> int:
        return len(self.list_documents(member_id))

    def exists_by_member_id(self, member_id: str) -> bool:
        return self.get_member(member_id) is not None

    def _documents_by_member(self, member_ids: list[str]) -> dict[str, list[KbDocument]]:
        if not member_ids:
            return {}
        documents = (
            self.db.query(KbDocument)
            .filter(KbDocument.member_id.in_(member_ids))
            .order_by(KbDocument.created_at.desc())
            .all()
        )
        grouped: dict[str, list[KbDocument]] = defaultdict(list)
        for document in documents:
            if document.member_id:
                grouped[document.member_id].append(document)
        return grouped

    def _to_detail(self, member: Member) -> MemberDetail:
        return MemberDetail(
            member_id=member.member_id,
            name=member.name,
            relation=member.relation,
            gender=member.gender,
            birth_year=member.birth_year,
            phone=member.phone,
            height_cm=member.height_cm,
            weight_kg=member.weight_kg,
            allergies=member.allergies,
            taste_preferences=member.taste_preferences,
            created_at=member.created_at,
            updated_at=member.updated_at,
            health_tags_raw=member.health_tags,
        )

    @staticmethod
    def _to_datetime(value: date | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(value, datetime.min.time())
