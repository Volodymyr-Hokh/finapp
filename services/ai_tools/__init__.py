"""
AI Tool System with @ai_tool decorator for automatic OpenAI schema generation.

Usage:
    from services.ai_tools import ai_tool, ToolParam, AgentContext

    @ai_tool
    async def get_accounts(
        ctx: AgentContext,
        include_balance: Annotated[bool, ToolParam("Include balance info")] = True,
    ) -> dict:
        '''Get all user accounts.'''
        ...
"""
from ._types import AgentContext, ToolDefinition, ToolParam
from ._registry import ToolRegistry, get_global_registry
from ._decorator import ai_tool, create_registry_from_tools

__all__ = [
    # Types
    "AgentContext",
    "ToolParam",
    "ToolDefinition",
    # Registry
    "ToolRegistry",
    "get_global_registry",
    # Decorator
    "ai_tool",
    "create_registry_from_tools",
]
