from fastapi import APIRouter
from api.api.routes import analytics, auth, chat, documents, models, sessions, workflows, api_keys, memory

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api_keys"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
