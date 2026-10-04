from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ── Workspace ────────────────────────────────────────────────────────────────
class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    identifier: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class WorkspaceResponse(BaseModel):
    id: UUID
    identifier: str
    name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WorkspaceCreateResponse(WorkspaceResponse):
    """Returned only once on creation — includes the raw API key."""
    api_key: str


# ── Documents ────────────────────────────────────────────────────────────────
class IngestResponse(BaseModel):
    id: UUID
    filename: str
    status: str  # "ingested" | "duplicate"
    chunk_count: int
    file_hash: str
    file_type: str


class DocumentResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: str
    filename: str
    file_type: str
    chunk_count: int
    is_public: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    files: List[DocumentResponse]
    total: int
    page: int
    size: int
    total_pages: int


# ── Conversations ─────────────────────────────────────────────────────────────
class ConversationCreate(BaseModel):
    name: str = Field(default="New conversation", max_length=300)
    user_id: str = Field(..., min_length=1, max_length=200)


class ConversationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=300)
    pinned: Optional[bool] = None


class ConversationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: str
    name: str
    pinned: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Chat ──────────────────────────────────────────────────────────────────────
class DocumentFilter(BaseModel):
    user_id: Optional[str] = None
    filename: Optional[str] = None  # None = all user docs in workspace


class ChatRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    document_filter: Optional[DocumentFilter] = None


class ChatSource(BaseModel):
    filename: str
    heading: Optional[str] = None
    chunk_index: int = 0
    score: float = 1.0


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: List[ChatSource]
    latency_ms: int
