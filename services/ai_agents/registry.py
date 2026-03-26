"""
Agent Registry - provides lookup and instantiation of agents by name.
"""
from typing import Optional, Type
from openai import AsyncOpenAI

from services.ai_agents.base_agent import BaseAgent
from services.ai_agents.account_agent import AccountAgent
from services.ai_agents.transaction_agent import TransactionAgent
from services.ai_agents.budget_agent import BudgetAgent
from services.ai_agents.analytics_agent import AnalyticsAgent
from services.ai_agents.category_agent import CategoryAgent


class AgentRegistry:
    """
    Registry for looking up and instantiating agents by name.

    Usage:
        registry = AgentRegistry(openai_client)
        agent = registry.get("transaction_agent")
        info = registry.get_agent_info()
    """

    # Map of agent names to their classes
    _agent_classes: dict[str, Type[BaseAgent]] = {
        "account_agent": AccountAgent,
        "transaction_agent": TransactionAgent,
        "budget_agent": BudgetAgent,
        "analytics_agent": AnalyticsAgent,
        "category_agent": CategoryAgent,
    }

    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self._instances: dict[str, BaseAgent] = {}

    def get(self, name: str) -> Optional[BaseAgent]:
        """
        Get an agent instance by name.

        Instances are cached for reuse within the same registry.
        """
        if name in self._instances:
            return self._instances[name]

        agent_class = self._agent_classes.get(name)
        if not agent_class:
            return None

        instance = agent_class(self.client)
        self._instances[name] = instance
        return instance

    def get_all_names(self) -> list[str]:
        """Get list of all registered agent names."""
        return list(self._agent_classes.keys())

    def get_agent_info(self) -> list[dict]:
        """
        Get info about all available agents.

        Useful for the main agent to know what agents it can delegate to.
        """
        info = []
        for name, agent_class in self._agent_classes.items():
            # Create temporary instance to get description
            agent = self.get(name)
            if agent:
                info.append({
                    "name": name,
                    "description": agent.description
                })
        return info


# Default registry singleton (initialized lazily)
_default_registry: Optional[AgentRegistry] = None


def get_agent_registry(client: AsyncOpenAI) -> AgentRegistry:
    """Get or create the agent registry with the given client."""
    global _default_registry
    if _default_registry is None:
        _default_registry = AgentRegistry(client)
    return _default_registry
