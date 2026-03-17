"""
Background Worker Tasks — Document ingestion, embedding generation, and workflow execution.
"""
import asyncio
import logging

from api.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine in sync Celery worker context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ─── Document Ingestion ──────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, name="process_document")
def process_document_background(
    self, file_path: str, collection_name: str, file_type: str
):
    """Parse and ingest a document into Qdrant."""
    logger.info(f"Worker: ingesting {file_path} ({file_type})")

    try:
        text = ""
        if file_type == "pdf":
            import fitz
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text()
        elif file_type in ("txt", "md"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        elif file_type == "html":
            from bs4 import BeautifulSoup
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                text = soup.get_text(separator="\n")
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return {"status": "error", "message": f"Unsupported type: {file_type}"}

        from api.rag.ingestion import DocumentIngestor
        ingestor = DocumentIngestor()
        chunks = _run_async(ingestor.ingest_document(text, collection_name))
        logger.info(f"Successfully ingested {chunks} chunks from {file_path}")
        return {"status": "success", "chunks": chunks}
    except Exception as e:
        logger.error(f"Document ingestion failed: {str(e)}")
        self.retry(exc=e, countdown=60)


# ─── Embedding Generation ────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2, name="generate_embeddings")
def generate_embeddings_task(
    self, texts: list[str], collection_name: str, model: str = "nomic-embed-text"
):
    """Generate embeddings for text chunks and store in Qdrant."""
    logger.info(f"Worker: generating embeddings for {len(texts)} chunks")

    try:
        import httpx

        embeddings = []
        # Batch embed
        response = httpx.post(
            "http://localhost:11434/api/embed",
            json={"model": model, "input": texts},
            timeout=120.0,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings", [])

        if not embeddings:
            return {"status": "error", "message": "No embeddings generated"}

        # Store in Qdrant
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        import uuid

        client = QdrantClient(url="http://localhost:6333")

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={"text": text, "collection": collection_name},
            )
            for text, emb in zip(texts, embeddings)
        ]

        client.upsert(collection_name=collection_name, points=points)

        logger.info(f"Stored {len(points)} embeddings in {collection_name}")
        return {"status": "success", "count": len(points)}

    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}")
        self.retry(exc=e, countdown=30)


# ─── Workflow Step Execution ─────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2, name="run_workflow_step")
def run_workflow_step_task(self, workflow_id: str, step_config: dict):
    """Execute a single workflow step in the background."""
    logger.info(f"Worker: executing workflow step for {workflow_id}")

    try:
        step_type = step_config.get("type", "llm_call")

        if step_type == "llm_call":
            from api.llm.ollama_client import OllamaManager
            manager = OllamaManager()
            model = step_config.get("model", "gemma3:1b")
            prompt = step_config.get("prompt", "")
            result = _run_async(
                manager.chat(model=model, messages=[
                    {"role": "user", "content": prompt}
                ])
            )
            return {"status": "success", "output": result}

        elif step_type == "tool_call":
            from api.agents.tool_router import ToolRouter
            router = ToolRouter()
            tool_name = step_config.get("tool", "")
            tool_input = step_config.get("input", "")
            if tool_name in router.tools:
                result = _run_async(router.tools[tool_name].execute(tool_input))
                return {"status": "success", "output": result}
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

        elif step_type == "webhook":
            import httpx
            url = step_config.get("url", "")
            payload = step_config.get("payload", {})
            response = httpx.post(url, json=payload, timeout=30.0)
            return {"status": "success", "output": response.text[:1000]}

        else:
            return {"status": "error", "message": f"Unknown step type: {step_type}"}

    except Exception as e:
        logger.error(f"Workflow step failed: {str(e)}")
        self.retry(exc=e, countdown=15)
