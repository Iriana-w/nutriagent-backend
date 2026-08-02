"""
NutriAgent Backend — Chat Routes.

POST   /api/v1/chat/sessions
GET    /api/v1/chat/sessions
GET    /api/v1/chat/sessions/{id}
POST   /api/v1/chat/sessions/{id}/messages
PATCH  /api/v1/chat/sessions/{id}/close
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

from app.api.deps import CurrentUserId, DBSession, Pagination
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
)
from app.schemas.common import PaginatedResponse
from app.services.chat_service import (
    add_message,
    close_session,
    create_session,
    get_session,
    list_sessions,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/sessions", response_model=ChatSessionRead, status_code=201)
async def create_chat_session(
    db: DBSession,
    user_id: CurrentUserId,
    data: ChatSessionCreate,
) -> ChatSessionRead:
    """Create a new AI chat session."""
    session = await create_session(
        db,
        UUID(user_id),
        session_type=data.session_type,
        title=data.title,
    )
    return ChatSessionRead.model_validate(session)


@router.get("/sessions", response_model=PaginatedResponse[ChatSessionRead])
async def list_chat_sessions(
    db: DBSession,
    user_id: CurrentUserId,
    pagination: Pagination,
) -> PaginatedResponse[ChatSessionRead]:
    """List active chat sessions for the current user."""
    sessions, total = await list_sessions(
        db,
        UUID(user_id),
        page=pagination["page"],
        page_size=pagination["page_size"],
    )
    return PaginatedResponse.from_items(
        items=[ChatSessionRead.model_validate(s) for s in sessions],
        total=total,
        page=pagination["page"],
        page_size=pagination["page_size"],
    )


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    db: DBSession,
    user_id: CurrentUserId,
    session_id: UUID = Path(...),
) -> ChatHistoryResponse:
    """Get a chat session with full message history."""
    session = await get_session(db, session_id, UUID(user_id))
    return ChatHistoryResponse(
        session=ChatSessionRead.model_validate(session),
        messages=[ChatMessageRead.model_validate(m) for m in (session.messages or [])],
    )


@router.post("/sessions/{session_id}/messages", status_code=201)
async def send_message(
    db: DBSession,
    user_id: CurrentUserId,
    session_id: UUID = Path(...),
    data: ChatMessageCreate = ...,
):
    """Send a message and get AI response."""
    import json, traceback, httpx
    from sqlalchemy import text as sa_text
    from app.config import settings
    try:
        result = await db.execute(
            sa_text("SELECT id FROM chat_sessions WHERE id=:sid AND user_id=:uid"),
            {"sid": session_id, "uid": UUID(user_id)},
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Session not found")

        # 1. Store user message
        row = await db.execute(
            sa_text(
                "INSERT INTO chat_messages (session_id, role, content, metadata_json) "
                "VALUES (:sid, :role, :content, CAST(:meta AS jsonb)) "
                "RETURNING id, session_id, role, content, metadata_json, created_at"
            ),
            {"sid": session_id, "role": "user", "content": data.content, "meta": "{}"},
        )
        user_msg = row.fetchone()

        # 2. Fetch recent history for context (last 10 messages)
        history = await db.execute(
            sa_text(
                "SELECT role, content FROM chat_messages "
                "WHERE session_id=:sid ORDER BY created_at DESC LIMIT 10"
            ),
            {"sid": session_id},
        )
        messages = []
        for h in reversed(history.fetchall()):
            messages.append({"role": h.role, "content": h.content})

        # 3. Call DeepSeek API
        system_prompt = (
            "你是 NutriAgent，一个专为中国程序员打造的 AI 营养师助手。"
            "你的风格：温暖、专业、实用。给出具体可执行的饮食建议。"
            "用中文回答，简洁有条理，每次回复控制在 200 字以内。"
        )
        llm_messages = [{"role": "system", "content": system_prompt}]
        llm_messages.extend(messages[-8:])  # last 8 messages for context

        ai_response = "抱歉，AI 服务暂时不可用，请稍后再试。"
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                r = await client.post(
                    f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.DEFAULT_LLM_MODEL,
                        "messages": llm_messages,
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )
                if r.status_code == 200:
                    ai_response = r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass  # fallback message already set

        # 4. Store AI response
        ai_row = await db.execute(
            sa_text(
                "INSERT INTO chat_messages (session_id, role, content, metadata_json) "
                "VALUES (:sid, 'assistant', :content, CAST(:meta AS jsonb)) "
                "RETURNING id, session_id, role, content, metadata_json, created_at"
            ),
            {"sid": session_id, "content": ai_response, "meta": "{}"},
        )
        ai_msg = ai_row.fetchone()

        return {
            "id": str(ai_msg.id),
            "session_id": str(ai_msg.session_id),
            "role": "assistant",
            "content": ai_msg.content,
            "created_at": str(ai_msg.created_at),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()})


@router.patch("/sessions/{session_id}/close", response_model=ChatSessionRead)
async def close_chat_session(
    db: DBSession,
    user_id: CurrentUserId,
    session_id: UUID = Path(...),
) -> ChatSessionRead:
    """Close (deactivate) a chat session."""
    session = await close_session(db, session_id, UUID(user_id))
    return ChatSessionRead.model_validate(session)
