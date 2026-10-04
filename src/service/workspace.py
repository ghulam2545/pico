"""
Workspace service — create, read, delete workspaces.
API keys are generated as secure random tokens and stored as SHA-256 hashes.
"""
import hashlib
import secrets
import uuid
from typing import Optional, List, Tuple

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.db import Workspace
import structlog

log = structlog.get_logger()


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.strip().encode()).hexdigest()


def generate_api_key() -> Tuple[str, str]:
    """Return (raw_key, hashed_key). Store only the hash."""
    raw = secrets.token_hex(32)  # 64-char hex string
    return raw, _hash_key(raw)


class WorkspaceService:

    @staticmethod
    async def create(db: AsyncSession, name: str, identifier: str) -> Tuple[Workspace, str]:
        """Create a workspace. Returns (workspace, raw_api_key)."""
        existing = await db.execute(select(Workspace).where(Workspace.identifier == identifier))
        if existing.scalar_one_or_none():
            raise ValueError(f"Identifier '{identifier}' already taken")

        raw_key, key_hash = generate_api_key()
        workspace = Workspace(
            id=uuid.uuid4(),
            identifier=identifier,
            name=name,
            api_key_hash=key_hash,
        )
        db.add(workspace)
        await db.flush()
        await db.refresh(workspace)
        log.info("workspace_created", identifier=identifier, workspace_id=str(workspace.id))
        return workspace, raw_key

    @staticmethod
    async def get_by_identifier(db: AsyncSession, identifier: str) -> Optional[Workspace]:
        result = await db.execute(select(Workspace).where(Workspace.identifier == identifier))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_api_key(db: AsyncSession, raw_key: str) -> Optional[Workspace]:
        if not raw_key:
            return None
        key_hash = _hash_key(raw_key)
        result = await db.execute(
            select(Workspace).where(Workspace.api_key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(db: AsyncSession) -> List[Workspace]:
        result = await db.execute(select(Workspace).order_by(Workspace.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def delete(db: AsyncSession, identifier: str) -> bool:
        result = await db.execute(
            delete(Workspace).where(Workspace.identifier == identifier)
        )
        deleted = (result.rowcount or 0) > 0
        if deleted:
            log.info("workspace_deleted", identifier=identifier)
        return deleted
