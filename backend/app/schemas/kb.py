from datetime import date, datetime

from pydantic import BaseModel, computed_field


class UploadResponse(BaseModel):
    document_id: str
    status: str
    page_count: int
    chunk_count: int
    error_message: str | None = None


class DocumentListItem(BaseModel):
    document_id: str
    file_name: str
    title: str | None
    patient_name: str | None
    exam_date: date | None
    institution: str | None
    status: str
    page_count: int
    created_at: datetime

    @computed_field
    @property
    def thumbnail_url(self) -> str:
        return f"/uploads/{self.document_id}/thumbnail.png"


class DocumentDetail(DocumentListItem):
    file_path: str
    file_size: int
    error_message: str | None


class DocumentChunkItem(BaseModel):
    chunk_id: str
    page_no: int
    content: str


class DocumentChunksResponse(BaseModel):
    items: list[DocumentChunkItem]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResultItem(BaseModel):
    document_id: str
    chunk_id: str
    page_no: int
    content: str
    score: float


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
