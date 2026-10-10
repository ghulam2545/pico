"""
Vector store service — batch upsert and delete embeddings via langchain-postgres PGVector.
"""
from typing import List

from langchain_core.documents import Document
from langchain_postgres import PGVector
from config.settings import settings
from core.embeddings import embeddings
from core.retriever import COLLECTION_NAME
import structlog

log = structlog.get_logger()
BATCH_SIZE = 60


def _get_store() -> PGVector:
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=settings.postgres_url_sync,
        use_jsonb=True,
    )


class VectorStoreService:

    @staticmethod
    def add_documents(documents: List[Document]) -> None:
        """Embed and upsert documents in batches."""
        if not documents:
            return
        store = _get_store()
        for i in range(0, len(documents), BATCH_SIZE):
            batch = documents[i: i + BATCH_SIZE]
            store.add_documents(batch)
            log.info("vectors_upserted", batch_start=i, batch_size=len(batch))
        log.info("all_vectors_upserted", total=len(documents))

    @staticmethod
    def delete_by_metadata(
            workspace_id: str,
            user_id: str,
            filename: str,
    ) -> None:
        """Delete all vectors for a specific document."""
        store = _get_store()
        try:
            store.delete(
                filter={
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "filename": filename,
                }
            )
            log.info(
                "vectors_deleted",
                workspace_id=workspace_id,
                user_id=user_id,
                filename=filename,
            )
        except Exception as e:
            log.warning("vector_delete_failed", error=str(e))

    @staticmethod
    def delete_by_workspace(workspace_id: str) -> None:
        """Delete all vectors for a workspace."""
        store = _get_store()
        try:
            store.delete(filter={"workspace_id": workspace_id})
            log.info("workspace_vectors_deleted", workspace_id=workspace_id)
        except Exception as e:
            log.warning("workspace_vector_delete_failed", error=str(e))
