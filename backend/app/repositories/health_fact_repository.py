from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.health_fact import HealthFact


@dataclass(frozen=True)
class HealthFactCreate:
    fact_id: str
    member_id: str
    fact_type: str
    name: str
    value: str | None
    unit: str | None
    reference_range: str | None
    status: str
    source_document_id: str
    source_page_no: int
    source_chunk_id: str | None
    evidence_text: str


class SqlAlchemyHealthFactRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_facts(self, facts: list[HealthFactCreate]) -> None:
        if not facts:
            return
        self.db.add_all(
            [
                HealthFact(
                    fact_id=fact.fact_id,
                    member_id=fact.member_id,
                    fact_type=fact.fact_type,
                    name=fact.name,
                    value=fact.value,
                    unit=fact.unit,
                    reference_range=fact.reference_range,
                    status=fact.status,
                    source_document_id=fact.source_document_id,
                    source_page_no=fact.source_page_no,
                    source_chunk_id=fact.source_chunk_id,
                    evidence_text=fact.evidence_text,
                )
                for fact in facts
            ]
        )
        self.db.commit()

    def list_by_document(self, document_id: str) -> list[HealthFact]:
        return (
            self.db.query(HealthFact)
            .filter(HealthFact.source_document_id == document_id)
            .order_by(HealthFact.source_page_no.asc(), HealthFact.id.asc())
            .all()
        )

    def list_by_member(self, member_id: str) -> list[HealthFact]:
        return (
            self.db.query(HealthFact)
            .filter(HealthFact.member_id == member_id)
            .order_by(HealthFact.created_at.desc(), HealthFact.id.desc())
            .all()
        )

    def delete_by_document(self, document_id: str) -> None:
        for fact in self.db.query(HealthFact).filter(HealthFact.source_document_id == document_id).all():
            self.db.delete(fact)
        self.db.commit()
