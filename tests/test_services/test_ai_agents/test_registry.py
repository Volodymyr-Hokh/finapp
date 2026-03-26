"""
Tests for AgentRegistry.
"""
import pytest
from unittest.mock import AsyncMock

from services.ai_agents.registry import AgentRegistry, get_agent_registry
from services.ai_agents.account_agent import AccountAgent
from services.ai_agents.transaction_agent import TransactionAgent


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    client = AsyncMock()
    return client


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_get_returns_agent_by_name(self, mock_openai_client):
        """Test getting agent by name."""
        registry = AgentRegistry(mock_openai_client)

        agent = registry.get("account_agent")

        assert agent is not None
        assert isinstance(agent, AccountAgent)
        assert agent.name == "account_agent"

    def test_get_returns_none_for_unknown_agent(self, mock_openai_client):
        """Test returns None for unknown agent name."""
        registry = AgentRegistry(mock_openai_client)

        agent = registry.get("unknown_agent")

        assert agent is None

    def test_get_caches_instances(self, mock_openai_client):
        """Test that agent instances are cached."""
        registry = AgentRegistry(mock_openai_client)

        agent1 = registry.get("account_agent")
        agent2 = registry.get("account_agent")

        assert agent1 is agent2

    def test_get_all_names(self, mock_openai_client):
        """Test getting all agent names."""
        registry = AgentRegistry(mock_openai_client)

        names = registry.get_all_names()

        assert "account_agent" in names
        assert "transaction_agent" in names
        assert "budget_agent" in names
        assert "analytics_agent" in names
        assert "category_agent" in names
        assert len(names) == 5

    def test_get_agent_info(self, mock_openai_client):
        """Test getting info about all agents."""
        registry = AgentRegistry(mock_openai_client)

        info = registry.get_agent_info()

        assert len(info) == 5
        for agent_info in info:
            assert "name" in agent_info
            assert "description" in agent_info

    def test_get_agent_info_contains_descriptions(self, mock_openai_client):
        """Test that agent info contains useful descriptions."""
        registry = AgentRegistry(mock_openai_client)

        info = registry.get_agent_info()
        info_dict = {i["name"]: i["description"] for i in info}

        assert "account" in info_dict["account_agent"].lower()
        assert "transaction" in info_dict["transaction_agent"].lower()
        assert "budget" in info_dict["budget_agent"].lower()


class TestGetAgentRegistry:
    """Tests for get_agent_registry helper."""

    def test_creates_registry(self, mock_openai_client):
        """Test creating registry with helper."""
        # Reset global registry for test
        import services.ai_agents.registry as registry_module
        registry_module._default_registry = None

        registry = get_agent_registry(mock_openai_client)

        assert registry is not None
        assert isinstance(registry, AgentRegistry)

    def test_returns_same_instance(self, mock_openai_client):
        """Test that helper returns same instance."""
        # Reset global registry
        import services.ai_agents.registry as registry_module
        registry_module._default_registry = None

        registry1 = get_agent_registry(mock_openai_client)
        registry2 = get_agent_registry(mock_openai_client)

        assert registry1 is registry2
