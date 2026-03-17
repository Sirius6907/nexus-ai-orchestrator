"""
Workflow Routes — REST API for workflow management and execution.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import get_db
from api.services import workflow_service

router = APIRouter()


# ─── Request / Response Models ───────────────────────────────────────────────

class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    dag_json: dict = {"steps": []}
    trigger_type: str = "manual"
    schedule: str | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    dag_json: dict
    trigger_type: str
    schedule: str | None
    is_active: bool

    class Config:
        from_attributes = True


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    step_results: dict
    error: str | None

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[WorkflowResponse])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    """List all workflows."""
    workflows = await workflow_service.list_workflows(db)
    return workflows


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(
    req: WorkflowCreateRequest, db: AsyncSession = Depends(get_db)
):
    """Create a new workflow."""
    wf = await workflow_service.create_workflow(
        db=db,
        name=req.name,
        description=req.description,
        dag_json=req.dag_json,
        trigger_type=req.trigger_type,
        schedule=req.schedule,
    )
    return wf


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str, db: AsyncSession = Depends(get_db)
):
    """Get a specific workflow."""
    wf = await workflow_service.get_workflow(db, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str, db: AsyncSession = Depends(get_db)
):
    """Delete a workflow and its run history."""
    await workflow_service.delete_workflow(db, workflow_id)
    return {"status": "deleted"}


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    workflow_id: str, db: AsyncSession = Depends(get_db)
):
    """Trigger a workflow execution."""
    try:
        run = await workflow_service.execute_workflow(db, workflow_id)
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunResponse])
async def get_workflow_runs(
    workflow_id: str, db: AsyncSession = Depends(get_db)
):
    """Get execution history for a workflow."""
    return await workflow_service.get_workflow_runs(db, workflow_id)
