"""
NutriAgent Backend — Chat Schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Chat Session
# ============================================================================


class ChatSessionCreate(BaseModel):
    """Create a new chat session."""

    session_type: str = Field("chat", description="chat | onboarding | feedback")
    title: str | None = None


class ChatSessionRead(BaseModel):
    id: UUID
    user_id: UUID
    session_type: str
    title: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None
    message_count: int = 0

    model_config = {"from_attributes": True}


# ============================================================================
# Chat Message
# ============================================================================


class ChatMessageCreate(BaseModel):
    """Send a message to the AI chat."""

    content: str = Field(..., min_length=1, max_length=4096)
    session_id: UUID | None = Field(None, description="Existing session ID (creates new session if omitted)")


class ChatMessageRead(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    metadata_json: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    """Full chat session with messages."""

    session: ChatSessionRead
    messages: list[ChatMessageRead] = Field(default_factory=list)
