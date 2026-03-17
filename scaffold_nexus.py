import os
from pathlib import Path

def create_file(path_str, content=""):
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Created: {path}")

def scaffold_backend():
    base = Path("api")
    
    # 1. Core configs
    create_file(base / "core" / "config.py", """
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexus AI Platform"
    POSTGRES_URI: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nexus"
    REDIS_URI: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # 4GB VRAM specific settings
    MAX_VRAM_MODELS_LOADED: int = 1
    PLANNER_MODEL: str = "phi3:mini"
    CODER_MODEL: str = "deepseek-coder:6.7b-instruct-q4_K_M"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
    """)
    
    create_file(base / "core" / "security.py", "# JWT and Auth logic")
    create_file(base / "core" / "exceptions.py", "# Custom Exceptions")
    
    # 2. Database
    create_file(base / "db" / "session.py", """
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from api.core.config import settings

engine = create_async_engine(settings.POSTGRES_URI, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
    """)
    create_file(base / "db" / "base.py", """
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass
    """)
    create_file(base / "models" / "user.py", "# User SQLAlchemy Model")
    create_file(base / "models" / "session.py", "# Chat Session Model")
    create_file(base / "schemas" / "agent.py", "# Agent Pydantic Schemas")
    create_file(base / "schemas" / "chat.py", "# Chat Request/Response Schemas")

    # 3. Agents Core (VRAM Aware)
    create_file(base / "agents" / "orchestrator.py", """
import asyncio
from api.agents.planner import PlannerAgent
from api.agents.researcher import ResearchAgent
from api.agents.coder import CodingAgent
from api.core.config import settings
from api.llm.ollama_client import OllamaManager

class AgentOrchestrator:
    def __init__(self):
        self.llm_manager = OllamaManager()
        self.planner = PlannerAgent(self.llm_manager)
        self.researcher = ResearchAgent(self.llm_manager)
        self.coder = CodingAgent(self.llm_manager)

    async def run_task(self, prompt: str):
        # 1. Break down task with the small reasoning model
        plan = await self.planner.generate_plan(prompt)
        
        # 2. Determine execution route based on plan
        # TODO: Implement dynamic routing, web search, and coding tasks.
        return {"status": "success", "plan": plan}
    """)
    
    create_file(base / "agents" / "planner.py", """
class PlannerAgent:
    def __init__(self, llm_manager):
        self.llm = llm_manager

    async def generate_plan(self, prompt: str):
        # Uses lightweight model like phi3
        system_prompt = "You are a master planner. Break down the user prompt into 3-5 distinct steps."
        response = await self.llm.chat(model="phi3:mini", messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ], unload_after=True) # Critical for 4GB VRAM
        return response
    """)
    create_file(base / "agents" / "researcher.py", "# Researcher Agent Logic")
    create_file(base / "agents" / "coder.py", "# Coding Agent Logic")
    
    # 4. LLM Management
    create_file(base / "llm" / "ollama_client.py", """
import httpx
from api.core.config import settings
import logging

logger = logging.getLogger(__name__)

class OllamaManager:
    \"\"\"Manages Ollama interactions with strict VRAM controls.\"\"\"
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.active_model = None
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def chat(self, model: str, messages: list, unload_after: bool = False):
        if self.active_model and self.active_model != model:
            await self._unload_model(self.active_model)
            
        self.active_model = model
        
        payload = {"model": model, "messages": messages, "stream": False, "options": {"num_ctx": 4096}}
        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        
        if unload_after:
            await self._unload_model(model)
            self.active_model = None
            
        return response.json()["message"]["content"]

    async def _unload_model(self, model: str):
        logger.info(f"Unloading model {model} from VRAM...")
        # Ollama unloads a model if keep_alive is 0
        payload = {"model": model, "keep_alive": 0}
        await self.client.post("/api/generate", json=payload)
    """)

    # 5. RAG Pipeline
    create_file(base / "rag" / "vector_store.py", "# Qdrant interactions")
    create_file(base / "rag" / "embeddings.py", "# Embedding generation (using CPU to save VRAM)")
    create_file(base / "rag" / "ingestion.py", "# Document chunking and insertion")
    
    # 6. API Routers
    create_file(base / "api" / "routes" / "chat.py", """
from fastapi import APIRouter, WebSocket
router = APIRouter()

@router.websocket("/ws")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        # Mock response for now
        await websocket.send_text(f"Agent Processing: {data}")
    """)
    create_file(base / "api" / "routes" / "documents.py", "# Document Upload router")
    create_file(base / "api" / "routes" / "models.py", "# Model management (pull/unload)")
    
    create_file(base / "api" / "router.py", """
from fastapi import APIRouter
from api.api.routes import chat, documents, models

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
    """)

    # 7. Main FastAPI Entrypoint
    create_file(base / "main.py", """
from fastapi import FastAPI
from api.api.router import api_router
from api.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "ok", "vram_target": "4GB"}
    """)
    
    # 8. Requirements
    create_file("requirements.txt", """
fastapi==0.110.1
uvicorn[standard]==0.29.0
sqlalchemy==2.0.29
asyncpg==0.29.0
qdrant-client==1.8.0
redis==5.0.3
pydantic-settings==2.2.1
httpx==0.27.0
python-dotenv==1.0.1
    """)

def scaffold_infrastructure():
    create_file("docker-compose.yml", """
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: nexus
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
  qdrant_data:
    """)
    create_file(".env.example", """
POSTGRES_URI=postgresql+asyncpg://postgres:postgres@localhost:5432/nexus
REDIS_URI=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
OLLAMA_BASE_URL=http://localhost:11434
    """)
    create_file("README.md", """
# Nexus AI - VRAM Optimized Agent Platform
Fully localized, multi-agent AI framework designed specifically for 4GB VRAM hardware.
    """)

if __name__ == "__main__":
    print("Scaffolding Nexus AI Project Architecture...")
    scaffold_backend()
    scaffold_infrastructure()
    # Note: Frontend (Next.js) is best generated via create-next-app natively.
    print("Done generating base architecture files.")
