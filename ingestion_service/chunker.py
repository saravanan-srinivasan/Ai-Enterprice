"""
ingestion_service/chunker.py
-----------------------------
Hybrid chunking strategy combining:
  1. Recursive character-level splitting (structure-aware)
  2. Semantic chunking (sentence boundary detection)
Produces metadata-rich chunks ready for embedding.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from utils.config import settings
from utils.logger import get_logger
from utils.models import ChunkMetadata
from ingestion_service.processor import ProcessedDocument

logger = get_logger(__name__, service="chunker")


@dataclass
class TextChunk:
    """A single text chunk with rich metadata."""

    chunk_id: str
    doc_id: str
    filename: str
    doc_type: str
    content: str
    chunk_index: int
    total_chunks: int  # placeholder, filled after splitting
    page_number: Optional[int] = None
    section_header: Optional[str] = None
    start_char: int = 0
    end_char: int = 0


class RecursiveCharacterChunker:
    """
    Recursively splits text using a hierarchy of separators.
    Attempts larger separators first; falls back to character-level.
    Preserves semantic boundaries where possible.
    """

    # Ordered from coarsest to finest
    SEPARATORS = [
        "\n\n\n",  # Section breaks
        "\n\n",    # Paragraph breaks
        "\n",      # Line breaks
        ". ",      # Sentence ends
        "! ",
        "? ",
        "; ",
        ", ",
        " ",       # Word boundaries
        "",        # Character fallback
    ]

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        min_chunk_size: int = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.min_chunk_size = min_chunk_size or settings.min_chunk_size

    def split(self, text: str) -> List[str]:
        """Return list of text chunks split recursively."""
        chunks = self._recursive_split(text, self.SEPARATORS)
        return self._merge_short_chunks(chunks)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        if not text.strip():
            return []

        if len(text) <= self.chunk_size:
            return [text]

        separator = separators[0] if separators else ""
        remaining_seps = separators[1:] if len(separators) > 1 else []

        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        chunks = []
        current = ""

        for split in splits:
            candidate = current + (separator if current else "") + split
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    if len(current) > self.chunk_size and remaining_seps:
                        chunks.extend(self._recursive_split(current, remaining_seps))
                    else:
                        chunks.append(current)
                    # Carry overlap
                    overlap_text = current[-self.chunk_overlap:] if self.chunk_overlap else ""
                    current = overlap_text + (separator if overlap_text else "") + split
                else:
                    if len(split) > self.chunk_size and remaining_seps:
                        chunks.extend(self._recursive_split(split, remaining_seps))
                        current = ""
                    else:
                        current = split

        if current.strip():
            chunks.append(current)

        return chunks

    def _merge_short_chunks(self, chunks: List[str]) -> List[str]:
        """Merge consecutive chunks that are below the minimum size threshold."""
        if not chunks:
            return []

        merged = []
        buffer = chunks[0]

        for chunk in chunks[1:]:
            if len(buffer) < self.min_chunk_size:
                buffer = buffer + " " + chunk
            else:
                merged.append(buffer)
                buffer = chunk

        if buffer.strip():
            merged.append(buffer)

        return merged


class SemanticChunker:
    """
    Sentence-boundary-aware chunker.
    Groups sentences into chunks, respecting size limits.
    Falls back to RecursiveCharacterChunker for large paragraphs.
    """

    SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._recursive = RecursiveCharacterChunker(chunk_size, chunk_overlap)

    def split(self, text: str) -> List[str]:
        sentences = self.SENTENCE_ENDINGS.split(text)
        chunks: List[str] = []
        current_sentences: List[str] = []
        current_len = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If a single sentence exceeds chunk_size, split it recursively
            if len(sentence) > self.chunk_size:
                if current_sentences:
                    chunks.append(" ".join(current_sentences))
                    current_sentences = []
                    current_len = 0
                chunks.extend(self._recursive.split(sentence))
                continue

            if current_len + len(sentence) + 1 > self.chunk_size and current_sentences:
                chunks.append(" ".join(current_sentences))
                # Overlap: keep last few sentences
                overlap_sentences = current_sentences[-2:]
                current_sentences = overlap_sentences + [sentence]
                current_len = sum(len(s) for s in current_sentences)
            else:
                current_sentences.append(sentence)
                current_len += len(sentence) + 1

        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks


class HybridChunker:
    """
    Production chunker that combines recursive + semantic strategies.
    - PDFs: page-aware + recursive
    - Logs: line-based with rolling windows
    - JSON/CSV: record-aware chunking
    - TXT: semantic (sentence boundary)
    """

    def __init__(self):
        self.recursive = RecursiveCharacterChunker()
        self.semantic = SemanticChunker()

    def chunk_document(self, doc: ProcessedDocument) -> List[TextChunk]:
        """Route document to appropriate chunking strategy."""
        if doc.doc_type == "pdf":
            return self._chunk_pdf(doc)
        elif doc.doc_type in ("log",):
            return self._chunk_log(doc)
        elif doc.doc_type in ("json", "csv"):
            return self._chunk_structured(doc)
        else:
            return self._chunk_text(doc)

    def _chunk_pdf(self, doc: ProcessedDocument) -> List[TextChunk]:
        chunks = []
        for page in doc.pages:
            page_text = page.get("text", "").strip()
            if not page_text:
                continue
            page_num = page.get("page_number", 1)
            text_chunks = self.semantic.split(page_text)
            for chunk_text in text_chunks:
                if len(chunk_text.strip()) < settings.min_chunk_size:
                    continue
                chunks.append(
                    TextChunk(
                        chunk_id=str(uuid.uuid4()),
                        doc_id=doc.doc_id,
                        filename=doc.filename,
                        doc_type=doc.doc_type,
                        content=chunk_text.strip(),
                        chunk_index=len(chunks),
                        total_chunks=0,  # set after
                        page_number=page_num,
                    )
                )
        return self._finalize(chunks)

    def _chunk_log(self, doc: ProcessedDocument) -> List[TextChunk]:
        """Log-aware: group by time windows or error blocks."""
        lines = doc.raw_text.splitlines()
        window_size = settings.chunk_size // 80  # ~80 chars per log line
        window_size = max(window_size, 5)

        chunks = []
        for i in range(0, len(lines), window_size):
            window = lines[i : i + window_size]
            content = "\n".join(window).strip()
            if len(content) < settings.min_chunk_size:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    doc_type=doc.doc_type,
                    content=content,
                    chunk_index=len(chunks),
                    total_chunks=0,
                    page_number=1,
                )
            )
        return self._finalize(chunks)

    def _chunk_structured(self, doc: ProcessedDocument) -> List[TextChunk]:
        """Structured data: chunk by records."""
        text_chunks = self.recursive.split(doc.raw_text)
        chunks = []
        for text in text_chunks:
            if len(text.strip()) < settings.min_chunk_size:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    doc_type=doc.doc_type,
                    content=text.strip(),
                    chunk_index=len(chunks),
                    total_chunks=0,
                    page_number=1,
                )
            )
        return self._finalize(chunks)

    def _chunk_text(self, doc: ProcessedDocument) -> List[TextChunk]:
        text_chunks = self.semantic.split(doc.raw_text)
        chunks = []
        for text in text_chunks:
            if len(text.strip()) < settings.min_chunk_size:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    doc_type=doc.doc_type,
                    content=text.strip(),
                    chunk_index=len(chunks),
                    total_chunks=0,
                    page_number=1,
                )
            )
        return self._finalize(chunks)

    def _finalize(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """Set total_chunks and log summary."""
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.total_chunks = total
        logger.debug(
            "chunking_complete",
            doc_id=chunks[0].doc_id if chunks else "none",
            total_chunks=total,
        )
        return chunks

    def to_chunk_metadata(self, chunk: TextChunk) -> ChunkMetadata:
        """Convert internal chunk to the shared ChunkMetadata schema."""
        from datetime import datetime

        return ChunkMetadata(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            filename=chunk.filename,
            doc_type=chunk.doc_type,
            chunk_index=chunk.chunk_index,
            total_chunks=chunk.total_chunks,
            content=chunk.content,
            content_length=len(chunk.content),
            page_number=chunk.page_number,
            section_header=chunk.section_header,
            created_at=datetime.utcnow().isoformat(),
        )
