"""
Workflow Models — DAG-based workflow definitions and execution history.
"""
import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, JSON, func

from api.db.base import Base


class Workflow(Base):
    """A reusable automation workflow defined as a DAG."""
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    dag_json: Mapped[dict] = mapped_column(JSON, default=dict)
    trigger_type: Mapped[str] = mapped_column(
        String(50), default="manual"
    )  # manual, cron, event
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowRun(Base):
    """A single execution of a workflow."""
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("workflows.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, running, completed, failed
    step_results: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workflow: Mapped["Workflow"] = relationship(back_populates="runs")
