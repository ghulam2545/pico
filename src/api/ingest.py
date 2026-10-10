from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from config.dependencies import get_db, get_current_workspace
from models.db import Workspace
from models.schemas import IngestResponse
from service.ingestion import IngestionService
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/upload", response_model=IngestResponse)
async def upload_file(
        file: UploadFile = File(...),
        user_id: str = Form(...),
        is_public: bool = Form(False),
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    """Upload and ingest a single document."""
    file_bytes = await file.read()
    filename = file.filename or "unknown"

    try:
        result = await IngestionService.ingest(
            db=db,
            file_bytes=file_bytes,
            filename=filename,
            workspace_id=str(workspace.id),
            user_id=user_id,
            is_public=is_public,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return IngestResponse(
        id=result.id,
        filename=result.filename,
        status=result.status,
        chunk_count=result.chunk_count,
        file_hash=result.file_hash,
        file_type=result.file_type,
    )


@router.post("/bulk", response_model=List[IngestResponse])
async def upload_bulk(
        files: List[UploadFile] = File(...),
        user_id: str = Form(...),
        is_public: bool = Form(False),
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    """Upload and ingest multiple documents."""
    results = []
    errors = []

    for file in files:
        try:
            file_bytes = await file.read()
            filename = file.filename or "unknown"
            result = await IngestionService.ingest(
                db=db,
                file_bytes=file_bytes,
                filename=filename,
                workspace_id=str(workspace.id),
                user_id=user_id,
                is_public=is_public,
            )
            results.append(
                IngestResponse(
                    id=result.id,
                    filename=result.filename,
                    status=result.status,
                    chunk_count=result.chunk_count,
                    file_hash=result.file_hash,
                    file_type=result.file_type,
                )
            )
        except ValueError as e:
            errors.append({"filename": file.filename, "error": str(e)})

    if errors and not results:
        raise HTTPException(status_code=400, detail={"errors": errors})

    return results