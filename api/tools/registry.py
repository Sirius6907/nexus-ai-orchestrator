"""
Tool Plugin Registry — Discovers and loads tools dynamically at runtime.
Allows extending Nexus AI capabilities by dropping new `.py` files into the plugins directory.
"""
import os
import sys
import glob
import inspect
import importlib.util
import logging
from typing import Dict, Type, Any

from api.tools.base import BaseTool

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Dynamically loads and registers tool plugins."""

    def __init__(self, plugin_dir: str = "api/tools/plugins"):
        self.plugin_dir = plugin_dir
        self._tools: Dict[str, BaseTool] = {}
        
        # Ensure plugin directory exists
        os.makedirs(self.plugin_dir, exist_ok=True)
        # Create __init__.py if it doesn't exist
        init_file = os.path.join(self.plugin_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("")

    def discover(self):
        """Scans the plugin directory and loads all BaseTool implementations."""
        self._tools.clear()
        
        # Add basic builtin tools first (we would normally discover these too, 
        # but let's just make sure they are available if needed)
        # For a full enterprise system, ALL tools including builtins should use this registry.
        
        search_pattern = os.path.join(self.plugin_dir, "*.py")
        plugin_files = glob.glob(search_pattern)
        
        # Also let's scan the base api/tools directory for built-in tools
        builtin_pattern = os.path.join(os.path.dirname(__file__), "*.py")
        builtin_files = [f for f in glob.glob(builtin_pattern) if not f.endswith(("__init__.py", "base.py", "registry.py"))]
        
        all_files = builtin_files + plugin_files

        for file_path in all_files:
            if not os.path.isfile(file_path):
                continue

            module_name = os.path.basename(file_path)[:-3]
            # Avoid loading __init__.py or the registry/base itself
            if module_name in ("__init__", "base", "registry"):
                continue

            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # Look for classes inheriting from BaseTool
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, BaseTool)
                            and obj is not BaseTool
                        ):
                            # Instantiate tool
                            tool_instance = obj()
                            self.register(tool_instance)
            except Exception as e:
                logger.error(f"Failed to load plugin {file_path}: {e}")
                
        logger.info(f"Plugin registry loaded {len(self._tools)} tools: {list(self._tools.keys())}")

    def register(self, tool: BaseTool):
        """Register a specific tool instance."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        """Retrieve a tool by its exact name."""
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return self._tools

    def get_tools_description(self) -> str:
        """Get a formatted string describing all available tools for LLM prompts."""
        if not self._tools:
            return "No tools available."
            
        desc = "AVAILABLE TOOLS:\n"
        for name, tool in self._tools.items():
            desc += f"- {name}: {tool.description}\n"
        return desc


# Global registry instance
plugin_registry = PluginRegistry()
# Discover tools on import
plugin_registry.discover()
