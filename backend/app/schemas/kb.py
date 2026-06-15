from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, computed_field


class UploadResponse(BaseModel):
    document_id: str
    status: str
    page_count: int
    chunk_count: int
    fact_extract_status: str = "pending"
    error_message: str | None = None


class DocumentListItem(BaseModel):
    document_id: str
    file_name: str
    title: str | None
    patient_name: str | None
    exam_date: date | None
    institution: str | None
    member_id: str | None = None
    member_name: str | None = None
    member_relation: str | None = None
    status: str
    fact_extract_status: str = "pending"
    fact_extract_error: str | None = None
    page_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
    member_id: str
    top_k: int = 5


class SearchResultItem(BaseModel):
    document_id: str
    chunk_id: str
    page_no: int
    content: str
    score: float


class SearchResponse(BaseModel):
    items: list[SearchResultItem]


class HealthFactItem(BaseModel):
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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthFactsResponse(BaseModel):
    fact_extract_status: str
    fact_extract_error: str | None = None
    items: list[HealthFactItem]
