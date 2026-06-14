import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.kb import (
    DocumentChunkItem,
    DocumentChunksResponse,
    DocumentDetail,
    DocumentListItem,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    UploadResponse,
)
from app.services.embedding import DashScopeEmbeddingService
from app.services.kb_service import KbService
from app.services.ocr import CloudOcrClient
from app.services.pdf_extractor import PdfExtractor
from app.services.vector_store import InMemoryVectorStore, MilvusVectorStore

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])
memory_vector_store = InMemoryVectorStore()


def get_vector_store():
    if settings.milvus_enabled:
        return MilvusVectorStore(
            uri=settings.milvus_uri,
            token=settings.milvus_token,
            collection_name=settings.milvus_collection,
            dimension=settings.embedding_dimension,
        )
    return memory_vector_store


def get_embedding_service():
    return DashScopeEmbeddingService(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key or settings.llm_api_key,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    member_id: str = Form(""),
    db: Session = Depends(get_db),
    embedding_service: DashScopeEmbeddingService = Depends(get_embedding_service),
    vector_store=Depends(get_vector_store),
):
    if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    member_id = member_id.strip()
    if not member_id:
        raise HTTPException(status_code=400, detail="请选择家人")
    member_repository = SqlAlchemyMemberRepository(db)
    if not member_repository.exists_by_member_id(member_id):
        raise HTTPException(status_code=404, detail="家人不存在")

    repository = SqlAlchemyKbRepository(db)
    service = KbService(
        repository=repository,
        pdf_extractor=PdfExtractor(),
        ocr_client=CloudOcrClient(settings.cloud_ocr_endpoint, settings.cloud_ocr_api_key),
        embedding_service=embedding_service,
        vector_store=vector_store,
        upload_dir=settings.upload_dir,
    )
    content = await file.read()
    return service.upload_pdf(file_name=file.filename, content=content, member_id=member_id)


@router.get("/documents", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)):
    repository = SqlAlchemyKbRepository(db)
    return repository.list_documents()


@router.get("/documents/{document_id}/chunks", response_model=DocumentChunksResponse)
def list_document_chunks(document_id: str, db: Session = Depends(get_db)):
    repository = SqlAlchemyKbRepository(db)
    if repository.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    chunks = repository.list_chunks_by_document(document_id)
    return DocumentChunksResponse(
        items=[
            DocumentChunkItem(
                chunk_id=chunk.chunk_id,
                page_no=chunk.page_no,
                content=chunk.content,
            )
            for chunk in chunks
        ]
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, db: Session = Depends(get_db)):
    repository = SqlAlchemyKbRepository(db)
    document = repository.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    repository = SqlAlchemyKbRepository(db)
    document = repository.delete_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    shutil.rmtree(Path(document.file_path).parent, ignore_errors=True)
    return Response(status_code=204)


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    embedding_service: DashScopeEmbeddingService = Depends(get_embedding_service),
    vector_store=Depends(get_vector_store),
):
    embedding = embedding_service.embed(request.query)
    hits = vector_store.search(embedding, request.top_k)
    repository = SqlAlchemyKbRepository(db)
    chunks = repository.get_chunks_by_ids([hit.chunk_id for hit in hits])
    score_by_chunk = {hit.chunk_id: hit.score for hit in hits}
    return SearchResponse(
        items=[
            SearchResultItem(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                page_no=chunk.page_no,
                content=chunk.content,
                score=score_by_chunk.get(chunk.chunk_id, 0.0),
            )
            for chunk in chunks
        ]
    )
