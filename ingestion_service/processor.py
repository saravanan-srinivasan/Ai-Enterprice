"""
ingestion_service/processor.py
--------------------------------
Multi-format document processor.
Handles PDF, TXT, JSON, CSV, and log files.
Extracts text, metadata, and structural info.
"""

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chardet

from utils.config import settings
from utils.logger import get_logger

logger = get_logger(__name__, service="ingestion")


@dataclass
class ProcessedDocument:
    """Normalized representation of any ingested document."""

    doc_id: str
    filename: str
    doc_type: str
    raw_text: str
    pages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    structure: Dict[str, Any] = field(default_factory=dict)
    char_count: int = 0
    word_count: int = 0


class PDFProcessor:
    """Extract text and structure from PDF files."""

    def process(self, file_bytes: bytes, filename: str) -> ProcessedDocument:
        try:
            import pdfplumber

            doc_id = str(uuid.uuid4())
            pages = []
            tables = []
            full_text_parts = []

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    full_text_parts.append(text)

                    page_tables = page.extract_tables() or []
                    for tbl in page_tables:
                        if tbl:
                            tables.append(
                                {"page": page_num, "data": tbl, "row_count": len(tbl)}
                            )

                    pages.append(
                        {
                            "page_number": page_num,
                            "text": text,
                            "char_count": len(text),
                            "bbox": page.bbox,
                        }
                    )

                meta = pdf.metadata or {}
                doc_metadata = {
                    "title": meta.get("Title", filename),
                    "author": meta.get("Author", "Unknown"),
                    "page_count": len(pdf.pages),
                    "created": str(meta.get("CreationDate", "")),
                }

            raw_text = "\n\n".join(full_text_parts)
            logger.info(
                "pdf_processed",
                doc_id=doc_id,
                filename=filename,
                pages=len(pages),
                chars=len(raw_text),
            )

            return ProcessedDocument(
                doc_id=doc_id,
                filename=filename,
                doc_type="pdf",
                raw_text=raw_text,
                pages=pages,
                metadata=doc_metadata,
                tables=tables,
                char_count=len(raw_text),
                word_count=len(raw_text.split()),
            )

        except Exception as exc:
            logger.error("pdf_processing_failed", filename=filename, error=str(exc))
            raise


class TextProcessor:
    """Process plain text and log files."""

    def process(self, file_bytes: bytes, filename: str) -> ProcessedDocument:
        doc_id = str(uuid.uuid4())
        detected = chardet.detect(file_bytes)
        encoding = detected.get("encoding") or "utf-8"

        try:
            raw_text = file_bytes.decode(encoding, errors="replace")
        except Exception:
            raw_text = file_bytes.decode("utf-8", errors="replace")

        lines = raw_text.splitlines()
        is_log = filename.endswith(".log") or self._looks_like_log(raw_text[:2000])

        structure = {}
        if is_log:
            structure = self._parse_log_structure(lines)

        logger.info(
            "text_processed",
            doc_id=doc_id,
            filename=filename,
            lines=len(lines),
            chars=len(raw_text),
            is_log=is_log,
        )

        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            doc_type="log" if is_log else "txt",
            raw_text=raw_text,
            pages=[{"page_number": 1, "text": raw_text, "char_count": len(raw_text)}],
            metadata={"line_count": len(lines), "encoding": encoding, "is_log": is_log},
            structure=structure,
            char_count=len(raw_text),
            word_count=len(raw_text.split()),
        )

    def _looks_like_log(self, sample: str) -> bool:
        log_patterns = [
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
            r"\b(INFO|DEBUG|WARN|WARNING|ERROR|CRITICAL|FATAL)\b",
            r"\[.+?\]\s+\[.+?\]",
        ]
        return any(re.search(p, sample) for p in log_patterns)

    def _parse_log_structure(self, lines: List[str]) -> Dict[str, Any]:
        """Extract log-level distribution and timestamp range."""
        levels = {"INFO": 0, "DEBUG": 0, "WARN": 0, "ERROR": 0, "CRITICAL": 0}
        timestamps = []
        level_pattern = re.compile(
            r"\b(INFO|DEBUG|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b", re.I
        )
        ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})")

        for line in lines:
            m = level_pattern.search(line)
            if m:
                lvl = m.group(1).upper()
                normalized = "WARN" if lvl == "WARNING" else lvl
                normalized = "CRITICAL" if lvl == "FATAL" else normalized
                levels[normalized] = levels.get(normalized, 0) + 1

            ts_m = ts_pattern.search(line)
            if ts_m:
                timestamps.append(ts_m.group(1))

        return {
            "level_distribution": levels,
            "timestamp_range": {
                "start": timestamps[0] if timestamps else None,
                "end": timestamps[-1] if timestamps else None,
            },
            "total_lines": len(lines),
        }


class JSONProcessor:
    """Process JSON and JSON-Lines files (SAP records, API exports)."""

    def process(self, file_bytes: bytes, filename: str) -> ProcessedDocument:
        doc_id = str(uuid.uuid4())
        raw_str = file_bytes.decode("utf-8", errors="replace")

        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError:
            # Try JSON-Lines format
            data = []
            for line in raw_str.splitlines():
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Convert structured data to searchable text
        if isinstance(data, list):
            text_parts = [self._record_to_text(r, i) for i, r in enumerate(data)]
            raw_text = "\n\n".join(text_parts)
            metadata = {
                "record_count": len(data),
                "is_array": True,
                "sample_keys": list(data[0].keys()) if data and isinstance(data[0], dict) else [],
            }
        elif isinstance(data, dict):
            raw_text = self._record_to_text(data)
            metadata = {
                "record_count": 1,
                "is_array": False,
                "top_level_keys": list(data.keys()),
            }
        else:
            raw_text = str(data)
            metadata = {"raw_type": type(data).__name__}

        logger.info(
            "json_processed",
            doc_id=doc_id,
            filename=filename,
            chars=len(raw_text),
        )

        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            doc_type="json",
            raw_text=raw_text,
            pages=[{"page_number": 1, "text": raw_text, "char_count": len(raw_text)}],
            metadata=metadata,
            structure={"original_data": data if len(raw_str) < 50000 else {}},
            char_count=len(raw_text),
            word_count=len(raw_text.split()),
        )

    def _record_to_text(self, record: Any, index: int = 0) -> str:
        """Convert dict/list to human-readable key: value pairs."""
        if not isinstance(record, dict):
            return str(record)
        parts = [f"Record {index + 1}:"] if index >= 0 else []
        for k, v in record.items():
            if isinstance(v, dict):
                parts.append(f"  {k}: {json.dumps(v)}")
            elif isinstance(v, list):
                parts.append(f"  {k}: [{', '.join(str(x) for x in v[:5])}]")
            else:
                parts.append(f"  {k}: {v}")
        return "\n".join(parts)


class CSVProcessor:
    """Process CSV files with header detection and column summarization."""

    def process(self, file_bytes: bytes, filename: str) -> ProcessedDocument:
        doc_id = str(uuid.uuid4())
        raw_str = file_bytes.decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(raw_str))
        rows = list(reader)
        headers = reader.fieldnames or []

        # Convert to searchable text
        text_parts = []
        for i, row in enumerate(rows[:1000]):  # Cap at 1000 rows for embedding
            parts = [f"Row {i + 1}:"]
            for k, v in row.items():
                if v:
                    parts.append(f"  {k}: {v}")
            text_parts.append("\n".join(parts))

        raw_text = "\n\n".join(text_parts)
        if len(rows) > 1000:
            raw_text += f"\n\n[Truncated: {len(rows) - 1000} additional rows not shown]"

        logger.info(
            "csv_processed",
            doc_id=doc_id,
            filename=filename,
            rows=len(rows),
            columns=len(headers),
        )

        return ProcessedDocument(
            doc_id=doc_id,
            filename=filename,
            doc_type="csv",
            raw_text=raw_text,
            pages=[{"page_number": 1, "text": raw_text, "char_count": len(raw_text)}],
            metadata={
                "row_count": len(rows),
                "column_count": len(headers),
                "headers": headers,
            },
            char_count=len(raw_text),
            word_count=len(raw_text.split()),
        )


class DocumentProcessorFactory:
    """Factory that routes files to the correct processor."""

    _processors = {
        "pdf": PDFProcessor,
        "txt": TextProcessor,
        "log": TextProcessor,
        "json": JSONProcessor,
        "csv": CSVProcessor,
    }

    @classmethod
    def get_processor(cls, extension: str):
        ext = extension.lower().lstrip(".")
        processor_cls = cls._processors.get(ext)
        if not processor_cls:
            raise ValueError(
                f"Unsupported file type: .{ext}. "
                f"Supported: {list(cls._processors.keys())}"
            )
        return processor_cls()

    @classmethod
    def process(cls, file_bytes: bytes, filename: str) -> ProcessedDocument:
        ext = Path(filename).suffix.lower().lstrip(".")
        processor = cls.get_processor(ext)
        return processor.process(file_bytes, filename)
