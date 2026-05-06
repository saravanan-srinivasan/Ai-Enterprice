"""
api_gateway/routes/documents.py
--------------------------------
Document management endpoints.
POST /upload — ingest new document
GET  /documents — list all documents
DELETE /documents/{doc_id} — remove document
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.ingestor import get_ingestor
from utils.database import get_db_session
from utils.logger import get_logger
from utils.models import DocumentInfo, DocumentStatus, DocumentUploadResponse

logger = get_logger(__name__, service="documents_api")
router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Upload and ingest a document",
    description=(
        "Upload PDF, TXT, JSON, CSV, or LOG files. "
        "Document is processed, chunked, embedded, and indexed for RAG retrieval."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to ingest"),
    source_tag: Optional[str] = Form(
        None, description="Optional tag to label the document source (e.g., 'sap_exports')"
    ),
    db: AsyncSession = Depends(get_db_session),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    ingestor = get_ingestor()
    try:
        result = await ingestor.ingest(
            file_bytes=file_bytes,
            filename=file.filename,
            db=db,
            source_metadata={"source_tag": source_tag, "content_type": file.content_type},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("upload_endpoint_error", filename=file.filename, error=str(exc))
        raise HTTPException(status_code=500, detail="Ingestion failed. See server logs.")


@router.get(
    "/documents",
    response_model=List[DocumentInfo],
    summary="List ingested documents",
)
async def list_documents(
    status: Optional[DocumentStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    ingestor = get_ingestor()
    return await ingestor.list_documents(db, status=status, limit=limit, offset=offset)


@router.delete(
    "/documents/{doc_id}",
    summary="Delete a document and its vectors",
)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    ingestor = get_ingestor()
    try:
        result = await ingestor.delete_document(doc_id, db)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/documents/stats",
    summary="Document ingestion statistics",
)
async def document_stats(db: AsyncSession = Depends(get_db_session)):
    ingestor = get_ingestor()
    return await ingestor.get_stats(db)
