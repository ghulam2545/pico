import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from config.dependencies import get_db, get_current_workspace
from models.db import Workspace, Conversation
from models.schemas import ConversationCreate, ConversationUpdate, ConversationResponse
from service.redis_memory import RedisMemoryService
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
        user_id: str = Query(...),
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace.id,
            Conversation.user_id == user_id,
        )
        .order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
    )
    convos = result.scalars().all()
    return [ConversationResponse.model_validate(c) for c in convos]


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
        payload: ConversationCreate,
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    convo = Conversation(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=payload.user_id,
        name=payload.name,
    )
    db.add(convo)
    await db.flush()
    await db.refresh(convo)
    return ConversationResponse.model_validate(convo)


@router.patch("/{convo_id}", response_model=ConversationResponse)
async def update_conversation(
        convo_id: uuid.UUID,
        payload: ConversationUpdate,
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == convo_id,
            Conversation.workspace_id == workspace.id,
        )
    )
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.name is not None:
        convo.name = payload.name
    if payload.pinned is not None:
        convo.pinned = payload.pinned
    convo.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(convo)
    return ConversationResponse.model_validate(convo)


@router.delete("/{convo_id}", status_code=204)
async def delete_conversation(
        convo_id: uuid.UUID,
        workspace: Workspace = Depends(get_current_workspace),
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == convo_id,
            Conversation.workspace_id == workspace.id,
        )
    )
    convo = result.scalar_one_or_none()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    RedisMemoryService.clear(str(convo_id))

    await db.delete(convo)
    log.info("conversation_deleted", convo_id=str(convo_id))
