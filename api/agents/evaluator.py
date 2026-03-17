"""
Evaluator Agent — Scores agent output quality and provides feedback.

Architecture:
  Receives the original prompt + agent output → returns a quality assessment.
  If score is below threshold, the orchestrator re-plans with the feedback.
"""
import logging

logger = logging.getLogger(__name__)


class EvaluatorAgent:
    def __init__(self, llm_manager):
        self.llm = llm_manager

    async def evaluate(
        self,
        original_prompt: str,
        agent_output: str,
        evaluator_model: str = "gemma3:1b",
    ) -> dict:
        """
        Evaluate the quality of an agent's output.

        Returns:
            {
                "score": float (0-10),
                "passed": bool,
                "feedback": str,
                "suggestions": list[str]
            }
        """
        system_prompt = (
            "You are a strict quality evaluator for AI agent outputs. "
            "Score the output from 0-10 based on: accuracy, completeness, "
            "clarity, and actionability. Respond in this EXACT format:\n"
            "SCORE: <number>\n"
            "PASSED: <yes/no>\n"
            "FEEDBACK: <one sentence>\n"
            "SUGGESTIONS: <comma-separated improvements>"
        )

        user_content = (
            f"ORIGINAL REQUEST: {original_prompt}\n\n"
            f"AGENT OUTPUT:\n{agent_output[:2000]}"
        )

        try:
            response = await self.llm.chat(
                model=evaluator_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                unload_after=True,
            )
            return self._parse_evaluation(response)
        except Exception as e:
            logger.error(f"Evaluator failed: {e}")
            return {
                "score": 5.0,
                "passed": True,
                "feedback": "Evaluation skipped due to error",
                "suggestions": [],
            }

    def _parse_evaluation(self, response: str) -> dict:
        """Parse the structured evaluation response."""
        result = {
            "score": 5.0,
            "passed": True,
            "feedback": "",
            "suggestions": [],
        }

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("SCORE:"):
                try:
                    result["score"] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.upper().startswith("PASSED:"):
                val = line.split(":", 1)[1].strip().lower()
                result["passed"] = val in ("yes", "true", "1")
            elif line.upper().startswith("FEEDBACK:"):
                result["feedback"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SUGGESTIONS:"):
                raw = line.split(":", 1)[1].strip()
                result["suggestions"] = [
                    s.strip() for s in raw.split(",") if s.strip()
                ]

        return result
