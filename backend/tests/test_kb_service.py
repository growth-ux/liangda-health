from pathlib import Path

from app.services.kb_service import KbService


class FakeVectorStore:
    def __init__(self):
        self.records = []

    def upsert(self, records):
        self.records.extend(records)


class FakeRepository:
    def __init__(self):
        self.documents = []
        self.pages = []
        self.chunks = []
        self.updated = []
        self.failed = []

    def create_document(self, document):
        self.documents.append(document)

    def save_pages(self, pages):
        self.pages.extend(pages)

    def save_chunks(self, chunks):
        self.chunks.extend(chunks)

    def mark_ready(self, document_id, page_count, metadata):
        self.updated.append((document_id, page_count, metadata))

    def mark_failed(self, document_id, error_message):
        self.failed.append((document_id, error_message))


class FakePdfExtractor:
    def extract_pages(self, path: Path):
        return [
            "市立医院体检报告\n姓名：王秀英\n检查日期：2026-05-12\n检查机构：市立医院\n骨密度 T 值 -2.1\n"
            + "报告正文" * 20
        ]

    def render_first_page_thumbnail(self, path: Path, output_path: Path):
        output_path.write_bytes(b"fake png")


class FakeOcrClient:
    def extract_pages(self, path: Path):
        return ["OCR 文本"]


class FakeEmbeddingService:
    def embed_many(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_upload_pdf_builds_pages_chunks_and_vectors(tmp_path):
    repository = FakeRepository()
    vector_store = FakeVectorStore()
    service = KbService(
        repository=repository,
        pdf_extractor=FakePdfExtractor(),
        ocr_client=FakeOcrClient(),
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        upload_dir=tmp_path,
    )

    result = service.upload_pdf(
        file_name="report.pdf",
        content=b"%PDF-1.4 fake",
        member_id="mem_1",
    )

    assert result.status == "ready"
    assert result.page_count == 1
    assert result.chunk_count == 1
    assert repository.documents[0].file_name == "report.pdf"
    assert (tmp_path / result.document_id / "thumbnail.png").read_bytes() == b"fake png"
    assert repository.pages[0].page_no == 1
    assert "骨密度" in repository.chunks[0].content
    assert repository.chunks[0].member_id == "mem_1"
    assert len(vector_store.records) == 1
    assert vector_store.records[0].member_id == "mem_1"


def test_upload_pdf_uses_cloud_ocr_when_pdf_text_is_too_short(tmp_path):
    class ShortPdfExtractor:
        def extract_pages(self, path: Path):
            return [""]

    repository = FakeRepository()
    vector_store = FakeVectorStore()
    service = KbService(
        repository=repository,
        pdf_extractor=ShortPdfExtractor(),
        ocr_client=FakeOcrClient(),
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        upload_dir=tmp_path,
    )

    result = service.upload_pdf(file_name="scan.pdf", content=b"%PDF-1.4 fake", member_id="mem_1")

    assert result.status == "ready"
    assert repository.pages[0].text_content == "OCR 文本"


def test_upload_pdf_marks_document_failed_when_processing_fails(tmp_path):
    class BrokenPdfExtractor:
        def extract_pages(self, path: Path):
            raise RuntimeError("PDF 解析失败")

    repository = FakeRepository()
    service = KbService(
        repository=repository,
        pdf_extractor=BrokenPdfExtractor(),
        ocr_client=FakeOcrClient(),
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(),
        upload_dir=tmp_path,
    )

    result = service.upload_pdf(file_name="broken.pdf", content=b"%PDF-1.4 fake", member_id="mem_1")

    assert result.status == "failed"
    assert result.document_id == repository.documents[0].document_id
    assert result.error_message == "PDF 解析失败"
    assert repository.failed == [(result.document_id, "PDF 解析失败")]
