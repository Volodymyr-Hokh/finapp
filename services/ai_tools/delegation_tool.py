"""
Delegation tool for the main agent to delegate to sub-agents.
"""
from typing import Annotated, Callable

from services.ai_tools import ai_tool, ToolParam, AgentContext


def create_delegation_tool(agent_names: list[str]) -> Callable:
    """
    Create a delegation tool with dynamic agent enum.

    Args:
        agent_names: List of valid agent names from the registry
    """
    @ai_tool
    async def delegate_to_agent(
        ctx: AgentContext,
        agent_name: Annotated[str, ToolParam(
            "Name of the agent to delegate to",
            enum=agent_names
        )],
        task: Annotated[str, ToolParam("The task or question to pass to the agent")]
    ) -> dict:
        """
        Delegate a task to a specialized agent. Use this when the user's request
        matches a specific agent's domain.
        """
        return {
            "delegation_requested": True,
            "agent_name": agent_name,
            "task": task
        }

    return delegate_to_agent
