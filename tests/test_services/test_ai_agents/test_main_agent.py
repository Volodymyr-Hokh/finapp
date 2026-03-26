"""
Tests for MainAgent (orchestrator).
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai_agents.main_agent import MainAgent
from services.ai_tools import AgentContext


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    client = AsyncMock()
    client.chat = AsyncMock()
    client.chat.completions = AsyncMock()
    return client


@pytest.fixture
def mock_repo():
    """Create mock repository."""
    return MagicMock()


@pytest.fixture
def agent_context(mock_repo):
    """Create agent context."""
    return AgentContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        repo=mock_repo
    )


class TestMainAgent:
    """Tests for MainAgent."""

    def test_has_correct_name(self, mock_openai_client):
        """Test agent has correct name."""
        agent = MainAgent(mock_openai_client)
        assert agent.name == "main_agent"

    def test_has_description(self, mock_openai_client):
        """Test agent has description."""
        agent = MainAgent(mock_openai_client)
        assert "orchestrator" in agent.description.lower()

    def test_system_prompt_lists_available_agents(self, mock_openai_client):
        """Test system prompt includes available agents."""
        agent = MainAgent(mock_openai_client)

        prompt = agent.system_prompt

        assert "account_agent" in prompt
        assert "transaction_agent" in prompt
        assert "budget_agent" in prompt
        assert "analytics_agent" in prompt
        assert "category_agent" in prompt

    def test_has_delegation_tool(self, mock_openai_client):
        """Test agent has delegation tool."""
        agent = MainAgent(mock_openai_client)
        registry = agent.get_tool_registry()

        assert registry.get("delegate_to_agent") is not None

    def test_agent_registry_is_initialized(self, mock_openai_client):
        """Test internal agent registry is initialized."""
        agent = MainAgent(mock_openai_client)

        assert agent._agent_registry is not None
        assert agent._agent_registry.get("account_agent") is not None

    @pytest.mark.asyncio
    async def test_direct_response_without_delegation(self, mock_openai_client, agent_context):
        """Test direct response when no delegation needed."""
        # Mock simple response without tool calls
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello! I'm your financial assistant."
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        agent = MainAgent(mock_openai_client)

        responses = []
        async for response in agent.run("Hello", agent_context, stream=False):
            responses.append(response)

        assert len(responses) == 1
        assert responses[0].content == "Hello! I'm your financial assistant."

    @pytest.mark.asyncio
    async def test_delegation_to_sub_agent(self, mock_openai_client, agent_context):
        """Test delegation to sub-agent."""
        # First response: delegation tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "delegate_to_agent"
        mock_tool_call.function.arguments = json.dumps({
            "agent_name": "account_agent",
            "task": "Show my accounts"
        })

        mock_choice1 = MagicMock()
        mock_choice1.message.content = None
        mock_choice1.message.tool_calls = [mock_tool_call]
        mock_choice1.finish_reason = "tool_calls"

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        # Sub-agent response
        mock_choice2 = MagicMock()
        mock_choice2.message.content = "Here are your accounts..."
        mock_choice2.message.tool_calls = None
        mock_choice2.finish_reason = "stop"

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.prompt_tokens = 50
        mock_response2.usage.completion_tokens = 30
        mock_response2.usage.total_tokens = 80

        mock_openai_client.chat.completions.create.side_effect = [mock_response1, mock_response2]

        agent = MainAgent(mock_openai_client)

        responses = []
        async for response in agent.run("Show my accounts", agent_context, stream=False):
            responses.append(response)

        assert len(responses) == 1
        assert responses[0].content == "Here are your accounts..."

    @pytest.mark.asyncio
    async def test_delegation_to_unknown_agent_returns_error(self, mock_openai_client, agent_context):
        """Test delegation to unknown agent returns error."""
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "delegate_to_agent"
        mock_tool_call.function.arguments = json.dumps({
            "agent_name": "nonexistent_agent",
            "task": "Do something"
        })

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_openai_client.chat.completions.create.return_value = mock_response

        agent = MainAgent(mock_openai_client)

        responses = []
        async for response in agent.run("Do something", agent_context, stream=False):
            responses.append(response)

        assert len(responses) == 1
        assert "error" in responses[0].content.lower() or responses[0].finish_reason == "error"
