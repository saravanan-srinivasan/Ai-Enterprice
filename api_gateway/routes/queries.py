"""
api_gateway/routes/queries.py
------------------------------
Query execution and history endpoints.
POST /query         — submit a RAG query
GET  /history       — retrieve query history
GET  /history/{id}  — get specific query result
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_orchestrator.orchestrator import get_orchestrator
from utils.database import get_db_session
from utils.logger import get_logger
from utils.models import (
    AgentType,
    QueryHistoryItem,
    QueryRecord,
    QueryRequest,
    QueryResponse,
    QueryStatus,
)

logger = get_logger(__name__, service="queries_api")
router = APIRouter()


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Submit a knowledge query",
    description=(
        "Submit a natural language question to the enterprise knowledge base. "
        "Select agent type: query (factual), analysis (insights), report (structured doc), action (decision support)."
    ),
)
async def submit_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db_session),
):
    query_id = str(uuid.uuid4())
    orchestrator = get_orchestrator()

    # Create pending record
    record = QueryRecord(
        id=uuid.UUID(query_id),
        session_id=request.session_id,
        question=request.question,
        agent_type=request.agent_type.value,
        status=QueryStatus.PROCESSING.value,
    )
    db.add(record)
    await db.flush()

    try:
        response = await orchestrator.process_query(
            query_id=query_id,
            session_id=request.session_id,
            question=request.question,
            agent_type=request.agent_type,
            top_k=request.top_k,
            include_sources=request.include_sources,
            filters=request.filters,
        )

        # Persist completed record
        record.answer = response.answer
        record.status = QueryStatus.COMPLETED.value
        record.sources = [s.model_dump() for s in response.sources]
        record.confidence_score = response.confidence_score
        record.tokens_used = response.tokens_used
        record.latency_ms = response.latency_ms
        record.cached = response.cached
        record.completed_at = datetime.utcnow()
        await db.flush()

        return response

    except Exception as exc:
        record.status = QueryStatus.FAILED.value
        record.error_message = str(exc)[:500]
        record.completed_at = datetime.utcnow()
        await db.flush()
        logger.error("query_endpoint_error", query_id=query_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/history",
    response_model=List[QueryHistoryItem],
    summary="Get query history",
)
async def get_history(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    agent_type: Optional[AgentType] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(QueryRecord)
        .order_by(desc(QueryRecord.created_at))
        .limit(limit)
        .offset(offset)
    )

    if session_id:
        stmt = stmt.where(QueryRecord.session_id == session_id)
    if agent_type:
        stmt = stmt.where(QueryRecord.agent_type == agent_type.value)

    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        QueryHistoryItem(
            id=str(r.id),
            session_id=r.session_id,
            question=r.question,
            answer=r.answer,
            agent_type=AgentType(r.agent_type),
            status=QueryStatus(r.status),
            confidence_score=r.confidence_score,
            tokens_used=r.tokens_used or 0,
            latency_ms=r.latency_ms or 0,
            cached=r.cached or False,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get(
    "/history/{query_id}",
    response_model=QueryHistoryItem,
    summary="Get a specific query result",
)
async def get_query_by_id(
    query_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    import uuid as _uuid
    try:
        uid = _uuid.UUID(query_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid query ID format")

    stmt = select(QueryRecord).where(QueryRecord.id == uid)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Query not found")

    return QueryHistoryItem(
        id=str(record.id),
        session_id=record.session_id,
        question=record.question,
        answer=record.answer,
        agent_type=AgentType(record.agent_type),
        status=QueryStatus(record.status),
        confidence_score=record.confidence_score,
        tokens_used=record.tokens_used or 0,
        latency_ms=record.latency_ms or 0,
        cached=record.cached or False,
        created_at=record.created_at,
    )
