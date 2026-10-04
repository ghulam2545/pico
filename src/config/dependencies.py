"""
FastAPI dependency injection helpers.
"""
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, AsyncGenerator

from db.session import get_async_session
from models.db import Workspace
from service.workspace import WorkspaceService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession via the context manager."""
    async with get_async_session() as session:
        yield session


async def get_current_workspace(
        x_api_key: str = Header(..., alias="X-API-Key"),
        db: AsyncSession = Depends(get_db),
) -> Workspace:
    """
    Validate X-API-Key header and return the associated Workspace.
    Raises 401 if the key is invalid.
    """
    workspace = await WorkspaceService.get_by_api_key(db, x_api_key)
    if not workspace:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return workspace


async def get_workspace_from_cookie(
        request: Request,
        db: AsyncSession = Depends(get_db),
) -> Optional[Workspace]:
    """
    Used by Jinja2 page routes — reads API key from the 'pico_api_key' cookie.
    Returns None if no cookie / invalid key (page will redirect to log in).
    """
    raw_key = request.cookies.get("pico_api_key")
    if not raw_key:
        return None
    return await WorkspaceService.get_by_api_key(db, raw_key)
