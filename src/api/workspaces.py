from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from config.dependencies import get_db
from models.schemas import WorkspaceCreate, WorkspaceResponse, WorkspaceCreateResponse
from service.workspace import WorkspaceService
from service.vector_store import VectorStoreService
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceCreateResponse, status_code=201)
async def create_workspace(
        payload: WorkspaceCreate,
        db: AsyncSession = Depends(get_db),
):
    """Create a new workspace. The raw API key is returned only once."""
    try:
        workspace, raw_key = await WorkspaceService.create(db, payload.name, payload.identifier)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return WorkspaceCreateResponse(
        id=workspace.id,
        identifier=workspace.identifier,
        name=workspace.name,
        created_at=workspace.created_at,
        api_key=raw_key,
    )


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    """List all workspaces."""
    workspaces = await WorkspaceService.list_all(db)
    return [WorkspaceResponse.model_validate(w) for w in workspaces]


@router.delete("/{identifier}", status_code=204)
async def delete_workspace(
        identifier: str,
        db: AsyncSession = Depends(get_db),
):
    """Delete a workspace and all its data (documents, conversations, vectors)."""
    workspace = await WorkspaceService.get_by_identifier(db, identifier)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    VectorStoreService.delete_by_workspace(str(workspace.id))

    deleted = await WorkspaceService.delete(db, identifier)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")