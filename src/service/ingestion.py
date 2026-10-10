"""
Ingestion service — full pipeline from raw file bytes to stored embeddings.

Pipeline:
  raw bytes → detect type → SHA-256 hash → duplicate check
             → load (format-aware) → chunk → embed → upsert pgvector
             → insert document_data row
"""
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.loaders import load_document, detect_file_type, SUPPORTED_EXTENSIONS
from core.chunker import chunker
from models.db import DocumentData
from service.vector_store import VectorStoreService
import structlog

log = structlog.get_logger()


@dataclass
class IngestionResult:
    id: uuid.UUID
    filename: str
    status: str  # "ingested" | "duplicate"
    chunk_count: int
    file_hash: str
    file_type: str


class IngestionService:
    @staticmethod
    def _compute_hash(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    @staticmethod
    async def ingest(
            db: AsyncSession,
            file_bytes: bytes,
            filename: str,
            workspace_id: str,
            user_id: str,
            is_public: bool = False,
    ) -> IngestionResult:
        """Ingest a single file. Returns an IngestionResult."""
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        file_type = detect_file_type(filename)
        file_hash = IngestionService._compute_hash(file_bytes)

        # Duplicate check (same workspace + user + hash)
        existing = await db.execute(
            select(DocumentData).where(
                DocumentData.workspace_id == uuid.UUID(workspace_id),
                DocumentData.user_id == user_id,
                DocumentData.file_hash == file_hash,
            )
        )
        existing_doc = existing.scalar_one_or_none()
        if existing_doc:
            log.info("duplicate_file", filename=filename, file_hash=file_hash)
            return IngestionResult(
                id=existing_doc.id,
                filename=filename,
                status="duplicate",
                chunk_count=existing_doc.chunk_count,
                file_hash=file_hash,
                file_type=file_type,
            )

        # Delete old vectors for same filename (re-ingestion)
        old = await db.execute(
            select(DocumentData).where(
                DocumentData.workspace_id == uuid.UUID(workspace_id),
                DocumentData.user_id == user_id,
                DocumentData.filename == filename,
            )
        )
        old_doc = old.scalar_one_or_none()
        if old_doc:
            VectorStoreService.delete_by_metadata(
                workspace_id=workspace_id, user_id=user_id, filename=filename
            )
            await db.delete(old_doc)
            await db.flush()

        base_meta = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "filename": filename,
            "file_hash": file_hash,
            "file_type": file_type,
        }

        # Load raw documents
        raw_docs = load_document(file_bytes, filename, base_meta)

        # Chunk
        chunks = chunker.chunk_documents(raw_docs)

        if not chunks:
            raise ValueError(f"No usable content extracted from '{filename}'")

        # Embed + store in pgvector
        VectorStoreService.add_documents(chunks)

        # Record in document_data
        doc_record = DocumentData(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(workspace_id),
            user_id=user_id,
            filename=filename,
            file_hash=file_hash,
            file_type=file_type,
            chunk_count=len(chunks),
            is_public=is_public,
        )
        db.add(doc_record)
        await db.flush()
        await db.refresh(doc_record)

        log.info(
            "file_ingested",
            filename=filename,
            chunks=len(chunks),
            workspace_id=workspace_id,
        )
        return IngestionResult(
            id=doc_record.id,
            filename=filename,
            status="ingested",
            chunk_count=len(chunks),
            file_hash=file_hash,
            file_type=file_type,
        )
