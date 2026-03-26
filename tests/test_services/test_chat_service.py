"""
Tests for ChatService.
"""
import pytest
import json
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from services.chat_service import ChatService


@pytest.fixture
def mock_repo():
    """Create mock repository container."""
    repo = MagicMock()
    repo.chats = AsyncMock()
    repo.chat_messages = AsyncMock()
    return repo


@pytest.fixture
def mock_chat():
    """Create a mock chat object."""
    chat = MagicMock()
    chat.id = uuid4()
    chat.name = "Test Chat"
    chat.created_at = "2024-01-01T10:00:00"
    chat.updated_at = "2024-01-01T10:00:00"
    chat.update = AsyncMock()
    return chat


@pytest.fixture
def mock_message():
    """Create a mock message object."""
    msg = MagicMock()
    msg.id = 1
    msg.role = "user"
    msg.message_json = json.dumps({"content": "Hello"})
    msg.sequence_number = 1
    msg.created_at = "2024-01-01T10:00:00"
    return msg


class TestChatServiceCreation:
    """Tests for chat creation."""

    @pytest.mark.asyncio
    async def test_create_chat(self, mock_repo, mock_chat):
        """Test creating a new chat."""
        mock_repo.chats.create_for_user.return_value = mock_chat

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.create_chat(uuid4(), "Test Chat")

        assert result["name"] == "Test Chat"
        assert "id" in result
        mock_repo.chats.create_for_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_chat_with_default_name(self, mock_repo, mock_chat):
        """Test creating chat with default name."""
        mock_chat.name = "New Chat"
        mock_repo.chats.create_for_user.return_value = mock_chat

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            user_id = uuid4()
            await service.create_chat(user_id)

        mock_repo.chats.create_for_user.assert_called_once_with(user_id, "New Chat")


class TestChatServiceListing:
    """Tests for listing chats."""

    @pytest.mark.asyncio
    async def test_get_user_chats(self, mock_repo, mock_chat):
        """Test getting user's chats."""
        mock_repo.chats.get_user_chats.return_value = [mock_chat]

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.get_user_chats(uuid4())

        assert len(result) == 1
        assert result[0]["name"] == "Test Chat"

    @pytest.mark.asyncio
    async def test_get_user_chats_with_limit(self, mock_repo):
        """Test getting chats with limit."""
        mock_repo.chats.get_user_chats.return_value = []

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            user_id = uuid4()
            await service.get_user_chats(user_id, limit=10)

        mock_repo.chats.get_user_chats.assert_called_once_with(user_id, limit=10)


class TestChatServiceMessages:
    """Tests for message handling."""

    @pytest.mark.asyncio
    async def test_get_chat_messages(self, mock_repo, mock_message):
        """Test getting chat messages."""
        mock_repo.chat_messages.get_messages_by_chat_and_user.return_value = [mock_message]

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.get_chat_messages(uuid4(), uuid4())

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, mock_repo, mock_message):
        """Test getting conversation history for OpenAI."""
        mock_repo.chat_messages.get_latest_messages.return_value = [mock_message]

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service._get_conversation_history(uuid4())

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"


class TestChatServiceStreaming:
    """Tests for streaming responses."""

    @pytest.mark.asyncio
    async def test_send_message_stream_validates_chat_ownership(self, mock_repo):
        """Test that streaming validates chat ownership."""
        mock_repo.chats.get_by_id_and_user.return_value = None

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            chunks = []
            async for chunk in service.send_message_stream(uuid4(), uuid4(), "Hello"):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert "error" in chunks[0]
        assert "not found" in chunks[0].lower()

    @pytest.mark.asyncio
    async def test_quick_chat_stream_works(self, mock_repo):
        """Test quick chat without persistent session."""
        with patch("services.chat_service.AsyncOpenAI") as mock_openai:
            # Mock the main agent
            with patch("services.chat_service.MainAgent") as mock_agent_class:
                mock_agent = AsyncMock()

                async def mock_run(*args, **kwargs):
                    yield 'data: {"type": "content", "content": "Hello!"}\n\n'
                    yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

                mock_agent.run = mock_run
                mock_agent_class.return_value = mock_agent

                service = ChatService(mock_repo)
                chunks = []
                async for chunk in service.quick_chat_stream(uuid4(), "Hello"):
                    chunks.append(chunk)

        assert len(chunks) == 2


class TestChatServiceManagement:
    """Tests for chat management."""

    @pytest.mark.asyncio
    async def test_rename_chat(self, mock_repo, mock_chat):
        """Test renaming a chat."""
        mock_chat.name = "New Name"
        mock_repo.chats.update_name.return_value = mock_chat

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.rename_chat(mock_chat.id, uuid4(), "New Name")

        assert result["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_rename_chat_not_found(self, mock_repo):
        """Test renaming nonexistent chat."""
        mock_repo.chats.update_name.return_value = None

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.rename_chat(uuid4(), uuid4(), "New Name")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_chat(self, mock_repo):
        """Test deleting a chat."""
        mock_repo.chats.soft_delete.return_value = True

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.delete_chat(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_chat_not_found(self, mock_repo):
        """Test deleting nonexistent chat."""
        mock_repo.chats.soft_delete.return_value = False

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.delete_chat(uuid4(), uuid4())

        assert result is False


class TestChatServiceTitleGeneration:
    """Tests for AI title generation."""

    @pytest.mark.asyncio
    async def test_generate_chat_title(self, mock_repo, mock_chat, mock_message):
        """Test generating chat title."""
        mock_repo.chats.get_by_id_and_user.return_value = mock_chat
        mock_repo.chat_messages.get_messages_by_chat.return_value = [mock_message]

        with patch("services.chat_service.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Budget Questions"
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            service = ChatService(mock_repo)
            result = await service.generate_chat_title(mock_chat.id, uuid4())

        assert result == "Budget Questions"
        mock_repo.chats.update_name.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_chat_title_no_chat(self, mock_repo):
        """Test generating title for nonexistent chat."""
        mock_repo.chats.get_by_id_and_user.return_value = None

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.generate_chat_title(uuid4(), uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_chat_title_no_messages(self, mock_repo, mock_chat):
        """Test generating title with no messages."""
        mock_repo.chats.get_by_id_and_user.return_value = mock_chat
        mock_repo.chat_messages.get_messages_by_chat.return_value = []

        with patch("services.chat_service.AsyncOpenAI"):
            service = ChatService(mock_repo)
            result = await service.generate_chat_title(mock_chat.id, uuid4())

        assert result is None
