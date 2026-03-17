import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, JSON, Text, func
from datetime import datetime
from typing import Optional
from api.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))  # user, agent, system
    content: Mapped[str] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    agent_trace: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session = relationship("ChatSession", back_populates="messages")

    # Composite index for fast message retrieval per session
    __table_args__ = (
        Index("idx_messages_session_created", "session_id", "created_at"),
    )
