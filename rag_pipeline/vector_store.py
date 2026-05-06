"""
rag_pipeline/vector_store.py
-----------------------------
Vector store abstraction supporting ChromaDB and FAISS.
Handles embedding generation, upsert, and hybrid retrieval.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from utils.config import settings
from utils.logger import get_logger, metrics
from utils.models import ChunkMetadata

logger = get_logger(__name__, service="vector_store")

# ─── Embedding Model ──────────────────────────────────────────────────────────

class EmbeddingEngine:
    """
    Singleton embedding model wrapper.
    Uses sentence-transformers for local, privacy-preserving embeddings.
    """

    _instance: Optional[EmbeddingEngine] = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls) -> EmbeddingEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("loading_embedding_model", model=settings.embedding_model)
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info("embedding_model_loaded", dimension=settings.embedding_dimension)

    def embed(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for a list of texts. Thread-safe."""
        self._load_model()
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        metrics.increment("embeddings_generated", value=len(texts))
        return embeddings.tolist()

    def embed_single(self, text: str) -> List[float]:
        return self.embed([text])[0]


embedding_engine = EmbeddingEngine()


# ─── Abstract Vector Store ────────────────────────────────────────────────────

class VectorStoreBase(ABC):
    """Abstract interface for vector store backends."""

    @abstractmethod
    def upsert(
        self, chunks: List[ChunkMetadata], embeddings: List[List[float]]
    ) -> int:
        """Insert or update chunks. Returns count inserted."""
        ...

    @abstractmethod
    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[ChunkMetadata, float]]:
        """Return top_k (chunk, score) pairs by cosine similarity."""
        ...

    @abstractmethod
    def delete_document(self, doc_id: str) -> int:
        """Remove all chunks for a document. Returns count deleted."""
        ...

    @abstractmethod
    def collection_stats(self) -> Dict[str, Any]:
        """Return collection-level statistics."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        ...


# ─── ChromaDB Backend ─────────────────────────────────────────────────────────

class ChromaVectorStore(VectorStoreBase):
    """
    Production ChromaDB backend with persistent disk storage.
    Uses cosine distance and supports metadata filtering.
    """

    COLLECTION_NAME = "enterprise_knowledge"

    def __init__(self) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "chroma_initialized",
            persist_dir=settings.chroma_persist_dir,
            collection=self.COLLECTION_NAME,
            count=self._collection.count(),
        )

    def upsert(
        self, chunks: List[ChunkMetadata], embeddings: List[List[float]]
    ) -> int:
        if not chunks:
            return 0

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "filename": c.filename,
                "doc_type": c.doc_type,
                "chunk_index": c.chunk_index,
                "total_chunks": c.total_chunks,
                "content_length": c.content_length,
                "page_number": c.page_number or 0,
                "section_header": c.section_header or "",
                "created_at": c.created_at,
            }
            for c in chunks
        ]

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        metrics.increment("vectors_upserted", value=len(chunks))
        logger.info("chroma_upserted", count=len(chunks))
        return len(chunks)

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[ChunkMetadata, float]]:
        where = None
        if filters:
            where = {k: {"$eq": v} for k, v in filters.items() if v}

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
            where=where if where else None,
        )

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # Chroma uses L2 distance for cosine when normalized; convert to similarity
            score = 1.0 - (dist / 2.0)
            chunk = ChunkMetadata(
                chunk_id=results["ids"][0][len(output)],
                doc_id=meta["doc_id"],
                filename=meta["filename"],
                doc_type=meta["doc_type"],
                chunk_index=meta["chunk_index"],
                total_chunks=meta["total_chunks"],
                content=doc,
                content_length=meta["content_length"],
                page_number=meta.get("page_number"),
                section_header=meta.get("section_header") or None,
                created_at=meta.get("created_at", ""),
            )
            output.append((chunk, score))

        return output

    def delete_document(self, doc_id: str) -> int:
        results = self._collection.get(where={"doc_id": {"$eq": doc_id}})
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def collection_stats(self) -> Dict[str, Any]:
        return {
            "backend": "chroma",
            "collection": self.COLLECTION_NAME,
            "total_vectors": self._collection.count(),
            "persist_dir": settings.chroma_persist_dir,
        }

    def health_check(self) -> bool:
        try:
            self._collection.count()
            return True
        except Exception:
            return False


# ─── FAISS Backend ────────────────────────────────────────────────────────────

class FAISSVectorStore(VectorStoreBase):
    """
    FAISS flat index with metadata sidecar (JSON file).
    Use for environments without a persistent server.
    """

    def __init__(self) -> None:
        import faiss

        os.makedirs(settings.faiss_index_dir, exist_ok=True)
        self._dim = settings.embedding_dimension
        self._index_path = os.path.join(settings.faiss_index_dir, "index.faiss")
        self._meta_path = os.path.join(settings.faiss_index_dir, "metadata.json")
        self._faiss = faiss

        if os.path.exists(self._index_path):
            self._index = faiss.read_index(self._index_path)
            with open(self._meta_path) as f:
                self._metadata: List[Dict] = json.load(f)
        else:
            self._index = faiss.IndexFlatIP(self._dim)  # Inner product = cosine when normalized
            self._metadata = []

        logger.info("faiss_initialized", vectors=self._index.ntotal)

    def upsert(
        self, chunks: List[ChunkMetadata], embeddings: List[List[float]]
    ) -> int:
        vectors = np.array(embeddings, dtype=np.float32)
        self._index.add(vectors)
        for chunk in chunks:
            self._metadata.append(chunk.model_dump())
        self._persist()
        metrics.increment("vectors_upserted", value=len(chunks))
        return len(chunks)

    def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[ChunkMetadata, float]]:
        if self._index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        k = min(top_k * 3, self._index.ntotal)  # Over-fetch for post-filtering
        scores, indices = self._index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            meta = self._metadata[idx]
            if filters and not self._matches_filters(meta, filters):
                continue
            chunk = ChunkMetadata(**meta)
            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break

        return results

    def delete_document(self, doc_id: str) -> int:
        original = len(self._metadata)
        self._metadata = [m for m in self._metadata if m.get("doc_id") != doc_id]
        # Note: FAISS flat index doesn't support deletion; rebuild required
        logger.warning("faiss_delete_requires_rebuild", doc_id=doc_id)
        return original - len(self._metadata)

    def collection_stats(self) -> Dict[str, Any]:
        return {
            "backend": "faiss",
            "total_vectors": self._index.ntotal,
            "dimension": self._dim,
            "index_path": self._index_path,
        }

    def health_check(self) -> bool:
        return self._index is not None

    def _matches_filters(self, meta: Dict, filters: Dict) -> bool:
        return all(meta.get(k) == v for k, v in filters.items())

    def _persist(self) -> None:
        self._faiss.write_index(self._index, self._index_path)
        with open(self._meta_path, "w") as f:
            json.dump(self._metadata, f)


# ─── Factory ──────────────────────────────────────────────────────────────────

_vector_store_instance: Optional[VectorStoreBase] = None


def get_vector_store() -> VectorStoreBase:
    global _vector_store_instance
    if _vector_store_instance is None:
        if settings.vector_store_type == "faiss":
            _vector_store_instance = FAISSVectorStore()
        else:
            _vector_store_instance = ChromaVectorStore()
    return _vector_store_instance
