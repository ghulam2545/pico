from typing import List
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = ""
    database_user: str = ""
    database_password: str = ""

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{quote_plus(self.database_user)}:"
            f"{quote_plus(self.database_password)}@"
            f"{self.database_host}:{self.database_port}/"
            f"{self.database_name}"
        )

    @property
    def postgres_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{quote_plus(self.database_user)}:"
            f"{quote_plus(self.database_password)}@"
            f"{self.database_host}:{self.database_port}/"
            f"{self.database_name}"
        )

    # Redis
    redis_url: str = "redis://localhost:6380/0"

    # Ollama Local (embeddings)
    ollama_local_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"

    # Ollama Cloud / Remote (LLM) - OpenAI-compatible endpoint
    ollama_cloud_url: str = "https://api.ollama.com/v1"
    ollama_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.1

    # Retrieval
    top_k_dense: int = 15
    top_k_final: int = 6
    rrf_k: int = 50

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_length: int = 50

    # Memory
    redis_ttl_hours: int = 24
    redis_max_messages: int = 20

    # App
    cors_origins: List[str] = ["http://localhost:8000"]
    api_prefix: str = "/pico/api"
    secret_key: str = ""
    max_document_count: int = 30
    max_conversation_count: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
