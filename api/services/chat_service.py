"""
Chat Service — the single source of truth for all session/message persistence.

Architecture:  Route → Service → DB (routes never touch SQLAlchemy directly)
"""
import uuid
import logging
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.session import ChatSession
from api.models.message import Message

logger = logging.getLogger(__name__)


# ─── Session CRUD ────────────────────────────────────────────────────────────

async def create_session(
    db: AsyncSession,
    title: str = "New Chat",
    model_config: Optional[dict] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[str] = None,
) -> ChatSession:
    """Create a new chat session and return it."""
    session = ChatSession(
        id=str(uuid.uuid4()),
        title=title,
        model_config_data=model_config,
        user_id=user_id,
        organization_id=organization_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info(f"Created session {session.id} for user {user_id}")
    return session


def _get_tenant_filter(user_id: Optional[int], organization_id: Optional[str]):
    """Returns the SQLAlchemy filter condition for tenant isolation."""
    if organization_id:
        return ChatSession.organization_id == organization_id
    elif user_id:
        return ChatSession.user_id == user_id
    else:
        # Fallback for anon/dev users if auth is partially disabled
        return True

async def list_sessions(
    db: AsyncSession, user_id: Optional[int] = None, organization_id: Optional[str] = None
) -> list[ChatSession]:
    """Return all sessions ordered by most recently updated."""
    query = select(ChatSession).where(_get_tenant_filter(user_id, organization_id)).order_by(ChatSession.updated_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession, session_id: str, user_id: Optional[int] = None, organization_id: Optional[str] = None
) -> Optional[ChatSession]:
    """Return a session with all its messages eagerly loaded."""
    query = (
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
        .where(_get_tenant_filter(user_id, organization_id))
    )
    result = await db.execute(query)
    return result.scalars().first()


async def delete_session(
    db: AsyncSession, session_id: str, user_id: Optional[int] = None, organization_id: Optional[str] = None
) -> bool:
    """Delete a session and cascade-delete all messages. Returns True if found."""
    # Ensure ownership before deleting
    session = await get_session(db, session_id, user_id, organization_id)
    if not session:
        return False
        
    result = await db.execute(
        delete(ChatSession).where(ChatSession.id == session_id)
    )
    await db.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info(f"Deleted session {session_id}")
    return deleted


async def update_session_title(
    db: AsyncSession, session_id: str, title: str, user_id: Optional[int] = None, organization_id: Optional[str] = None
) -> Optional[ChatSession]:
    """Update a session's title."""
    session = await get_session(db, session_id, user_id, organization_id)
    if session:
        session.title = title
        await db.commit()
        await db.refresh(session)
    return session


# ─── Message CRUD ────────────────────────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    model_used: Optional[str] = None,
    agent_trace: Optional[dict] = None,
    token_count: Optional[int] = None,
) -> Message:
    """Persist a single message to a session."""
    msg = Message(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        model_used=model_used,
        agent_trace=agent_trace,
        token_count=token_count,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    logger.debug(f"Persisted {role} message {msg.id} to session {session_id}")
    return msg


async def get_messages(
    db: AsyncSession, session_id: str
) -> list[Message]:
    """Return all messages for a session ordered chronologically."""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())
