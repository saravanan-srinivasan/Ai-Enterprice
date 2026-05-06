"""
utils/config.py
---------------
Centralized configuration management using Pydantic Settings.
All environment variables are validated and typed here.
Production-ready for Render + Netlify deployment.
"""

import os
from functools import lru_cache
from typing import Literal, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────
    app_name: str = "Enterprise AI Knowledge Assistant"
    app_version: str = "1.0.0"
    app_env: Literal["development", "staging", "production", "testing"] = "production"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production", min_length=16)

    # ── Server ───────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=int(os.getenv("PORT", "8000")), ge=1024, le=65535)
    workers: int = Field(default=1, ge=1)
    reload: bool = False

    # ── Database ─────────────────────────────────────────────────
    # Support DATABASE_URL from Render or construct from components
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://enterprise_user:enterprise_pass@localhost:5432/enterprise_ai"
        )
    )

    # ── Redis ────────────────────────────────────────────────────
    # Support REDIS_URL from Render or construct from components
    redis_url: str = Field(
        default_factory=lambda: os.getenv(
            "REDIS_URL",
            "redis://localhost:6379/0"
        )
    )
    cache_ttl_seconds: int = Field(default=3600, ge=60)

    # ── Vector Store ─────────────────────────────────────────────
    vector_store_type: Literal["chroma", "faiss"] = "chroma"
    # Use /opt/render/project/data for Render persistent storage
    data_dir: str = Field(
        default_factory=lambda: os.getenv(
            "DATA_DIR",
            "./data"
        )
    )
    chroma_persist_dir: str = Field(default="")
    faiss_index_dir: str = Field(default="")
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    top_k_retrieval: int = Field(default=5, ge=1, le=20)

    # ── LLM (Groq) ───────────────────────────────────────────────
    llm_provider: Literal["groq"] = "groq"
    groq_api_key: str = Field(default="", description="Groq API Key")
    llm_model: str = "llama-3.3-70b-versatile"
    llm_max_tokens: int = Field(default=4096, ge=256)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_timeout_seconds: int = Field(default=60, ge=10)

    # ── Chunking ─────────────────────────────────────────────────
    chunk_size: int = Field(default=512, ge=64)
    chunk_overlap: int = Field(default=64, ge=0)
    min_chunk_size: int = Field(default=100, ge=10)

    # ── Observability ────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # ── File Upload ──────────────────────────────────────────────
    max_file_size_mb: int = Field(default=50, ge=1, le=500)
    allowed_extensions: str = "pdf,txt,json,csv,log"
    upload_dir: str = ""

    # ── Agent System ─────────────────────────────────────────────
    agent_max_iterations: int = Field(default=10, ge=1, le=50)
    agent_timeout_seconds: int = Field(default=120, ge=30)
    memory_window_size: int = Field(default=10, ge=1, le=50)

    # ── Security ─────────────────────────────────────────────────
    # Production: use frontend domain from environment
    cors_origins: str = Field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000"
        )
    )
    api_key_header: str = "X-API-Key"
    rate_limit_per_minute: int = Field(default=60, ge=1)

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize derived paths
        if not self.chroma_persist_dir:
            self.chroma_persist_dir = os.path.join(self.data_dir, "chroma")
        if not self.faiss_index_dir:
            self.faiss_index_dir = os.path.join(self.data_dir, "faiss")
        if not self.upload_dir:
            self.upload_dir = os.path.join(self.data_dir, "uploads")
        
        # Ensure directories exist
        for dir_path in [self.chroma_persist_dir, self.faiss_index_dir, self.upload_dir]:
            os.makedirs(dir_path, exist_ok=True)

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: str) -> str:
        return v.strip()

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton — call this everywhere."""
    return Settings()


# Module-level singleton for convenience imports
settings = get_settings()
