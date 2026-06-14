from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AI Model Settings (supports OpenAI, Gemini, Ollama, etc.)
    api_key: str = "placeholder_key"
    api_base_url: str | None = None
    api_embedding_model: str = "text-embedding-3-small"
    api_chat_model: str = "gpt-4o"
    api_max_tokens: int = 1000

    # Database — supports Railway's DATABASE_URL or individual vars
    database_url_override: str | None = None  # Set DATABASE_URL_OVERRIDE for Railway
    postgres_user: str = "documind"
    postgres_password: str = "documind_pass"
    postgres_db: str = "documind_db"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            url = self.database_url_override
            # Ensure we use asyncpg driver
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync database URL for Celery tasks and Scrapy pipelines."""
        if self.database_url_override:
            url = self.database_url_override
            # Ensure we use sync psycopg2 driver
            if "asyncpg" in url:
                url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
            if not url.startswith("postgresql://"):
                url = "postgresql://" + url.split("://", 1)[-1]
            return url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # RAG
    chunk_size: int = 512
    chunk_overlap: int = 128
    top_k_results: int = 5
    similarity_threshold: float = 0.0
    faiss_index_path: str = "./data/faiss_index"

    # Scraper
    scrapy_concurrent_requests: int = 8
    scrapy_download_delay: float = 0.5
    scrapy_depth_limit: int = 10

    # App
    app_env: str = "development"
    app_port: int = 8000
    port: int | None = None  # Railway injects PORT
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
