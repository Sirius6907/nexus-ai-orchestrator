"""
Auth Routes — Registration, login, and profile endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from api.db.session import get_db
from api.models.user import User
from api.core.security import get_password_hash, verify_password
from api.core.auth import create_access_token, require_current_user

router = APIRouter()


# ─── Request / Response Models ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = "User"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    organization_id: str | None = None
    is_active: bool

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    # Check for existing user
    existing = await db.execute(
        select(User).where(User.email == req.email)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT."""
    result = await db.execute(
        select(User).where(User.email == req.email)
    )
    user = result.scalars().first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_current_user)):
    """Get the current authenticated user's profile."""
    return user
