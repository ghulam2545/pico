"""
Landing page route
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(tags=["index"])
templates_dir = Path(__file__).parent.parent / "templates"


@router.get("/")
async def index():
    """Landing page"""
    return FileResponse(templates_dir / "index.html")