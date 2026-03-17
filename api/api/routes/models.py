from fastapi import APIRouter, HTTPException
import httpx
import logging
from api.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/list")
async def list_models():
    """Fetches the live list of models physically downloaded to the user's Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            # Extract just the model names from the Ollama response
            model_names = [model.get("name") for model in data.get("models", [])]
            return {"models": model_names}
    except Exception as e:
        logger.error(f"Failed to fetch live Ollama models: {e}")
        # Fallback to defaults if Ollama is unreachable
        return {"models": ["phi3:mini", "deepseek-coder:6.7b-instruct-q4_K_M", "gemma3:1b", "qwen:0.5b"], "error": str(e)}

