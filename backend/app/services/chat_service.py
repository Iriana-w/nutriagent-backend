"""
NutriAgent Backend — Chat Service.

Handles chat session management and message history.
"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatSession


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    session_type: str = "chat",
    title: str | None = None,
) -> ChatSession:
    """Create a new chat session."""
    session = ChatSession(
        user_id=user_id,
        session_type=session_type,
        title=title,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> ChatSession:
    """Get a chat session with messages, verified ownership."""
    result = await db.execute(
        select(ChatSession).where(
            and_(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError("ChatSession", str(session_id))
    return session


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ChatSession], int]:
    """Paginated list of user's chat sessions."""
    conditions = [ChatSession.user_id == user_id, ChatSession.is_active == True]

    count_stmt = select(func.count()).select_from(ChatSession).where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(ChatSession)
        .where(and_(*conditions))
        .order_by(ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    sessions = list(result.scalars().all())

    return sessions, total


async def add_message(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> ChatMessage:
    """Add a message to a chat session. Verifies session ownership."""
    session = await get_session(db, session_id, user_id)

    # Use raw SQL to avoid ORM column type issues with VECTOR column
    result = await db.execute(
        text(
            "INSERT INTO chat_messages (session_id, role, content, metadata_json) "
            "VALUES (:sid, :role, :content, CAST(:meta AS jsonb)) RETURNING *"
        ),
        {
            "sid": session_id,
            "role": role,
            "content": content,
            "meta": json.dumps(metadata or {}),
        },
    )
    row = result.fetchone()
    # Build a ChatMessage from the returned row
    message = ChatMessage(
        id=row.id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        metadata_json=row.metadata_json or {},
        created_at=row.created_at,
    )
    return message


async def close_session(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> ChatSession:
    """Close (deactivate) a chat session."""
    session = await get_session(db, session_id, user_id)
    session.is_active = False
    await db.flush()
    await db.refresh(session)
    return session
