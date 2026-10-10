"""
Ollama embeddings wrapper (local nomic-embed-text).
Provides a singleton instance used across the application.
"""
from langchain_ollama import OllamaEmbeddings
from config.settings import settings
import structlog

log = structlog.get_logger()


def get_embeddings() -> OllamaEmbeddings:
    """Return an OllamaEmbeddings instance pointed at local Ollama."""
    return OllamaEmbeddings(
        model=settings.embed_model,
        base_url=settings.ollama_local_url,
    )


# Singleton
embeddings = get_embeddings()