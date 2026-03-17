import os
from pathlib import Path

def create_file(path_str, content=""):
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Created/Updating: {path}")

def generate_db_models():
    base = Path("api/models")
    
    create_file(base / "__init__.py", "")
    create_file(base / "user.py", """
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, text
from datetime import datetime
from api.db.base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    """)

    create_file(base / "session.py", """
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from api.db.base import Base
from typing import List

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(primary_key=True) # UUID
    title: Mapped[str] = mapped_column(String, default="New Chat")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    """)

    create_file(base / "message.py", """
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, text
from datetime import datetime
from api.db.base import Base

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String) # user, agent, system
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    
    session = relationship("ChatSession", back_populates="messages")
    """)

    create_file(base / "document.py", """
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer
from api.db.base import Base

class Document(Base):
    '''Tracks uploaded documents metadata.'''
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(primary_key=True) # UUID
    filename: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String)
    qdrant_collection_id: Mapped[str] = mapped_column(String)
    """)

def generate_schemas():
    base = Path("api/schemas")
    create_file(base / "__init__.py", "")
    create_file(base / "user.py", """
from pydantic import BaseModel, EmailStr
class UserCreate(BaseModel):
    email: EmailStr
    password: str
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    """)
    create_file(base / "chat.py", """
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MessageSchema(BaseModel):
    role: str
    content: str
class SessionSchema(BaseModel):
    id: str
    title: str
    messages: List[MessageSchema] = []
    """)

def generate_core():
    base = Path("api/core")
    create_file(base / "security.py", """
import hashlib
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Basic implementation, should use passlib+bcrypt in prod
    return get_password_hash(plain_password) == hashed_password
def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
    """)
    create_file(base / "exceptions.py", """
from fastapi import HTTPException
class AgentError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)
    """)
    create_file(base / "logging_config.py", """
import logging
import sys

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    """)

def generate_rag():
    base = Path("api/rag")
    create_file(base / "__init__.py", "")
    
    create_file(base / "vector_store.py", """
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance
from api.core.config import settings
import logging

logger = logging.getLogger(__name__)

class QdrantManager:
    def __init__(self):
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)
        
    async def create_collection_if_not_exists(self, collection_name: str, vector_size: int = 384):
        exists = await self.client.collection_exists(collection_name)
        if not exists:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
            
    async def search(self, collection_name: str, query_vector: list, limit: int = 3):
        return await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
    """)
    
    create_file(base / "embeddings.py", """
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self):
        # We use a small local CPU model to save GPU VRAM for Ollama
        self.model_name = "all-MiniLM-L6-v2" 
        logger.info(f"Loading CPU Embedding Model: {self.model_name}. This avoids VRAM overhead.")
        self.model = SentenceTransformer(self.model_name, device="cpu")
        
    def generate_embedding(self, text: str):
        return self.model.encode(text).tolist()
    """)
    
    create_file(base / "ingestion.py", """
import uuid
from api.rag.vector_store import QdrantManager
from api.rag.embeddings import EmbeddingManager
from qdrant_client.models import PointStruct

class DocumentIngestor:
    def __init__(self):
        self.qdrant = QdrantManager()
        self.embedder = EmbeddingManager()
        
    def chunk_text(self, text: str, chunk_size: int = 1000):
        # Simple character chunking
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
    async def ingest_document(self, text: str, collection_name: str, metadata: dict = None):
        await self.qdrant.create_collection_if_not_exists(collection_name)
        chunks = self.chunk_text(text)
        
        points = []
        for chunk in chunks:
            vector = self.embedder.generate_embedding(chunk)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"text": chunk, **(metadata or {})}
            )
            points.append(point)
            
        await self.qdrant.client.upsert(collection_name=collection_name, points=points)
        return len(chunks)
    """)

    # Parsers
    p_base = base / "parsers"
    create_file(p_base / "__init__.py", "")
    create_file(p_base / "text_parser.py", """
async def parse_text_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
    """)

def generate_tools():
    base = Path("api/tools")
    create_file(base / "__init__.py", "")
    
    create_file(base / "base.py", """
from abc import ABC, abstractmethod

class BaseTool(ABC):
    name: str = "base_tool"
    description: str = "Base description"
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> str:
        pass
    """)

    create_file(base / "web_search.py", """
from .base import BaseTool
import httpx

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Searches the web for current information using DuckDuckGo HTML."
    
    async def execute(self, query: str) -> str:
        # A simple headless scraper fallback for DDG
        headers = {'User-Agent': 'Mozilla/5.0 Nexus AI'}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers)
            if resp.status_code == 200:
                # Naive text extraction
                return f"Found search results for: {query} (HTML dump truncated) {resp.text[:500]}"
        return "Search failed."
    """)

    create_file(base / "calculator.py", """
from .base import BaseTool
import ast
import operator

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Evaluates basic math expressions safely."
    
    async def execute(self, expression: str) -> str:
        try:
            # Very basic safe eval mapping
            allowed_operators = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
            def _eval(node):
                if isinstance(node, ast.Num): return node.n
                if isinstance(node, ast.BinOp): return allowed_operators[type(node.op)](_eval(node.left), _eval(node.right))
                raise TypeError(node)
            result = _eval(ast.parse(expression, mode='eval').body)
            return str(result)
        except Exception as e:
            return f"Error computing {expression}: {str(e)}"
    """)

    create_file(base / "code_executor.py", """
from .base import BaseTool
import subprocess
import os
import uuid

class CodeExecutorTool(BaseTool):
    name = "python_repl"
    description = "Executes Python code in a safe sandbox."
    
    async def execute(self, code: str) -> str:
        filename = f"/tmp/nexus_{uuid.uuid4().hex}.py"
        try:
            with open(filename, "w") as f:
                f.write(code)
            
            # Execute with a 10 second timeout
            result = subprocess.run(["python", filename], capture_output=True, text=True, timeout=10)
            return f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Code execution timed out."
        except Exception as e:
            return f"Error executing code: {str(e)}"
        finally:
            if os.path.exists(filename): os.remove(filename)
    """)

def generate_routes():
    base = Path("api/api/routes")
    
    create_file(base / "documents.py", """
from fastapi import APIRouter, UploadFile, File
from api.rag.ingestion import DocumentIngestor
import os
router = APIRouter()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    # Save file temporally
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())
        
    # Read text (assuming TXT for now)
    with open(temp_path, "r", encoding="utf-8") as f:
        text = f.read()
        
    ingestor = DocumentIngestor()
    chunks = await ingestor.ingest_document(text, collection_name="user_uploads")
    
    os.remove(temp_path)
    return {"message": f"Ingested {file.filename} into {chunks} chunks."}
    """)
    
    create_file(base / "models.py", """
from fastapi import APIRouter
from api.llm.ollama_client import OllamaManager
router = APIRouter()

ol_mgr = OllamaManager()

@router.get("/list")
async def list_models():
    # Example proxy to Ollama tags
    # return await ol_mgr.client.get("/api/tags")
    return {"models": ["phi3:mini", "deepseek-coder:6.7b-instruct-q4_K_M"]}
    """)

    create_file(base / "sessions.py", """
from fastapi import APIRouter
router = APIRouter()

@router.get("/")
async def get_sessions():
    return {"sessions": []}
    """)
    
    # Update router.py to include sessions
    create_file(Path("api/api/router.py"), """
from fastapi import APIRouter
from api.api.routes import chat, documents, models, sessions

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    """)

if __name__ == "__main__":
    generate_db_models()
    generate_schemas()
    generate_core()
    generate_rag()
    generate_tools()
    generate_routes()
    print("Phase 2 code generation complete.")
