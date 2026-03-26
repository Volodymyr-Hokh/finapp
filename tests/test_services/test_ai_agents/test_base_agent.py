"""
Tests for BaseAgent class.
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai_agents.base_agent import BaseAgent, AgentResponse, ToolCall
from services.ai_tools import ToolRegistry, AgentContext


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def __init__(self, client, tools=None):
        super().__init__(client)
        self._tools = tools or ToolRegistry()

    @property
    def name(self) -> str:
        return "test_agent"

    @property
    def description(self) -> str:
        return "A test agent"

    @property
    def system_prompt(self) -> str:
        return "You are a test agent."

    def get_tool_registry(self) -> ToolRegistry:
        return self._tools


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


class TestAgentResponse:
    """Tests for AgentResponse dataclass."""

    def test_creates_with_defaults(self):
        """Test creating AgentResponse with defaults."""
        response = AgentResponse(content="Hello")

        assert response.content == "Hello"
        assert response.tool_calls == []
        assert response.usage == {}
        assert response.finish_reason == "stop"

    def test_creates_with_all_fields(self):
        """Test creating AgentResponse with all fields."""
        tool_calls = [ToolCall(id="1", name="test", arguments={})]
        response = AgentResponse(
            content="Hello",
            tool_calls=tool_calls,
            usage={"total_tokens": 100},
            finish_reason="tool_calls"
        )

        assert response.content == "Hello"
        assert len(response.tool_calls) == 1
        assert response.usage["total_tokens"] == 100
        assert response.finish_reason == "tool_calls"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_creates_tool_call(self):
        """Test creating ToolCall."""
        tc = ToolCall(id="call_123", name="get_accounts", arguments={"limit": 10})

        assert tc.id == "call_123"
        assert tc.name == "get_accounts"
        assert tc.arguments == {"limit": 10}


class TestBaseAgent:
    """Tests for BaseAgent class."""

    def test_agent_has_required_properties(self, mock_openai_client):
        """Test that concrete agent has required properties."""
        agent = ConcreteAgent(mock_openai_client)

        assert agent.name == "test_agent"
        assert agent.description == "A test agent"
        assert agent.system_prompt == "You are a test agent."

    def test_agent_has_model_constants(self, mock_openai_client):
        """Test default model constants."""
        agent = ConcreteAgent(mock_openai_client)

        assert agent.MODEL == "gpt-4o"
        assert agent.MAX_TOKENS == 4096
        assert agent.TEMPERATURE == 0.7

    @pytest.mark.asyncio
    async def test_complete_response_returns_content(self, mock_openai_client, agent_context):
        """Test non-streaming response returns content."""
        # Mock OpenAI response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, I'm the AI!"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_openai_client.chat.completions.create.return_value = mock_response

        agent = ConcreteAgent(mock_openai_client)

        # Run non-streaming
        responses = []
        async for response in agent.run("Hello", agent_context, stream=False):
            responses.append(response)

        assert len(responses) == 1
        assert isinstance(responses[0], AgentResponse)
        assert responses[0].content == "Hello, I'm the AI!"
        assert responses[0].usage["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_complete_response_with_tool_calls(self, mock_openai_client, agent_context):
        """Test response with tool calls executes tools and continues."""
        # First response: tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"arg": "value"}'

        mock_choice1 = MagicMock()
        mock_choice1.message.content = None
        mock_choice1.message.tool_calls = [mock_tool_call]
        mock_choice1.message.model_dump.return_value = {"role": "assistant", "content": None, "tool_calls": []}
        mock_choice1.finish_reason = "tool_calls"

        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]
        mock_response1.usage = None

        # Second response: final answer
        mock_choice2 = MagicMock()
        mock_choice2.message.content = "Done!"
        mock_choice2.message.tool_calls = None
        mock_choice2.finish_reason = "stop"

        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]
        mock_response2.usage.prompt_tokens = 50
        mock_response2.usage.completion_tokens = 10
        mock_response2.usage.total_tokens = 60

        mock_openai_client.chat.completions.create.side_effect = [mock_response1, mock_response2]

        # Create registry with mock tool
        registry = ToolRegistry()

        async def mock_tool_func(ctx, arg):
            return {"result": arg}

        from services.ai_tools import ToolDefinition
        registry.register(ToolDefinition(
            name="test_tool",
            description="Test",
            schema={},
            func=mock_tool_func
        ))

        agent = ConcreteAgent(mock_openai_client, tools=registry)

        responses = []
        async for response in agent.run("Use the tool", agent_context, stream=False):
            responses.append(response)

        assert len(responses) == 1
        assert responses[0].content == "Done!"

    def test_build_messages_includes_system_prompt(self, mock_openai_client, agent_context):
        """Test that _build_messages includes system prompt with date."""
        agent = ConcreteAgent(mock_openai_client)

        messages = agent._build_messages(agent_context, "Hello")

        assert messages[0]["role"] == "system"
        assert "Current date:" in messages[0]["content"]
        assert "You are a test agent." in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_build_system_prompt_includes_date_and_weekday(self, mock_openai_client, agent_context):
        """Test that _build_system_prompt includes current date and weekday."""
        agent = ConcreteAgent(mock_openai_client)

        system_prompt = agent._build_system_prompt(agent_context)

        expected_date = agent_context.current_date.strftime("%A, %Y-%m-%d")
        assert f"Current date: {expected_date}" in system_prompt
        assert "You are a test agent." in system_prompt
