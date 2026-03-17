"""
Inference Router — Gateway to isolate API from specific LLM providers.
Supports routing to Ollama, vLLM, or OpenRouter based on model tags.
"""
import os
import json
import httpx
import logging
from typing import List, Dict, Any, AsyncGenerator

from api.core.config import settings

logger = logging.getLogger(__name__)


class InferenceRouter:
    """Routes LLM requests to the correct inference backend based on model name."""

    def __init__(self):
        self.ollama_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.vllm_url = os.getenv("VLLM_BASE_URL", "")

        logger.info(f"Initialized InferenceRouter (Ollama: {self.ollama_url})")

    def _determine_provider(self, model_name: str) -> str:
        """Simple routing logic based on prefix/tags."""
        if model_name.startswith("openrouter/"):
            return "openrouter"
        if model_name.startswith("vllm/"):
            return "vllm"
        # Default to local Ollama
        return "ollama"

    async def generate_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> Any:
        """
        Unified interface for chat completion.
        Returns an AsyncGenerator if stream=True, else a dict with 'message' and 'usage'.
        """
        provider = self._determine_provider(model)

        if provider == "openrouter":
            return await self._generate_openrouter(
                model.replace("openrouter/", ""), messages, temperature, max_tokens, stream
            )
        elif provider == "vllm":
            return await self._generate_vllm(
                model.replace("vllm/", ""), messages, temperature, max_tokens, stream
            )
        else:
            return await self._generate_ollama(model, messages, temperature, stream)

    async def _generate_ollama(
        self, model: str, messages: List[Dict[str, str]], temperature: float, stream: bool
    ):
        """Standard Ollama implementation."""
        payload = {
            "model": model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": stream,
        }
        
        timeout = httpx.Timeout(120.0, connect=10.0)
        
        if not stream:
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.post(
                        f"{self.ollama_url}/api/chat", json=payload
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Normalize output format
                    return {
                        "message": data.get("message", {}),
                        "usage": {
                            "prompt_tokens": data.get("prompt_eval_count", 0),
                            "completion_tokens": data.get("eval_count", 0),
                            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                        }
                    }
                except Exception as e:
                    logger.error(f"Ollama generation failed: {e}")
                    raise

        # Streaming generator
        async def ollama_stream() -> AsyncGenerator[str, None]:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.ollama_url}/api/chat", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse stream line: {line}")
                            continue

        return ollama_stream()

    async def _generate_openrouter(
        self, model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int, stream: bool
    ):
        """OpenRouter implementation (OpenAI API format)."""
        if not self.openrouter_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
            
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "http://localhost:3000", # Required by OpenRouter
            "X-Title": "Nexus AI",
        }
        
        timeout = httpx.Timeout(60.0, connect=10.0)
        
        if not stream:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                # Normalize output format to match Ollama's structure for orchestrator compatibility
                return {
                    "message": {
                        "role": data["choices"][0]["message"]["role"],
                        "content": data["choices"][0]["message"]["content"],
                    },
                    "usage": data.get("usage", {})
                }
                
        # Streaming generator
        async def openrouter_stream() -> AsyncGenerator[str, None]:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", "https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                            
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue

        return openrouter_stream()
        
    async def _generate_vllm(
        self, model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int, stream: bool
    ):
        """vLLM implementation (usually OpenAI compatible endpoint)."""
        if not self.vllm_url:
            raise ValueError("VLLM_BASE_URL environment variable not set")
            
        # Implementation identical to OpenRouter but pointing to vLLM URL and without special headers
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        headers = {"Content-Type": "application/json"}
        timeout = httpx.Timeout(60.0, connect=10.0)
        
        if not stream:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.vllm_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "message": {
                        "role": data["choices"][0]["message"]["role"],
                        "content": data["choices"][0]["message"]["content"],
                    },
                    "usage": data.get("usage", {})
                }
                
        # Streaming generator
        async def vllm_stream() -> AsyncGenerator[str, None]:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.vllm_url}/v1/chat/completions", json=payload, headers=headers
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, IndexError, KeyError):
                            continue

        return vllm_stream()

# Initialize global router
inference_router = InferenceRouter()
