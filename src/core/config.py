from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Document Intelligence RAG API"
    app_version: str = "0.2.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    # MongoDB
    mongo_host: str = "127.0.0.1"
    mongo_port: int = Field(default=27018, ge=1, le=65535)
    mongo_database: str = "rag_db"
    mongo_app_username: str
    mongo_app_password: SecretStr
    mongo_auth_source: str = "rag_db"

    # Qdrant and embeddings
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "document_chunks"
    embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_dimensions: int = Field(default=384, gt=0)

    # File storage and chunking
    storage_dir: Path = Path("assets/uploads")
    max_upload_size_mb: int = Field(default=25, ge=1)
    chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=150, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)

    # Celery / Redis
    celery_broker_url: str = "redis://127.0.0.1:6380/0"
    celery_result_backend: str = "redis://127.0.0.1:6380/1"

    # LLM provider selection
    llm_provider: Literal["openai", "gemini", "groq"] = "openai"
    llm_timeout_seconds: int = Field(default=45, ge=1, le=180)

    # OpenAI
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""

    # Gemini
    gemini_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai"
    )
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""

    # Groq
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = ""

    # Legacy settings for backward compatibility
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"development", "testing", "staging", "production"}:
            raise ValueError("Invalid environment.")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid log level.")
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            raise ValueError("api_v1_prefix must not be empty.")
        if not value.startswith("/"):
            raise ValueError("api_v1_prefix must start with '/'.")
        return value

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(
        cls,
        value: int,
        info: ValidationInfo,
    ) -> int:
        size = info.data.get("chunk_size", 1000)
        if value >= size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
