"""
Agent Orchestrator — Enterprise multi-agent coordination with:
  - Planner → Executor → Evaluator loop
  - Tool routing from agent outputs
  - RAG-enhanced research
  - Structured agent traces for observability
"""
import time
import asyncio
import logging
from typing import Optional

from api.agents.planner import PlannerAgent
from api.agents.researcher import ResearchAgent
from api.agents.coder import CodingAgent
from api.agents.evaluator import EvaluatorAgent
from api.agents.tool_router import ToolRouter
from api.llm.ollama_client import OllamaManager
from api.services.cache_service import cache_service

logger = logging.getLogger(__name__)

MAX_EVAL_RETRIES = 1  # Max re-plan attempts after failed evaluation
EVAL_THRESHOLD = 4.0   # Minimum score to pass evaluation


class AgentOrchestrator:
    def __init__(self):
        self.llm_manager = OllamaManager()
        self.planner = PlannerAgent(self.llm_manager)
        self.researcher = ResearchAgent(self.llm_manager)
        self.coder = CodingAgent(self.llm_manager)
        self.evaluator = EvaluatorAgent(self.llm_manager)
        self.tool_router = ToolRouter()

    async def run_task(
        self,
        prompt: str,
        planner_model: str = "gemma3:1b",
        coder_model: str = "gemma3:1b",
        image_base64: str | None = None,
    ) -> dict:
        """
        Run the full agent pipeline:
          1. Plan the task
          2. Check for tool invocations
          3. Optionally run coder
          4. Evaluate output quality
          5. Re-plan if quality is below threshold
        """
        agent_trace = []
        tool_outputs = []

        # ── Step 0: Semantic Cache ──
        t_cache = time.time()
        cached_result = await cache_service.get(prompt, planner_model)
        if cached_result:
            cache_duration = int((time.time() - t_cache) * 1000)
            logger.info(f"Semantic Cache HIT in Orchestrator for {planner_model}")
            return {
                "status": "success",
                "plan": cached_result,
                "agent_trace": [{
                    "agent": "cache",
                    "model": "redis",
                    "input": prompt[:200],
                    "output": cached_result[:300],
                    "duration_ms": cache_duration,
                }],
                "model_used": "cache_hit"
            }

        # ── Step 1: Planner ──
        t0 = time.time()
        plan = await self.planner.generate_plan(
            prompt, planner_model=planner_model
        )
        planner_duration = int((time.time() - t0) * 1000)

        agent_trace.append({
            "agent": "planner",
            "model": planner_model,
            "input": prompt[:200],
            "output": plan[:300],
            "duration_ms": planner_duration,
        })
        logger.info(f"Planner completed in {planner_duration}ms")

        # ── Step 2: Parallel DAG Execution ──
        tasks = []

        # 1. Tool Router Task
        async def run_tool():
            t = time.time()
            res = await self.tool_router.route(plan)
            return ("tool", res, int((time.time() - t) * 1000))
        tasks.append(run_tool())

        # 2. Conditional Coder Task
        code_keywords = ["code", "build", "ui", "html", "css", "function", "component", "app", "page", "script", "program"]
        should_code = any(kw in prompt.lower() for kw in code_keywords) or bool(image_base64)
        
        async def run_coder():
            if not should_code: return ("coder", None, 0)
            t = time.time()
            res = await self.coder.write_code(instructions=prompt, coder_model=coder_model, image_base64=image_base64)
            return ("coder", res, int((time.time() - t) * 1000))
        tasks.append(run_coder())

        # 3. Conditional Researcher Task
        research_keywords = ["search", "find", "who", "what", "where", "when", "why", "how", "explain", "research", "lookup"]
        should_research = any(kw in prompt.lower() for kw in research_keywords)
        
        async def run_researcher():
            if not should_research: return ("research", None, 0)
            t = time.time()
            res = await self.researcher.execute_research(query=prompt, research_model=planner_model)
            return ("research", res, int((time.time() - t) * 1000))
        tasks.append(run_researcher())

        # Execute parallel
        results = await asyncio.gather(*tasks)

        code_result = None
        for task_type, res, duration in results:
            if task_type == "tool" and res:
                tool_outputs.append(res)
                agent_trace.append({
                    "agent": "tool_router",
                    "tool": res["tool_name"],
                    "input": res["tool_input"][:200],
                    "output": res["tool_output"][:300],
                    "duration_ms": duration,
                })
                logger.info(f"Tool executed: {res['tool_name']}")
            elif task_type == "coder" and res:
                code_result = res
                agent_trace.append({
                    "agent": "coder",
                    "model": coder_model,
                    "input": prompt[:200],
                    "output": (res or "")[:300],
                    "duration_ms": duration,
                })
                logger.info(f"Coder completed in {duration}ms")
            elif task_type == "research" and res:
                agent_trace.append({
                    "agent": "researcher",
                    "model": planner_model,
                    "input": prompt[:200],
                    "output": (str(res) or "")[:300],
                    "duration_ms": duration,
                })
                logger.info(f"Researcher completed in {duration}ms")
                # Append research to plan so Evaluator sees the full context
                plan += f"\n\nRESEARCH FINDINGS:\n{res}"

        # ── Step 4: Evaluator Loop ──
        primary_output = code_result or plan
        eval_attempts = 0

        while eval_attempts <= MAX_EVAL_RETRIES:
            t2 = time.time()
            evaluation = await self.evaluator.evaluate(
                original_prompt=prompt,
                agent_output=primary_output,
                evaluator_model=planner_model,
            )
            eval_duration = int((time.time() - t2) * 1000)

            agent_trace.append({
                "agent": "evaluator",
                "model": planner_model,
                "score": evaluation["score"],
                "passed": evaluation["passed"],
                "feedback": evaluation.get("feedback", ""),
                "duration_ms": eval_duration,
            })
            logger.info(
                f"Evaluator: score={evaluation['score']}, "
                f"passed={evaluation['passed']}"
            )

            if evaluation["passed"] and evaluation["score"] >= EVAL_THRESHOLD:
                break

            eval_attempts += 1
            if eval_attempts > MAX_EVAL_RETRIES:
                logger.info("Max eval retries reached, using current output")
                break

            # Re-plan with feedback
            logger.info(f"Re-planning based on evaluator feedback...")
            refined_prompt = (
                f"ORIGINAL REQUEST: {prompt}\n\n"
                f"PREVIOUS OUTPUT (scored {evaluation['score']}/10):\n"
                f"{primary_output[:500]}\n\n"
                f"EVALUATOR FEEDBACK: {evaluation.get('feedback', '')}\n"
                f"SUGGESTIONS: {', '.join(evaluation.get('suggestions', []))}\n\n"
                f"Please provide an improved response."
            )

            t3 = time.time()
            primary_output = await self.planner.generate_plan(
                refined_prompt, planner_model=planner_model
            )
            replan_duration = int((time.time() - t3) * 1000)
            agent_trace.append({
                "agent": "planner_revision",
                "model": planner_model,
                "input": "re-plan based on evaluator feedback",
                "output": primary_output[:300],
                "duration_ms": replan_duration,
            })

        # ── Build Result ──
        result = {
            "status": "success",
            "plan": primary_output,
            "agent_trace": agent_trace,
            "model_used": planner_model,
        }

        if code_result:
            result["code"] = code_result
        if tool_outputs:
            result["tool_outputs"] = tool_outputs
        if evaluation:
            result["evaluation"] = evaluation

        # ── Step 5: Cache Result ──
        # Only cache if evaluation passed or no evaluation was done
        if not evaluation or evaluation.get("passed", True):
            await cache_service.set(prompt, planner_model, primary_output)

        return result
