"""
Coder Agent — Code generation with optional multi-modal (image) support.
"""
from api.llm.ollama_client import OllamaManager


class CodingAgent:
    def __init__(self, llm_manager: OllamaManager):
        self.llm_manager = llm_manager

    async def write_code(
        self,
        instructions: str,
        coder_model: str = "gemma3:1b",
        image_base64: str | None = None,
    ):
        """Generate code based on instructions + optional UI screenshot."""
        system_prompt = (
            "You are an expert AI software engineer. Write clean, "
            "production-ready code based on the user's instructions. "
            "If an image is provided, it is a UI mockup to implement."
        )

        user_msg = {"role": "user", "content": instructions}
        if image_base64:
            user_msg["images"] = [image_base64]

        messages = [
            {"role": "system", "content": system_prompt},
            user_msg,
        ]

        response = await self.llm_manager.chat(
            model=coder_model,
            messages=messages,
            unload_after=False,
        )
        return response
