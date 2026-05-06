"""
utils/models.py
---------------
Shared Pydantic models and domain types used across all services.
SQLAlchemy ORM models for PostgreSQL persistence.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


# ─── SQLAlchemy Base ────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Enums ──────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class QueryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, Enum):
    QUERY = "query"
    ANALYSIS = "analysis"
    REPORT = "report"
    ACTION = "action"


class DocumentType(str, Enum):
    PDF = "pdf"
    TXT = "txt"
    JSON = "json"
    CSV = "csv"
    LOG = "log"


# ─── ORM Models ─────────────────────────────────────────────────────────────

class DocumentRecord(Base):
    """Metadata for ingested enterprise documents."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(512), nullable=False)
    original_name = Column(String(512), nullable=False)
    doc_type = Column(String(20), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    status = Column(String(20), default=DocumentStatus.PENDING, nullable=False)
    chunk_count = Column(Integer, default=0)
    collection_name = Column(String(256), nullable=True)
    source_metadata = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    indexed_at = Column(DateTime(timezone=True), nullable=True)


class QueryRecord(Base):
    """Audit log for every query processed by the system."""

    __tablename__ = "query_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(256), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    agent_type = Column(String(20), default=AgentType.QUERY)
    status = Column(String(20), default=QueryStatus.PENDING)
    sources = Column(JSON, default=list)
    confidence_score = Column(Float, nullable=True)
    tokens_used = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    cached = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class InsightRecord(Base):
    """Persisted analytical insights and generated reports."""

    __tablename__ = "insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insight_type = Column(String(50), nullable=False)  # anomaly | report | decision
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=False)
    detail = Column(JSON, default=dict)
    confidence_score = Column(Float, nullable=True)
    source_documents = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── Pydantic Request/Response Schemas ──────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    status: DocumentStatus
    message: str


class DocumentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    original_name: str
    doc_type: str
    file_size_bytes: int
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    indexed_at: Optional[datetime] = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: AgentType = AgentType.QUERY
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = True
    filters: Optional[Dict[str, Any]] = None


class SourceDocument(BaseModel):
    doc_id: str
    filename: str
    chunk_id: str
    content_preview: str
    relevance_score: float
    page_number: Optional[int] = None


class QueryResponse(BaseModel):
    query_id: str
    session_id: str
    question: str
    answer: str
    agent_type: AgentType
    status: QueryStatus
    sources: List[SourceDocument] = []
    confidence_score: float
    tokens_used: int
    latency_ms: int
    cached: bool
    reasoning_steps: Optional[List[str]] = None  # Chain-of-thought (optional expose)
    created_at: datetime


class QueryHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    question: str
    answer: Optional[str]
    agent_type: AgentType
    status: QueryStatus
    confidence_score: Optional[float]
    tokens_used: int
    latency_ms: int
    cached: bool
    created_at: datetime


class InsightSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    insight_type: str
    title: str
    summary: str
    confidence_score: Optional[float]
    tags: List[str]
    created_at: datetime


class SystemMetrics(BaseModel):
    total_documents: int
    total_queries: int
    avg_latency_ms: float
    cache_hit_rate: float
    total_tokens_used: int
    documents_by_status: Dict[str, int]
    queries_last_24h: int
    top_query_topics: List[str]


class AnomalyReport(BaseModel):
    anomaly_id: str
    severity: str  # critical | high | medium | low
    category: str
    description: str
    affected_records: List[str]
    recommended_action: str
    confidence_score: float
    detected_at: datetime


class ChunkMetadata(BaseModel):
    """Metadata stored alongside each vector embedding."""

    chunk_id: str
    doc_id: str
    filename: str
    doc_type: str
    chunk_index: int
    total_chunks: int
    content: str
    content_length: int
    page_number: Optional[int] = None
    section_header: Optional[str] = None
    created_at: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
