"""
rag_pipeline/retriever.py
--------------------------
Hybrid retrieval engine: semantic (vector) + keyword (BM25).
Implements reciprocal rank fusion (RRF) to merge ranked lists.
Includes context compression to reduce LLM token usage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from rag_pipeline.vector_store import EmbeddingEngine, VectorStoreBase, embedding_engine, get_vector_store
from utils.config import settings
from utils.logger import get_logger, metrics
from utils.models import ChunkMetadata, SourceDocument

logger = get_logger(__name__, service="retriever")


@dataclass
class RetrievedChunk:
    """A chunk retrieved with combined relevance score."""

    chunk: ChunkMetadata
    semantic_score: float
    keyword_score: float
    combined_score: float
    rank: int


# ─── BM25 Keyword Retriever ───────────────────────────────────────────────────

class BM25Retriever:
    """
    In-memory BM25 retriever built from the current vector store corpus.
    Rebuilt on demand (acceptable for < 100K chunks; use Elasticsearch for larger).
    """

    def __init__(self, corpus: List[ChunkMetadata]) -> None:
        self._corpus = corpus
        tokenized = [self._tokenize(c.content) for c in corpus]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def retrieve(self, query: str, top_k: int) -> List[Tuple[ChunkMetadata, float]]:
        if not self._bm25 or not self._corpus:
            return []
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        # Pair scores with chunks and sort descending
        ranked = sorted(
            zip(self._corpus, scores), key=lambda x: x[1], reverse=True
        )
        return [(chunk, float(score)) for chunk, score in ranked[:top_k] if score > 0]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Lowercase, split on non-alphanumeric, remove stopwords
        tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
        stopwords = {
            "the", "a", "an", "is", "in", "on", "at", "to", "for",
            "of", "and", "or", "but", "with", "this", "that", "it",
            "be", "are", "was", "were", "have", "has", "from", "by",
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]


# ─── Context Compressor ───────────────────────────────────────────────────────

class ContextCompressor:
    """
    Compresses retrieved chunks to reduce LLM input tokens.
    Strategies:
      1. Score-threshold filtering
      2. Sentence relevance scoring
      3. Deduplication
    """

    def compress(
        self,
        chunks: List[RetrievedChunk],
        query: str,
        max_context_chars: int = 8000,
    ) -> List[RetrievedChunk]:
        # Step 1: Filter low-confidence chunks
        filtered = [c for c in chunks if c.combined_score > 0.1]
        if not filtered:
            filtered = chunks[:3]

        # Step 2: Deduplicate near-identical content
        deduped = self._deduplicate(filtered)

        # Step 3: Trim to token budget
        trimmed = self._trim_to_budget(deduped, max_context_chars)

        metrics.increment("context_chunks_compressed", value=len(chunks) - len(trimmed))
        return trimmed

    def _deduplicate(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        seen_fingerprints = set()
        unique = []
        for chunk in chunks:
            # Simple fingerprint: first 100 chars
            fp = chunk.chunk.content[:100].strip().lower()
            if fp not in seen_fingerprints:
                seen_fingerprints.add(fp)
                unique.append(chunk)
        return unique

    def _trim_to_budget(
        self, chunks: List[RetrievedChunk], max_chars: int
    ) -> List[RetrievedChunk]:
        result = []
        used = 0
        for chunk in sorted(chunks, key=lambda x: x.combined_score, reverse=True):
            chunk_len = len(chunk.chunk.content)
            if used + chunk_len <= max_chars:
                result.append(chunk)
                used += chunk_len
            else:
                remaining = max_chars - used
                if remaining > 200:
                    # Partial include — truncate content
                    truncated_chunk = RetrievedChunk(
                        chunk=ChunkMetadata(
                            **{
                                **chunk.chunk.model_dump(),
                                "content": chunk.chunk.content[:remaining] + "…",
                                "content_length": remaining,
                            }
                        ),
                        semantic_score=chunk.semantic_score,
                        keyword_score=chunk.keyword_score,
                        combined_score=chunk.combined_score,
                        rank=chunk.rank,
                    )
                    result.append(truncated_chunk)
                break
        return result


# ─── Hybrid Retriever ─────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Combines semantic (dense) and keyword (sparse) retrieval
    using Reciprocal Rank Fusion (RRF) for final ranking.
    """

    RRF_K = 60  # Standard RRF constant

    def __init__(self) -> None:
        self._vector_store: VectorStoreBase = get_vector_store()
        self._compressor = ContextCompressor()
        self._embedding_engine: EmbeddingEngine = embedding_engine

    def retrieve(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        use_compression: bool = True,
    ) -> List[RetrievedChunk]:
        """
        Full hybrid retrieval pipeline:
        1. Dense (semantic) search via vector store
        2. Sparse (keyword) search via BM25
        3. RRF fusion of both ranked lists
        4. Optional context compression
        """
        top_k = top_k or settings.top_k_retrieval
        fetch_k = top_k * 3  # Over-fetch to give RRF room to work

        # ── Semantic search ──────────────────────────────────────
        query_embedding = self._embedding_engine.embed_single(query)
        semantic_results = self._vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=fetch_k,
            filters=filters,
        )
        metrics.increment("semantic_searches")

        # ── BM25 keyword search ───────────────────────────────────
        # For production: replace with Elasticsearch or Typesense.
        # Here we build BM25 from the semantic candidates (re-ranking).
        corpus = [chunk for chunk, _ in semantic_results]
        bm25_results = []
        if corpus:
            bm25 = BM25Retriever(corpus)
            bm25_results = bm25.retrieve(query, top_k=fetch_k)
        metrics.increment("bm25_searches")

        # ── RRF Fusion ────────────────────────────────────────────
        fused = self._reciprocal_rank_fusion(
            semantic_results, bm25_results, top_k=top_k
        )

        # ── Context Compression ───────────────────────────────────
        if use_compression and fused:
            fused = self._compressor.compress(fused, query)

        logger.info(
            "retrieval_complete",
            query_preview=query[:60],
            semantic_hits=len(semantic_results),
            bm25_hits=len(bm25_results),
            fused_count=len(fused),
        )

        return fused

    def _reciprocal_rank_fusion(
        self,
        semantic: List[Tuple[ChunkMetadata, float]],
        keyword: List[Tuple[ChunkMetadata, float]],
        top_k: int,
    ) -> List[RetrievedChunk]:
        """
        RRF score = Σ 1 / (k + rank_i) for each ranked list.
        Merges semantic and keyword results with equal weight.
        """
        rrf_scores: Dict[str, Dict] = {}

        def _update(ranked_list: List[Tuple[ChunkMetadata, float]], field: str):
            for rank, (chunk, score) in enumerate(ranked_list, start=1):
                cid = chunk.chunk_id
                if cid not in rrf_scores:
                    rrf_scores[cid] = {
                        "chunk": chunk,
                        "rrf": 0.0,
                        "semantic_score": 0.0,
                        "keyword_score": 0.0,
                    }
                rrf_scores[cid]["rrf"] += 1.0 / (self.RRF_K + rank)
                rrf_scores[cid][field] = score

        _update(semantic, "semantic_score")
        _update(keyword, "keyword_score")

        sorted_chunks = sorted(
            rrf_scores.values(), key=lambda x: x["rrf"], reverse=True
        )[:top_k]

        return [
            RetrievedChunk(
                chunk=item["chunk"],
                semantic_score=item["semantic_score"],
                keyword_score=item["keyword_score"],
                combined_score=item["rrf"],
                rank=i + 1,
            )
            for i, item in enumerate(sorted_chunks)
        ]

    def to_source_documents(
        self, retrieved: List[RetrievedChunk]
    ) -> List[SourceDocument]:
        """Convert retrieved chunks to API-friendly SourceDocument schema."""
        return [
            SourceDocument(
                doc_id=r.chunk.doc_id,
                filename=r.chunk.filename,
                chunk_id=r.chunk.chunk_id,
                content_preview=r.chunk.content[:300].strip(),
                relevance_score=round(r.combined_score, 4),
                page_number=r.chunk.page_number,
            )
            for r in retrieved
        ]
