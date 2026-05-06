"""
api_gateway/routes/health.py
-----------------------------
System health and readiness endpoints.
GET /health       — liveness probe
GET /health/ready — readiness probe (checks all dependencies)
GET /metrics      — Prometheus-style metrics snapshot
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from utils.cache import cache_service
from utils.config import settings
from utils.logger import get_logger, metrics

logger = get_logger(__name__, service="health")
router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def health_liveness():
    return {"status": "alive", "service": settings.app_name, "version": settings.app_version}


@router.get("/health/ready", summary="Readiness probe — checks all dependencies")
async def health_readiness():
    checks = {}
    overall = "healthy"

    # Redis
    try:
        redis_ok = await cache_service.health_check()
        checks["redis"] = "ok" if redis_ok else "degraded"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        overall = "degraded"

    # Vector store
    try:
        from rag_pipeline.vector_store import get_vector_store
        vs = get_vector_store()
        vs_ok = vs.health_check()
        stats = vs.collection_stats()
        checks["vector_store"] = {"status": "ok" if vs_ok else "error", **stats}
    except Exception as exc:
        checks["vector_store"] = f"error: {exc}"
        overall = "degraded"

    # Database
    try:
        from utils.database import get_engine
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        overall = "degraded"

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "checks": checks,
            "version": settings.app_version,
        },
    )


@router.get("/metrics", summary="Runtime metrics snapshot")
async def get_metrics():
    snapshot = metrics.snapshot()
    return {
        "service": settings.app_name,
        "environment": settings.app_env,
        "metrics": snapshot,
    }
