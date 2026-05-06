"""
utils/logger.py
---------------
Structured logging with structlog.
Outputs JSON in production, colored text in development.
Includes request-scoped context binding.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.types import EventDict, WrappedLogger

# Context variable for request-scoped trace ID
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="anonymous")


def get_request_id() -> str:
    return _request_id.get() or str(uuid.uuid4())


def set_request_context(request_id: str, user_id: str = "anonymous") -> None:
    _request_id.set(request_id)
    _user_id.set(user_id)


def _add_request_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject request-scoped context into every log entry."""
    rid = _request_id.get("")
    uid = _user_id.get("anonymous")
    if rid:
        event_dict["request_id"] = rid
    if uid and uid != "anonymous":
        event_dict["user_id"] = uid
    return event_dict


def _drop_color_message_key(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove uvicorn's color_message to keep logs clean."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Initialize structlog with shared processors.
    Call once at application startup.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _add_request_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _drop_color_message_key,
    ]

    if log_format == "json":
        # Production: machine-readable JSON
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        # Development: human-readable colored output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to route through structlog
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    for noisy in ["httpx", "httpcore", "chromadb", "sentence_transformers"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str, **initial_context: Any) -> structlog.BoundLogger:
    """
    Get a named logger with optional initial context.

    Usage:
        logger = get_logger(__name__, service="ingestion")
        logger.info("document_ingested", doc_id="abc123", chunks=42)
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


class MetricsLogger:
    """
    Lightweight in-process metrics collector.
    In production, replace with Prometheus push gateway or OTLP exporter.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._histograms: Dict[str, list] = {}
        self._logger = get_logger(__name__, component="metrics")

    def increment(self, metric: str, value: int = 1, **labels: Any) -> None:
        key = f"{metric}:{labels}"
        self._counters[key] = self._counters.get(key, 0) + value
        self._logger.debug("metric_counter", metric=metric, value=value, **labels)

    def record(self, metric: str, value: float, **labels: Any) -> None:
        key = f"{metric}:{labels}"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._logger.debug("metric_histogram", metric=metric, value=value, **labels)

    def snapshot(self) -> Dict[str, Any]:
        """Return current metrics snapshot."""
        return {
            "counters": dict(self._counters),
            "histogram_counts": {k: len(v) for k, v in self._histograms.items()},
            "histogram_means": {
                k: sum(v) / len(v) for k, v in self._histograms.items() if v
            },
        }


# Global metrics collector
metrics = MetricsLogger()
