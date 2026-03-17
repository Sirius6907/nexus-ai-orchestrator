"""
OllamaManager — Production-grade Ollama client with VRAM management.

Features:
  - Non-streaming chat (for agents that need complete responses)
  - Streaming chat (yields tokens for real-time WS streaming)
  - VRAM-aware model unloading
  - Model name sanitization
"""
import httpx
import json
import logging
from typing import AsyncGenerator, Optional

from api.core.config import settings

logger = logging.getLogger(__name__)


class OllamaManager:
    """Manages Ollama interactions with strict VRAM controls."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.active_model: Optional[str] = None
        self.client = httpx.AsyncClient(
            base_url=self.base_url, timeout=120.0
        )

    async def chat(
        self,
        model: str,
        messages: list,
        unload_after: bool = False,
    ) -> str:
        """
        Non-streaming chat — returns the complete response as a string.
        Used by agents that need the full plan before continuing.
        """
        model = model.strip()  # Sanitize whitespace from frontend

        if self.active_model and self.active_model != model:
            await self._unload_model(self.active_model)

        self.active_model = model

        logger.info(f"Ollama chat request: model={repr(model)}")
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": 4096},
        }

        response = await self.client.post("/api/chat", json=payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {response.text}")
            raise e

        if unload_after:
            await self._unload_model(model)
            self.active_model = None

        data = response.json()
        return data["message"]["content"]

    async def chat_stream(
        self,
        model: str,
        messages: list,
        unload_after: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat — yields tokens as they arrive from Ollama.
        Used for real-time WebSocket streaming to the frontend.
        """
        model = model.strip()

        if self.active_model and self.active_model != model:
            await self._unload_model(self.active_model)

        self.active_model = model

        logger.info(f"Ollama stream request: model={repr(model)}")
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"num_ctx": 4096},
        }

        async with self.client.stream(
            "POST", "/api/chat", json=payload
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get("done"):
                        break
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                except json.JSONDecodeError:
                    continue

        if unload_after:
            await self._unload_model(model)
            self.active_model = None

    async def _unload_model(self, model: str):
        """Unload a model from VRAM by setting keep_alive to 0."""
        logger.info(f"Unloading model {model} from VRAM...")
        payload = {"model": model, "keep_alive": 0}
        try:
            await self.client.post("/api/generate", json=payload)
        except Exception as e:
            logger.warning(f"Failed to unload {model}: {e}")
