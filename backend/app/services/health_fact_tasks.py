from app.db.session import SessionLocal
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.services.health_fact_extractor import HealthFactExtractor


def extract_health_facts_for_document(document_id: str) -> None:
    db = SessionLocal()
    try:
        repository = SqlAlchemyKbRepository(db)
        document = repository.get_document(document_id)
        if document is None:
            return

        repository.mark_fact_extract_processing(document_id)
        try:
            pages = repository.list_pages(document_id)
            chunks = repository.list_chunks(document_id)
            facts = HealthFactExtractor().extract(
                document_id=document_id,
                member_id=document.member_id or "",
                pages=pages,
                chunks=chunks,
            )
            repository.delete_facts_by_document(document_id)
            repository.save_facts(facts)
            repository.mark_fact_extract_ready(document_id)
        except Exception as exc:
            repository.mark_fact_extract_failed(document_id, str(exc))
    finally:
        db.close()
