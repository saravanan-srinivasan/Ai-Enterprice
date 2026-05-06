"""
api_gateway/main.py
--------------------
FastAPI application entrypoint.
Configures middleware, lifespan, CORS, rate limiting, and routes.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_gateway.routes import documents, queries, insights, health
from utils.cache import close_redis, get_redis
from utils.config import settings
from utils.database import create_all_tables, dispose_engine
from utils.logger import configure_logging, get_logger, set_request_context

configure_logging(settings.log_level, settings.log_format)
logger = get_logger(__name__, service="gateway")


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application startup and shutdown lifecycle."""
    logger.info(
        "application_starting",
        name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
    )

    # Initialize database schema
    try:
        await create_all_tables()
        logger.info("database_ready")
    except Exception as exc:
        logger.warning("database_init_failed", error=str(exc))

    # Warm up Redis
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("redis_ready")
    except Exception as exc:
        logger.warning("redis_init_failed", error=str(exc))

    # Pre-load vector store and embedding model
    try:
        from rag_pipeline.vector_store import get_vector_store
        store = get_vector_store()
        stats = store.collection_stats()
        logger.info("vector_store_ready", **stats)
    except Exception as exc:
        logger.warning("vector_store_init_failed", error=str(exc))

    logger.info("application_ready")
    yield

    # Shutdown
    logger.info("application_shutting_down")
    await dispose_engine()
    await close_redis()
    logger.info("application_stopped")


# ─── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Enterprise AI Knowledge & Decision Assistant — "
        "RAG-powered knowledge base with multi-agent decision support."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Inject request ID into logging context and add to response headers."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_context(request_id)

    start_time = time.monotonic()
    response: Response = await call_next(request)
    duration_ms = int((time.monotonic() - start_time) * 1000)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)

    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        request_id=request_id,
    )
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Per-IP rate limiting using Redis sliding window."""
    # Skip rate limiting for health checks
    if request.url.path in ("/health", "/metrics"):
        return await call_next(request)

    from utils.cache import cache_service
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining = await cache_service.check_rate_limit(client_ip)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": f"Maximum {settings.rate_limit_per_minute} requests per minute",
            },
            headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


# ─── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation Error", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred"},
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

app.include_router(health.router, tags=["System"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(queries.router, prefix="/api/v1", tags=["Queries"])
app.include_router(insights.router, prefix="/api/v1", tags=["Insights"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "docs": "/docs",
    }
