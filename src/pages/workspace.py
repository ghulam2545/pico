"""
Workspace page route — main 3-column UI.
"""
from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse
from config.settings import settings

from config.dependencies import get_db, get_workspace_from_cookie
from models.db import Workspace, DocumentData, Conversation

log = structlog.get_logger()
router = APIRouter(tags=["workspace"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/ws/{identifier}", response_class=HTMLResponse)
async def workspace_page(
        identifier: str,
        request: Request,
        workspace: Optional[Workspace] = Depends(get_workspace_from_cookie),
        db: AsyncSession = Depends(get_db),
):
    """Main workspace UI — three-column layout."""
    if not workspace or workspace.identifier != identifier:
        return RedirectResponse(url=f"/?next=/ws/{identifier}", status_code=303)

    raw_api_key = request.cookies.get("pico_api_key", "")

    # Fetch documents
    docs_result = await db.execute(
        select(DocumentData)
        .where(DocumentData.workspace_id == workspace.id)
        .order_by(DocumentData.created_at.desc())
        .limit(settings.max_document_count)
    )
    documents = docs_result.scalars().all()

    # Fetch conversations
    convos_result = await db.execute(
        select(Conversation)
        .where(Conversation.workspace_id == workspace.id)
        .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
        .limit(settings.max_conversation_count)
    )
    conversations = convos_result.scalars().all()

    return templates.TemplateResponse(
        "workspace.html",
        {
            "request": request,
            "workspace": workspace,
            "documents": documents,
            "conversations": conversations,
            "api_key": raw_api_key,
            "api_prefix": "/pico/api",
        },
    )
