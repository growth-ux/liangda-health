import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.repositories.health_fact_repository import SqlAlchemyHealthFactRepository
from app.repositories.kb_repository import SqlAlchemyKbRepository
from app.repositories.member_repository import SqlAlchemyMemberRepository
from app.schemas.kb import (
    DocumentChunkItem,
    DocumentChunksResponse,
    DocumentDetail,
    DocumentListItem,
    HealthFactsResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    UploadResponse,
)
from app.services.embedding import DashScopeEmbeddingService
from app.services.kb_service import KbService
from app.services.ocr import CloudOcrClient
from app.services.pdf_extractor import PdfExtractor
from app.services.health_fact_tasks import extract_health_facts_for_document
from app.services.vector_store import MilvusVectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


def get_vector_store():
    return MilvusVectorStore(
        uri=settings.milvus_uri,
        token=settings.milvus_token,
        collection_name=settings.milvus_collection,
        dimension=settings.embedding_dimension,
    )


def get_embedding_service():
    return DashScopeEmbeddingService(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key or settings.llm_api_key,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
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
    result = service.upload_pdf(file_name=file.filename, content=content, member_id=member_id)
    if result.status == "ready":
        background_tasks.add_task(extract_health_facts_for_document, result.document_id)
    return result


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


@router.get("/documents/{document_id}/facts", response_model=HealthFactsResponse)
def list_document_health_facts(document_id: str, db: Session = Depends(get_db)):
    kb_repository = SqlAlchemyKbRepository(db)
    document = kb_repository.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    fact_repository = SqlAlchemyHealthFactRepository(db)
    return HealthFactsResponse(
        fact_extract_status=document.fact_extract_status,
        fact_extract_error=document.fact_extract_error,
        items=fact_repository.list_by_document(document_id),
    )


@router.get("/members/{member_id}/facts", response_model=HealthFactsResponse)
def list_member_health_facts(member_id: str, db: Session = Depends(get_db)):
    member_repository = SqlAlchemyMemberRepository(db)
    if not member_repository.exists_by_member_id(member_id):
        raise HTTPException(status_code=404, detail="家人不存在")
    fact_repository = SqlAlchemyHealthFactRepository(db)
    return HealthFactsResponse(
        fact_extract_status="ready",
        fact_extract_error=None,
        items=fact_repository.list_by_member(member_id),
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
    member_repository = SqlAlchemyMemberRepository(db)
    if not member_repository.exists_by_member_id(request.member_id):
        raise HTTPException(status_code=400, detail="家人不存在")
    logger.info(
        "kb_api_search embedding start member_id=%s top_k=%s query_chars=%s",
        request.member_id,
        request.top_k,
        len(request.query),
    )
    embedding = embedding_service.embed(request.query)
    logger.info("kb_api_search embedding done member_id=%s", request.member_id)
    hits = vector_store.search(embedding, request.top_k, member_id=request.member_id)
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
