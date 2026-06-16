from dataclasses import dataclass
import logging
from pathlib import Path
from uuid import uuid4

from app.services.chunker import TextChunk, chunk_page_text
from app.services.embedding import DashScopeEmbeddingService
from app.services.metadata import BasicMetadata, extract_basic_metadata
from app.services.vector_store import VectorRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentCreate:
    document_id: str
    file_name: str
    file_path: str
    file_size: int
    status: str
    member_id: str | None = None


@dataclass(frozen=True)
class PageCreate:
    document_id: str
    page_no: int
    text_content: str


@dataclass(frozen=True)
class UploadResult:
    document_id: str
    status: str
    page_count: int
    chunk_count: int
    fact_extract_status: str = "pending"
    error_message: str | None = None


class KbService:
    def __init__(
        self,
        repository,
        pdf_extractor,
        ocr_client,
        embedding_service: DashScopeEmbeddingService,
        vector_store,
        upload_dir: Path,
    ):
        self.repository = repository
        self.pdf_extractor = pdf_extractor
        self.ocr_client = ocr_client
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.upload_dir = upload_dir

    def upload_pdf(self, file_name: str, content: bytes, member_id: str | None = None) -> UploadResult:
        if not file_name.lower().endswith(".pdf"):
            raise ValueError("只支持 PDF 文件")

        document_id = f"doc_{uuid4().hex}"
        target_dir = self.upload_dir / document_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file_name
        target_path.write_bytes(content)

        self.repository.create_document(
            DocumentCreate(
                document_id=document_id,
                file_name=file_name,
                file_path=str(target_path),
                file_size=len(content),
                member_id=member_id,
                status="processing",
            )
        )

        try:
            thumbnail_path = target_dir / "thumbnail.png"
            if hasattr(self.pdf_extractor, "render_first_page_thumbnail"):
                self.pdf_extractor.render_first_page_thumbnail(target_path, thumbnail_path)

            pages_text = self.pdf_extractor.extract_pages(target_path)
            if len("".join(pages_text).strip()) < 100:
                pages_text = self.ocr_client.extract_pages(target_path)
            pages = [
                PageCreate(document_id=document_id, page_no=index + 1, text_content=text)
                for index, text in enumerate(pages_text)
            ]
            self.repository.save_pages(pages)

            all_text = "\n".join(pages_text)
            metadata = extract_basic_metadata(all_text)

            chunks: list[TextChunk] = []
            for page in pages:
                chunks.extend(
                    chunk_page_text(
                        document_id=document_id,
                        member_id=member_id or "",
                        page_no=page.page_no,
                        text=page.text_content,
                    )
                )
            self.repository.save_chunks(chunks)

            logger.info(
                "kb_upload embedding start document_id=%s member_id=%s chunk_count=%s",
                document_id,
                member_id,
                len(chunks),
            )
            embeddings = self.embedding_service.embed_many([chunk.content for chunk in chunks])
            logger.info(
                "kb_upload embedding done document_id=%s member_id=%s vector_count=%s",
                document_id,
                member_id,
                len(embeddings),
            )
            self.vector_store.upsert(
                [
                    VectorRecord(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        member_id=chunk.member_id,
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ]
            )
            self.repository.mark_ready(document_id, len(pages), metadata)

            return UploadResult(
                document_id=document_id,
                status="ready",
                page_count=len(pages),
                chunk_count=len(chunks),
                fact_extract_status="pending",
            )
        except Exception as exc:
            error_message = str(exc)
            self.repository.mark_failed(document_id, error_message)
            return UploadResult(
                document_id=document_id,
                status="failed",
                page_count=0,
                chunk_count=0,
                fact_extract_status="pending",
                error_message=error_message,
            )
