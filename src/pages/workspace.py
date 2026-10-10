"""
Workspace page route — main 3-column UI. Data is loaded by the page via the API.
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(tags=["workspace"])
templates_dir = Path(__file__).parent.parent / "templates"


@router.get("/ws/{identifier}")
async def workspace_page(identifier: str):
    """Main workspace UI — three-column layout."""
    return FileResponse(templates_dir / "workspace.html")