import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Index, JSON, func
from api.db.base import Base
from typing import List, Optional
from datetime import datetime


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String, default="New Chat")
    model_config_data: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None
    )  # {"planner_model": "...", "coder_model": "..."}
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # Production index for fast session listing
    __table_args__ = (
        Index("idx_chat_sessions_updated_at", "updated_at"),
    )


# Avoid circular import — Message is imported at model registration time
from api.models.message import Message  # noqa: E402, F401
