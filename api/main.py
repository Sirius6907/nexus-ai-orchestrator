"""
Nexus AI — FastAPI Application Entry Point

Startup lifecycle:
  1. Configure structured logging
  2. Create all DB tables (auto-migration)
  3. Register middleware stack
  4. Register API router
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.api.router import api_router
from api.core.config import settings
from api.core.logging_config import setup_logging
from api.core.middleware import TimingMiddleware, RequestIdMiddleware, RateLimitMiddleware
from api.db.base import Base
from api.db.session import engine

# Force model imports so SQLAlchemy sees them during create_all
from api.models.session import ChatSession  # noqa: F401
from api.models.message import Message  # noqa: F401
from api.models.user import User  # noqa: F401
from api.models.api_key import ApiKey  # noqa: F401
from api.models.workflow import Workflow, WorkflowRun  # noqa: F401

# Configure structured logging
setup_logging(level="INFO", json_format=False)  # Set json_format=True for prod
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle handler."""
    # ── Startup ──
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Ensure Default Guest User exists
    from api.models.user import User
    from api.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.id == 1))
        if not result.scalars().first():
            logger.info("Seeding default 'Nexus Guest' user...")
            from api.core.security import get_password_hash
            guest = User(
                id=1,
                email="guest@nexus.ai",
                hashed_password=get_password_hash("guest"),
                display_name="Nexus Guest",
                role="admin"
            )
            session.add(guest)
            await session.commit()
            logger.info("Default user seeded successfully.")
            
    logger.info("Database tables and seeds ready.")
    logger.info(f"Nexus AI platform started — {settings.PROJECT_NAME}")

    yield  # App runs here

    # ── Shutdown ──
    logger.info("Disposing database engine...")
    await engine.dispose()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# ── OpenTelemetry Instrumentation ──
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry instrumentation enabled via FastAPIInstrumentor.")
except ImportError:
    logger.info("opentelemetry-instrumentation-fastapi not found. Skipping OTEL.")
# ── Middleware Stack (order matters: outermost first) ──
app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(TimingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "platform": "Nexus AI Enterprise", "vram_target": "4GB"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
