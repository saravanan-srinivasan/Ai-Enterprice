"""
ingestion_service/ingestor.py
------------------------------
Document ingestion pipeline coordinator.
Orchestrates: process → chunk → embed → store → persist metadata.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.chunker import HybridChunker
from ingestion_service.processor import DocumentProcessorFactory, ProcessedDocument
from rag_pipeline.vector_store import embedding_engine, get_vector_store
from utils.config import settings
from utils.logger import get_logger, metrics
from utils.models import (
    ChunkMetadata,
    DocumentRecord,
    DocumentStatus,
    DocumentUploadResponse,
    DocumentInfo,
)

logger = get_logger(__name__, service="ingestor")


class DocumentIngestor:
    """
    Full document ingestion pipeline.
    Thread-safe and idempotent per document ID.
    """

    def __init__(self) -> None:
        self._chunker = HybridChunker()
        self._vector_store = get_vector_store()
        os.makedirs(settings.upload_dir, exist_ok=True)

    async def ingest(
        self,
        file_bytes: bytes,
        filename: str,
        db: AsyncSession,
        source_metadata: Optional[Dict] = None,
    ) -> DocumentUploadResponse:
        """
        Full ingestion pipeline:
        1. Validate & save file
        2. Process (extract text, tables, structure)
        3. Chunk (semantic + recursive)
        4. Embed (sentence-transformers)
        5. Store in vector DB
        6. Persist metadata in PostgreSQL
        """
        doc_id = str(uuid.uuid4())
        ext = Path(filename).suffix.lower().lstrip(".")

        # ── Validate ─────────────────────────────────────────────
        if ext not in settings.allowed_extensions_list:
            raise ValueError(f"File type '.{ext}' not allowed")

        if len(file_bytes) > settings.max_file_size_bytes:
            raise ValueError(
                f"File exceeds maximum size of {settings.max_file_size_mb}MB"
            )

        # ── Persist initial record ────────────────────────────────
        record = DocumentRecord(
            id=uuid.UUID(doc_id),
            filename=f"{doc_id}_{filename}",
            original_name=filename,
            doc_type=ext,
            file_size_bytes=len(file_bytes),
            status=DocumentStatus.PROCESSING,
            source_metadata=source_metadata or {},
        )
        db.add(record)
        await db.flush()
        logger.info("ingestion_started", doc_id=doc_id, filename=filename)

        try:
            # ── Save to disk ──────────────────────────────────────
            save_path = os.path.join(settings.upload_dir, f"{doc_id}_{filename}")
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            # ── Process document ──────────────────────────────────
            processed: ProcessedDocument = DocumentProcessorFactory.process(
                file_bytes, filename
            )
            processed.doc_id = doc_id  # Override with our tracked ID

            # ── Chunk ─────────────────────────────────────────────
            chunks = self._chunker.chunk_document(processed)
            if not chunks:
                raise ValueError("Document produced zero chunks after processing")

            # ── Convert to ChunkMetadata ──────────────────────────
            chunk_metas: List[ChunkMetadata] = [
                self._chunker.to_chunk_metadata(c) for c in chunks
            ]

            # ── Generate embeddings ───────────────────────────────
            texts = [c.content for c in chunk_metas]
            embeddings = embedding_engine.embed(texts, batch_size=32)

            # ── Store in vector DB ────────────────────────────────
            inserted = self._vector_store.upsert(chunk_metas, embeddings)

            # ── Update DB record ──────────────────────────────────
            record.status = DocumentStatus.INDEXED
            record.chunk_count = inserted
            record.indexed_at = datetime.utcnow()
            record.collection_name = "enterprise_knowledge"
            await db.flush()

            metrics.increment("documents_ingested", doc_type=ext)
            metrics.increment("chunks_created", value=inserted)
            logger.info(
                "ingestion_complete",
                doc_id=doc_id,
                filename=filename,
                chunks=inserted,
                chars=processed.char_count,
            )

            return DocumentUploadResponse(
                document_id=doc_id,
                filename=filename,
                status=DocumentStatus.INDEXED,
                message=f"Successfully ingested {inserted} chunks from '{filename}'",
            )

        except Exception as exc:
            record.status = DocumentStatus.FAILED
            record.error_message = str(exc)[:1000]
            await db.flush()
            metrics.increment("ingestion_failures", doc_type=ext)
            logger.error("ingestion_failed", doc_id=doc_id, filename=filename, error=str(exc))
            raise

    async def list_documents(
        self,
        db: AsyncSession,
        status: Optional[DocumentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentInfo]:
        """List all documents with optional status filter."""
        stmt = select(DocumentRecord).order_by(DocumentRecord.created_at.desc())
        if status:
            stmt = stmt.where(DocumentRecord.status == status.value)
        stmt = stmt.limit(limit).offset(offset)

        result = await db.execute(stmt)
        records = result.scalars().all()

        return [
            DocumentInfo(
                id=str(r.id),
                filename=r.filename,
                original_name=r.original_name,
                doc_type=r.doc_type,
                file_size_bytes=r.file_size_bytes,
                status=DocumentStatus(r.status),
                chunk_count=r.chunk_count or 0,
                created_at=r.created_at,
                indexed_at=r.indexed_at,
            )
            for r in records
        ]

    async def delete_document(
        self, doc_id: str, db: AsyncSession
    ) -> Dict[str, str]:
        """Remove a document from vector store and database."""
        # Remove vectors
        deleted_vectors = self._vector_store.delete_document(doc_id)

        # Remove DB record
        stmt = select(DocumentRecord).where(
            DocumentRecord.id == uuid.UUID(doc_id)
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            # Remove file from disk
            file_path = os.path.join(settings.upload_dir, record.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            await db.delete(record)

        logger.info("document_deleted", doc_id=doc_id, vectors_removed=deleted_vectors)
        return {
            "doc_id": doc_id,
            "vectors_deleted": str(deleted_vectors),
            "status": "deleted",
        }

    async def get_stats(self, db: AsyncSession) -> Dict:
        """Return ingestion pipeline statistics."""
        count_by_status = await db.execute(
            select(DocumentRecord.status, func.count(DocumentRecord.id))
            .group_by(DocumentRecord.status)
        )
        stats = dict(count_by_status.all())

        total_chunks = await db.execute(
            select(func.sum(DocumentRecord.chunk_count))
        )
        total_chunk_count = total_chunks.scalar() or 0

        vector_stats = self._vector_store.collection_stats()

        return {
            "documents_by_status": stats,
            "total_chunks_indexed": total_chunk_count,
            "vector_store": vector_stats,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_ingestor: Optional[DocumentIngestor] = None


def get_ingestor() -> DocumentIngestor:
    global _ingestor
    if _ingestor is None:
        _ingestor = DocumentIngestor()
    return _ingestor
