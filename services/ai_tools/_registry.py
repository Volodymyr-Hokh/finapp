"""Tool registry for managing and executing AI tools."""
import json
from typing import Any

from ._types import AgentContext, ToolDefinition


class ToolRegistry:
    """Registry for AI tools with schema generation and execution."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[ToolDefinition]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict]:
        """Get OpenAI-compatible schemas for all tools."""
        return [tool.schema for tool in self._tools.values()]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: AgentContext
    ) -> str:
        """Execute a tool by name with given arguments and context."""
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = await tool.func(context, **arguments)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})


# Global registry for tools
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _global_registry
