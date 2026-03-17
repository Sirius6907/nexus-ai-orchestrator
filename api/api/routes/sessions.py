"""
Session Routes — REST endpoints for chat session management.

Architecture: Route → Service → DB
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from api.db.session import get_db
from api.services import chat_service

from api.models.user import User
from api.core.auth import require_current_user

router = APIRouter()


# ─── Request/Response Models ─────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"
    planner_model: Optional[str] = None
    coder_model: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    model_used: Optional[str] = None
    agent_trace: Optional[dict] = None
    token_count: Optional[int] = None
    created_at: str

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    id: str
    title: str
    model_config_data: Optional[dict] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = []


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/")
async def list_sessions(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all chat sessions, most recent first."""
    sessions = await chat_service.list_sessions(
        db, user_id=current_user.id, organization_id=current_user.organization_id
    )
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "model_config_data": s.model_config_data,
                "created_at": str(s.created_at),
                "updated_at": str(s.updated_at),
            }
            for s in sessions
        ]
    }


@router.post("/")
async def create_session(
    req: CreateSessionRequest, 
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session."""
    model_config = None
    if req.planner_model or req.coder_model:
        model_config = {
            "planner_model": req.planner_model,
            "coder_model": req.coder_model,
        }

    session = await chat_service.create_session(
        db, 
        title=req.title or "New Chat", 
        model_config=model_config,
        user_id=current_user.id,
        organization_id=current_user.organization_id
    )
    return {
        "id": session.id,
        "title": session.title,
        "model_config_data": session.model_config_data,
        "created_at": str(session.created_at),
        "updated_at": str(session.updated_at),
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str, 
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a session with all its messages."""
    session = await chat_service.get_session(
        db, session_id, user_id=current_user.id, organization_id=current_user.organization_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "title": session.title,
        "model_config_data": session.model_config_data,
        "created_at": str(session.created_at),
        "updated_at": str(session.updated_at),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "model_used": m.model_used,
                "agent_trace": m.agent_trace,
                "token_count": m.token_count,
                "created_at": str(m.created_at),
            }
            for m in session.messages
        ],
    }


@router.patch("/{session_id}")
async def update_session(
    session_id: str,
    req: UpdateSessionRequest,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a session's title."""
    session = await chat_service.update_session_title(
        db, session_id, req.title, user_id=current_user.id, organization_id=current_user.organization_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": session.id, "title": session.title}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str, 
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a session and all its messages."""
    deleted = await chat_service.delete_session(
        db, session_id, user_id=current_user.id, organization_id=current_user.organization_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}
