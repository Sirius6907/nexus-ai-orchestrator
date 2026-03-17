"""
API Key Routes — endpoints for external developers to generate and manage keys.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional

from api.db.session import get_db
from api.core.auth import require_current_user, generate_api_key
from api.models.user import User
from api.models.api_key import ApiKey

router = APIRouter()


class ApiKeyCreateRequest(BaseModel):
    name: str


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    raw_key: str
    created_at: str

    class Config:
        from_attributes = True


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    created_at: str
    last_used_at: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/", response_model=ApiKeyCreateResponse)
async def create_api_key(
    req: ApiKeyCreateRequest,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. The raw_key is only returned once."""
    raw_key, hashed_key = generate_api_key()
    
    api_key_record = ApiKey(
        name=req.name,
        hashed_key=hashed_key,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
    )
    db.add(api_key_record)
    await db.commit()
    await db.refresh(api_key_record)
    
    return {
        "id": api_key_record.id,
        "name": api_key_record.name,
        "raw_key": raw_key,
        "created_at": str(api_key_record.created_at),
    }


@router.get("/", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the current user."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id)
    )
    keys = result.scalars().all()
    
    return [
        {
            "id": k.id,
            "name": k.name,
            "created_at": str(k.created_at),
            "last_used_at": str(k.last_used_at) if k.last_used_at else None,
        }
        for k in keys
    ]


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    result = await db.execute(
        delete(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )
        
    return {"status": "success", "message": "API Key revoked"}
