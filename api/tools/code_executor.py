"""
Code Executor Tool — Runs Python code in a sandboxed subprocess.
"""
import subprocess
import tempfile
import os
import logging
from api.tools.base import BaseTool

logger = logging.getLogger(__name__)

# Safety limits
MAX_EXECUTION_TIME = 10  # seconds
MAX_OUTPUT_LENGTH = 5000  # characters


class CodeExecutorTool(BaseTool):
    name: str = "code_executor"
    description: str = "Execute Python code safely. Input: Python code string."

    async def execute(self, code: str, **kwargs) -> str:
        """Run Python code in a sandboxed subprocess."""
        # Strip markdown code fences if present
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].strip()
        if code.startswith("```"):
            code = code[3:].strip()
        if code.endswith("```"):
            code = code[:-3].strip()

        # Write to temp file and execute
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=tempfile.gettempdir(),
            )

            stdout = result.stdout[:MAX_OUTPUT_LENGTH] if result.stdout else ""
            stderr = result.stderr[:MAX_OUTPUT_LENGTH] if result.stderr else ""

            output = ""
            if stdout:
                output += f"Output:\n{stdout}"
            if stderr:
                output += f"\nErrors:\n{stderr}"
            if not output:
                output = "Code executed successfully (no output)"

            return output.strip()

        except subprocess.TimeoutExpired:
            return f"Error: Code execution exceeded {MAX_EXECUTION_TIME}s timeout"
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return f"Execution error: {str(e)}"
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
