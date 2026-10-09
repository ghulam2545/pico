import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_db, get_current_workspace
from models.db import Workspace
from models.schemas import ChatRequest
from service.chat import ChatService
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
        payload: ChatRequest,
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    """
    Streaming chat endpoint.
    Returns Server-Sent Events (text/event-stream).

    SSE format:
      data: {"token": "..."} \n\n  — per token
      data: [SOURCES][{...}]  \n\n  — final source list
      data: [DONE]            \n\n  — stream end sentinel
    """
    user_id = (
        payload.document_filter.user_id
        if (payload.document_filter and payload.document_filter.user_id)
        else payload.user_id
    )
    filename = (
        payload.document_filter.filename
        if (payload.document_filter and payload.document_filter.filename)
        else None
    )

    async def event_generator():
        try:
            async for chunk in ChatService.stream(
                    query=payload.query,
                    conversation_id=payload.conversation_id,
                    workspace_id=str(workspace.id),
                    user_id=user_id,
                    filename=filename,
            ):
                yield chunk
        except Exception as e:
            log.error("chat_stream_error", error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )