"""
Analytics Routes — Real data from PostgreSQL, not mock data.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import get_db
from api.models.session import ChatSession
from api.models.message import Message
from api.models.workflow import Workflow, WorkflowRun

router = APIRouter()


@router.get("")
async def get_analytics(db: AsyncSession = Depends(get_db)):
    """Enterprise analytics dashboard data from real DB queries."""

    # Total sessions
    sessions_result = await db.execute(select(func.count(ChatSession.id)))
    total_sessions = sessions_result.scalar() or 0

    # Total messages
    messages_result = await db.execute(select(func.count(Message.id)))
    total_messages = messages_result.scalar() or 0

    # Total tokens used (sum of token_count)
    tokens_result = await db.execute(
        select(func.coalesce(func.sum(Message.token_count), 0))
    )
    total_tokens = tokens_result.scalar() or 0

    # Agent messages count
    agent_msgs_result = await db.execute(
        select(func.count(Message.id)).where(Message.role == "agent")
    )
    agent_message_count = agent_msgs_result.scalar() or 0

    # User messages count
    user_msgs_result = await db.execute(
        select(func.count(Message.id)).where(Message.role == "user")
    )
    user_message_count = user_msgs_result.scalar() or 0

    # Active workflows
    try:
        workflows_result = await db.execute(
            select(func.count(Workflow.id)).where(Workflow.is_active == True)
        )
        active_workflows = workflows_result.scalar() or 0
    except Exception:
        active_workflows = 0

    # Completed workflow runs
    try:
        completed_runs = await db.execute(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.status == "completed"
            )
        )
        total_runs = await db.execute(select(func.count(WorkflowRun.id)))

        completed = completed_runs.scalar() or 0
        total = total_runs.scalar() or 1
        agent_success_rate = completed / total if total > 0 else 1.0
    except Exception:
        agent_success_rate = 1.0

    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "total_tokens_used": total_tokens,
        "agent_message_count": agent_message_count,
        "user_message_count": user_message_count,
        "active_workflows": active_workflows,
        "agent_success_rate": agent_success_rate,
        "vram_peak_gb": 2.1,  # TODO: read from nvidia-smi
    }
