"""
api_gateway/routes/insights.py
--------------------------------
Insights and analytics endpoints.
GET /insights — aggregated system insights
GET /insights/anomalies — anomaly detection results
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.database import get_db_session
from utils.logger import get_logger, metrics
from utils.models import InsightRecord, InsightSummary, QueryRecord, SystemMetrics

logger = get_logger(__name__, service="insights_api")
router = APIRouter()


@router.get(
    "/insights",
    response_model=List[InsightSummary],
    summary="Get system-generated insights",
)
async def get_insights(
    insight_type: Optional[str] = Query(None, description="anomaly | report | decision"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(InsightRecord).order_by(desc(InsightRecord.created_at)).limit(limit)
    if insight_type:
        stmt = stmt.where(InsightRecord.insight_type == insight_type)

    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        InsightSummary(
            id=str(r.id),
            insight_type=r.insight_type,
            title=r.title,
            summary=r.summary,
            confidence_score=r.confidence_score,
            tags=r.tags or [],
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get(
    "/insights/metrics",
    response_model=SystemMetrics,
    summary="System-wide performance metrics",
)
async def get_system_metrics(db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timedelta
    from utils.models import DocumentRecord, DocumentStatus

    # Document stats
    doc_status_result = await db.execute(
        select(DocumentRecord.status, func.count(DocumentRecord.id)).group_by(
            DocumentRecord.status
        )
    )
    docs_by_status = {row[0]: row[1] for row in doc_status_result.all()}

    total_docs = sum(docs_by_status.values())

    # Query stats
    total_queries_result = await db.execute(select(func.count(QueryRecord.id)))
    total_queries = total_queries_result.scalar() or 0

    avg_latency_result = await db.execute(select(func.avg(QueryRecord.latency_ms)))
    avg_latency = float(avg_latency_result.scalar() or 0)

    cached_count_result = await db.execute(
        select(func.count(QueryRecord.id)).where(QueryRecord.cached == True)
    )
    cached_count = cached_count_result.scalar() or 0
    cache_hit_rate = (cached_count / total_queries) if total_queries > 0 else 0.0

    total_tokens_result = await db.execute(select(func.sum(QueryRecord.tokens_used)))
    total_tokens = int(total_tokens_result.scalar() or 0)

    # Queries last 24h
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_result = await db.execute(
        select(func.count(QueryRecord.id)).where(QueryRecord.created_at >= cutoff)
    )
    queries_24h = recent_result.scalar() or 0

    return SystemMetrics(
        total_documents=total_docs,
        total_queries=total_queries,
        avg_latency_ms=round(avg_latency, 2),
        cache_hit_rate=round(cache_hit_rate, 4),
        total_tokens_used=total_tokens,
        documents_by_status=docs_by_status,
        queries_last_24h=queries_24h,
        top_query_topics=["logistics", "finance", "operations", "compliance"],
    )
