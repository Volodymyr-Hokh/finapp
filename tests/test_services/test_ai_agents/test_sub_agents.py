"""
Tests for specialized sub-agents.
"""
import pytest
from unittest.mock import AsyncMock

from services.ai_agents.account_agent import AccountAgent
from services.ai_agents.transaction_agent import TransactionAgent
from services.ai_agents.budget_agent import BudgetAgent
from services.ai_agents.analytics_agent import AnalyticsAgent
from services.ai_agents.category_agent import CategoryAgent


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    client = AsyncMock()
    client.chat = AsyncMock()
    client.chat.completions = AsyncMock()
    return client


class TestAccountAgent:
    """Tests for AccountAgent."""

    def test_has_correct_name(self, mock_openai_client):
        """Test agent has correct name."""
        agent = AccountAgent(mock_openai_client)
        assert agent.name == "account_agent"

    def test_has_description(self, mock_openai_client):
        """Test agent has description."""
        agent = AccountAgent(mock_openai_client)
        assert "account" in agent.description.lower()

    def test_has_system_prompt(self, mock_openai_client):
        """Test agent has system prompt."""
        agent = AccountAgent(mock_openai_client)
        assert len(agent.system_prompt) > 0
        assert "account" in agent.system_prompt.lower()

    def test_has_tool_registry(self, mock_openai_client):
        """Test agent has tool registry with account tools."""
        agent = AccountAgent(mock_openai_client)
        registry = agent.get_tool_registry()

        assert registry.get("get_user_accounts") is not None
        assert registry.get("get_default_account") is not None
        assert registry.get("create_account") is not None


class TestTransactionAgent:
    """Tests for TransactionAgent."""

    def test_has_correct_name(self, mock_openai_client):
        """Test agent has correct name."""
        agent = TransactionAgent(mock_openai_client)
        assert agent.name == "transaction_agent"

    def test_has_description(self, mock_openai_client):
        """Test agent has description."""
        agent = TransactionAgent(mock_openai_client)
        assert "transaction" in agent.description.lower()

    def test_has_tool_registry(self, mock_openai_client):
        """Test agent has tool registry with transaction tools."""
        agent = TransactionAgent(mock_openai_client)
        registry = agent.get_tool_registry()

        assert registry.get("get_transactions") is not None
        assert registry.get("create_transaction") is not None
        assert registry.get("delete_transaction") is not None


class TestBudgetAgent:
    """Tests for BudgetAgent."""

    def test_has_correct_name(self, mock_openai_client):
        """Test agent has correct name."""
        agent = BudgetAgent(mock_openai_client)
        assert agent.name == "budget_agent"

    def test_has_description(self, mock_openai_client):
        """Test agent has description."""
        agent = BudgetAgent(mock_openai_client)
        assert "budget" in agent.description.lower()

    def test_has_tool_registry(self, mock_openai_client):
        """Test agent has tool registry with budget tools."""
        agent = BudgetAgent(mock_openai_client)
        registry = agent.get_tool_registry()

        assert registry.get("get_budgets_with_progress") is not None
        assert registry.get("create_budget") is not None


class TestAnalyticsAgent:
    """Tests for AnalyticsAgent."""

    def test_has_correct_name(self, mock_openai_client):
        """Test agent has correct name."""
        agent = AnalyticsAgent(mock_openai_client)
        assert agent.name == "analytics_agent"

    def test_has_description(self, mock_openai_client):
        """Test agent has description."""
        agent = AnalyticsAgent(mock_openai_client)
        assert "analytics" in agent.description.lower()

    def test_has_tool_registry(self, mock_openai_client):
        """Test agent has tool registry with analytics tools."""
        agent = AnalyticsAgent(mock_openai_client)
        registry = agent.get_tool_registry()

        assert registry.get("get_spending_summary") is not None
        assert registry.get("get_category_breakdown") is not None
        assert registry.get("get_monthly_trend") is not None


class TestCategoryAgent:
    """Tests for CategoryAgent."""

    def test_has_correct_name(self, mock_openai_client):
        """Test agent has correct name."""
        agent = CategoryAgent(mock_openai_client)
        assert agent.name == "category_agent"

    def test_has_description(self, mock_openai_client):
        """Test agent has description."""
        agent = CategoryAgent(mock_openai_client)
        assert "categor" in agent.description.lower()

    def test_has_tool_registry(self, mock_openai_client):
        """Test agent has tool registry with category tools."""
        agent = CategoryAgent(mock_openai_client)
        registry = agent.get_tool_registry()

        assert registry.get("get_categories") is not None
        assert registry.get("create_category") is not None
        assert registry.get("get_tags") is not None
        assert registry.get("create_tags") is not None
