"""
Tool Router — Parses agent output for tool invocation directives and routes
to the appropriate BaseTool implementation.

Supported directive format in agent output:
  [TOOL:tool_name] arguments
"""
import logging
from typing import Optional

from api.tools.base import BaseTool
from api.tools.registry import plugin_registry

logger = logging.getLogger(__name__)


class ToolRouter:
    """Routes tool calls from agent outputs to the correct tool implementation."""

    def __init__(self):
        # Tools are now managed by the registry, but we can keep a reference 
        # or just point to it directly. For compatibility, we'll map to it.
        pass

    @property
    def tools(self) -> dict[str, BaseTool]:
        return plugin_registry.get_all_tools()

    def _register_default_tools(self):
        pass # Handle by PluginRegistry.discover() now

    def register_tool(self, tool: BaseTool):
        """Register a custom tool at runtime."""
        plugin_registry.register(tool)

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for the agent system prompt."""
        lines = ["Available tools:"]
        for name, tool in self.tools.items():
            lines.append(f"  [TOOL:{name}] — {tool.description}")
        return "\n".join(lines)

    async def route(self, agent_output: str) -> Optional[dict]:
        """
        Parse agent output for tool directives and execute the first one found.

        Returns:
            {
                "tool_name": str,
                "tool_input": str,
                "tool_output": str,
            }
            or None if no tool directive found.
        """
        import re

        # Look for [TOOL:name] pattern
        match = re.search(r"\[TOOL:(\w+)\]\s*(.*)", agent_output, re.DOTALL)
        if not match:
            return None

        tool_name = match.group(1).lower()
        tool_input = match.group(2).strip()

        if tool_name not in self.tools:
            logger.warning(f"Unknown tool requested: {tool_name}")
            return {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": f"Error: tool '{tool_name}' not found. "
                f"Available tools: {list(self.tools.keys())}",
            }

        try:
            logger.info(f"Executing tool: {tool_name}")
            result = await self.tools[tool_name].execute(tool_input)
            return {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": result,
            }
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": f"Error executing {tool_name}: {str(e)}",
            }
