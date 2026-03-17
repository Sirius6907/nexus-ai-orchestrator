"""
API Key Model — Supports external developer access and multi-tenant isolation.
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Index, func

from api.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: f"ak_{uuid.uuid4().hex}"
    )
    name: Mapped[str] = mapped_column(String(100))
    hashed_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    organization_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_org_id", "organization_id"),
    )
