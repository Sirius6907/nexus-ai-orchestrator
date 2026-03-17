"""
Workflow Service — CRUD and DAG execution engine.

DAG JSON Format:
{
  "steps": [
    {"id": "step_1", "type": "llm_call", "model": "gemma3:1b", "prompt": "..."},
    {"id": "step_2", "type": "tool_call", "tool": "web_search", "input": "..."},
    {"id": "step_3", "type": "webhook", "url": "...", "payload": {...}}
  ]
}
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.workflow import Workflow, WorkflowRun
from api.worker.tasks import run_workflow_step_task

logger = logging.getLogger(__name__)


# ─── CRUD Operations ─────────────────────────────────────────────────────────

async def list_workflows(db: AsyncSession) -> list[Workflow]:
    result = await db.execute(
        select(Workflow).order_by(Workflow.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_workflow(
    db: AsyncSession,
    name: str,
    description: str = "",
    dag_json: dict | None = None,
    trigger_type: str = "manual",
    schedule: str | None = None,
) -> Workflow:
    workflow = Workflow(
        name=name,
        description=description,
        dag_json=dag_json or {"steps": []},
        trigger_type=trigger_type,
        schedule=schedule,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflow(db: AsyncSession, workflow_id: str) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    return result.scalars().first()


async def delete_workflow(db: AsyncSession, workflow_id: str):
    wf = await get_workflow(db, workflow_id)
    if wf:
        await db.delete(wf)
        await db.commit()


# ─── Execution ───────────────────────────────────────────────────────────────

async def execute_workflow(db: AsyncSession, workflow_id: str) -> WorkflowRun:
    """Execute a workflow by running its DAG steps."""
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")

    # Create run record
    run = WorkflowRun(
        workflow_id=workflow_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    try:
        steps = workflow.dag_json.get("steps", [])
        step_results = {}

        for step in steps:
            step_id = step.get("id", f"step_{len(step_results)}")
            logger.info(f"Workflow {workflow_id}: executing {step_id}")

            # Dispatch step to Celery worker
            task = run_workflow_step_task.delay(workflow_id, step)
            result = task.get(timeout=120)  # Wait up to 2 minutes

            step_results[step_id] = result

            # Stop on failure
            if result.get("status") == "error":
                run.status = "failed"
                run.error = result.get("message", "Step failed")
                break
        else:
            run.status = "completed"

        run.step_results = step_results
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run)
        return run

    except Exception as e:
        run.status = "failed"
        run.error = str(e)
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run)
        logger.error(f"Workflow execution failed: {e}")
        return run


async def get_workflow_runs(
    db: AsyncSession, workflow_id: str
) -> list[WorkflowRun]:
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.desc())
    )
    return list(result.scalars().all())
