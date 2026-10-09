import uuid
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_db, get_current_workspace
from models.db import Workspace, DocumentData
from models.schemas import DocumentListResponse, DocumentResponse
from service.vector_store import VectorStoreService
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        user_id: str = Query(None),
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    """List documents in the current workspace, with optional user_id filter."""
    offset = (page - 1) * size
    base_filter = [DocumentData.workspace_id == workspace.id]
    if user_id:
        base_filter.append(DocumentData.user_id == user_id)

    count_q = select(func.count()).select_from(DocumentData).where(*base_filter)
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    data_q = (
        select(DocumentData)
        .where(*base_filter)
        .order_by(DocumentData.created_at.desc())
        .limit(size)
        .offset(offset)
    )
    rows = await db.execute(data_q)
    docs = rows.scalars().all()

    return DocumentListResponse(
        files=[DocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
        doc_id: uuid.UUID,
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    """Delete a document and its associated vectors."""
    result = await db.execute(
        select(DocumentData).where(
            DocumentData.id == doc_id,
            DocumentData.workspace_id == workspace.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    VectorStoreService.delete_by_metadata(
        workspace_id=str(workspace.id),
        user_id=doc.user_id,
        filename=doc.filename,
    )

    await db.delete(doc)
    log.info("document_deleted", doc_id=str(doc_id))
