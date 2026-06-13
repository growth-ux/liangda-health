from sqlalchemy.orm import Session

from app.models.kb import KbChunk, KbDocument, KbPage
from app.services.kb_service import DocumentCreate, PageCreate
from app.services.metadata import BasicMetadata


class SqlAlchemyKbRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, document: DocumentCreate) -> None:
        self.db.add(
            KbDocument(
                document_id=document.document_id,
                file_name=document.file_name,
                file_path=document.file_path,
                file_size=document.file_size,
                status=document.status,
            )
        )
        self.db.commit()

    def save_pages(self, pages: list[PageCreate]) -> None:
        self.db.add_all(
            [
                KbPage(
                    document_id=page.document_id,
                    page_no=page.page_no,
                    text_content=page.text_content,
                )
                for page in pages
            ]
        )
        self.db.commit()

    def save_chunks(self, chunks) -> None:
        self.db.add_all(
            [
                KbChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    page_no=chunk.page_no,
                    content=chunk.content,
                )
                for chunk in chunks
            ]
        )
        self.db.commit()

    def mark_ready(self, document_id: str, page_count: int, metadata: BasicMetadata) -> None:
        document = self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one()
        document.status = "ready"
        document.page_count = page_count
        document.title = metadata.title
        document.patient_name = metadata.patient_name
        document.exam_date = metadata.exam_date
        document.institution = metadata.institution
        self.db.commit()

    def mark_failed(self, document_id: str, error_message: str) -> None:
        document = self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one_or_none()
        if document is None:
            return
        document.status = "failed"
        document.error_message = error_message
        self.db.commit()

    def list_documents(self) -> list[KbDocument]:
        return self.db.query(KbDocument).order_by(KbDocument.created_at.desc()).all()

    def get_document(self, document_id: str) -> KbDocument | None:
        return self.db.query(KbDocument).filter(KbDocument.document_id == document_id).one_or_none()

    def delete_document(self, document_id: str) -> KbDocument | None:
        document = self.get_document(document_id)
        if document is None:
            return None

        for chunk in self.db.query(KbChunk).filter(KbChunk.document_id == document_id).all():
            self.db.delete(chunk)
        for page in self.db.query(KbPage).filter(KbPage.document_id == document_id).all():
            self.db.delete(page)
        self.db.delete(document)
        self.db.commit()
        return document

    def list_chunks_by_document(self, document_id: str) -> list[KbChunk]:
        return (
            self.db.query(KbChunk)
            .filter(KbChunk.document_id == document_id)
            .order_by(KbChunk.page_no.asc(), KbChunk.id.asc())
            .all()
        )

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[KbChunk]:
        if not chunk_ids:
            return []
        chunks = self.db.query(KbChunk).filter(KbChunk.chunk_id.in_(chunk_ids)).all()
        order = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
        return sorted(chunks, key=lambda chunk: order.get(chunk.chunk_id, len(order)))
