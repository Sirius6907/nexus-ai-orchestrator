"""
Planner Agent — Fast task decomposition using lightweight models.
"""


class PlannerAgent:
    def __init__(self, llm_manager):
        self.llm = llm_manager

    async def generate_plan(self, prompt: str, planner_model: str = "gemma3:1b"):
        """Break down a user prompt into actionable steps using a fast model."""
        system_prompt = (
            "You are a master planner AI. Break down the user's request into "
            "3-5 distinct, actionable steps. Be concise and precise."
        )
        response = await self.llm.chat(
            model=planner_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            unload_after=True,  # Critical for 4GB VRAM
        )
        return response
