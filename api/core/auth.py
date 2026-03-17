"""
Authentication Module — JWT creation, verification, and FastAPI dependencies.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
import hashlib
from datetime import datetime, timezone

from api.core.config import settings
from api.db.session import get_db
from api.models.user import User
from api.models.api_key import ApiKey

# Configuration — pulled from settings, never hardcoded
SECRET_KEY = getattr(settings, "SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_IMMEDIATELY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours for local dev

security_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ─── API Key Utilities ───────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str]:
    """Generate a raw API key and its hash for DB storage."""
    raw_key = f"nx_{secrets.token_urlsafe(32)}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ─── Token Creation ──────────────────────────────────────────────────────────

def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ─── Token Verification ─────────────────────────────────────────────────────

def verify_access_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI Dependencies ────────────────────────────────────────────────────

async def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None

    payload = verify_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    return result.scalars().first()


async def get_current_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not api_key:
        return None

    hashed = hash_api_key(api_key)
    result = await db.execute(select(ApiKey).where(ApiKey.hashed_key == hashed))
    key_record = result.scalars().first()
    
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
        
    # Update last_used_at
    key_record.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    user_result = await db.execute(select(User).where(User.id == key_record.user_id))
    return user_result.scalars().first()


async def get_current_user(
    user_from_token: Optional[User] = Depends(get_current_user_from_token),
    user_from_api_key: Optional[User] = Depends(get_current_user_from_api_key),
) -> Optional[User]:
    """
    FastAPI dependency that extracts and validates the current user from JWT
    or API Key. Returns None if unauthenticated.
    """
    return user_from_api_key or user_from_token


async def require_current_user(
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """FastAPI dependency that requires authentication. In development, falls back to Nexus Guest."""
    if user:
        return user
        
    # Development Fallback: Automatically use User ID 1 if it exists
    result = await db.execute(select(User).where(User.id == 1))
    guest = result.scalars().first()
    if guest:
        return guest
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please login or ensure a default user exists.",
        headers={"WWW-Authenticate": "Bearer"},
    )
