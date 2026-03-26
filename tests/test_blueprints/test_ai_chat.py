"""
API tests for AI chat SSE endpoints (blueprints/ai_chat.py).
"""
import base64

import pytest
import json
from uuid import uuid4
from unittest.mock import patch, AsyncMock


@pytest.mark.api
class TestSendMessageEndpoint:
    """Tests for send message SSE endpoint."""

    def test_send_message_unauthorized(self, test_client):
        """Test that sending message requires authentication."""
        chat_id = uuid4()
        request, response = test_client.post(
            f"/ai/chats/{chat_id}/message",
            json={"message": "Hello"}
        )

        assert response.status_code == 401

    def test_send_message_validation(self, test_client, sample_chat, auth_headers):
        """Test message validation."""
        request, response = test_client.post(
            f"/ai/chats/{sample_chat.id}/message",
            headers=auth_headers,
            json={"message": ""}  # Empty message
        )

        assert response.status_code == 422

    async def test_send_message_chat_not_found(self, app, auth_headers):
        """Test sending message to nonexistent chat."""
        fake_id = uuid4()

        request, response = await app.asgi_client.post(
            f"/ai/chats/{fake_id}/message",
            headers=auth_headers,
            json={"message": "Hello"}
        )

        # Should return 200 with SSE error event (streaming endpoint)
        assert response.status_code == 200
        assert "error" in response.body.decode().lower()


@pytest.mark.api
class TestQuickChatEndpoint:
    """Tests for quick chat SSE endpoint."""

    def test_quick_chat_unauthorized(self, test_client):
        """Test that quick chat requires authentication."""
        request, response = test_client.post(
            "/ai/quick-chat/stream",
            json={"message": "Hello"}
        )

        assert response.status_code == 401

    def test_quick_chat_validation(self, test_client, auth_headers):
        """Test message validation for quick chat."""
        request, response = test_client.post(
            "/ai/quick-chat/stream",
            headers=auth_headers,
            json={"message": ""}
        )

        assert response.status_code == 422


@pytest.mark.api
class TestQuickChatCreateEndpoint:
    """Tests for quick chat with session creation endpoint."""

    def test_quick_chat_create_unauthorized(self, test_client):
        """Test that quick chat create requires authentication."""
        request, response = test_client.post(
            "/ai/quick-chat/create",
            json={"message": "Hello"}
        )

        assert response.status_code == 401

    def test_quick_chat_create_validation(self, test_client, auth_headers):
        """Test message validation."""
        request, response = test_client.post(
            "/ai/quick-chat/create",
            headers=auth_headers,
            json={"message": ""}
        )

        assert response.status_code == 422


@pytest.mark.api
class TestSSEResponseFormat:
    """Tests for SSE response format."""

    async def test_sse_content_type(self, app, sample_chat, auth_headers):
        """Test that SSE endpoints return correct content type."""
        # Mock the ChatService to avoid actual AI calls
        mock_service = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield 'data: {"type": "content", "content": "Hello"}\n\n'
            yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

        mock_service.send_message_stream = mock_stream

        with patch("blueprints.ai_chat.get_chat_service", return_value=mock_service):
            request, response = await app.asgi_client.post(
                f"/ai/chats/{sample_chat.id}/message",
                headers=auth_headers,
                json={"message": "Hello"}
            )

        assert response.content_type == "text/event-stream"


@pytest.mark.integration
class TestAIChatIntegration:
    """Integration tests for AI chat (requires mocking OpenAI)."""

    async def test_full_chat_flow(self, app, sample_user, auth_headers, create_model):
        """Test full chat flow: create chat, send message."""
        from db.models import Chat

        # Create a chat
        chat = await create_model(
            Chat,
            user_id=sample_user.id,
            name="Integration Test Chat"
        )

        # Mock the ChatService via get_chat_service to bypass caching
        mock_service = AsyncMock()

        async def mock_stream(*args, **kwargs):
            yield 'data: {"type": "content", "content": "I can help you with your finances!"}\n\n'
            yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

        mock_service.send_message_stream = mock_stream

        with patch("blueprints.ai_chat.get_chat_service", return_value=mock_service):
            request, response = await app.asgi_client.post(
                f"/ai/chats/{chat.id}/message",
                headers=auth_headers,
                json={"message": "What can you help me with?"}
            )

        assert response.status_code == 200
        body = response.body.decode()
        assert "content" in body
        assert "done" in body

    async def test_quick_chat_creates_session(self, app, auth_headers):
        """Test quick chat with session creation returns chat_id."""
        mock_service = AsyncMock()
        chat_id = uuid4()

        mock_service.create_chat.return_value = {
            "id": str(chat_id),
            "name": "Test"
        }

        async def mock_stream(*args, **kwargs):
            yield 'data: {"type": "content", "content": "Hello!"}\n\n'
            yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

        mock_service.send_message_stream = mock_stream

        with patch("blueprints.ai_chat.get_chat_service", return_value=mock_service):
            request, response = await app.asgi_client.post(
                "/ai/quick-chat/create",
                headers=auth_headers,
                json={"message": "Hello", "name": "Test Chat"}
            )

        assert response.status_code == 200
        body = response.body.decode()
        assert "chat_created" in body


@pytest.mark.api
class TestImageAttachment:
    """Tests for sending messages with image attachments."""

    TINY_JPEG_B64 = base64.b64encode(b"\xff\xd8" + b"\x00" * 100).decode()

    async def test_send_message_with_image(self, app, sample_chat, auth_headers):
        """Test sending a message with an image attachment passes image_data to service."""
        mock_service = AsyncMock()
        captured_kwargs = {}

        async def mock_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield 'data: {"type": "content", "content": "I see a receipt."}\n\n'
            yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

        mock_service.send_message_stream = mock_stream

        with patch("blueprints.ai_chat.get_chat_service", return_value=mock_service):
            request, response = await app.asgi_client.post(
                f"/ai/chats/{sample_chat.id}/message",
                headers=auth_headers,
                json={
                    "message": "What is this receipt?",
                    "image": {
                        "data": self.TINY_JPEG_B64,
                        "mime_type": "image/jpeg",
                    },
                },
            )

        assert response.status_code == 200
        assert captured_kwargs.get("image_data") is not None
        assert captured_kwargs["image_data"]["mime_type"] == "image/jpeg"

    async def test_send_message_without_image(self, app, sample_chat, auth_headers):
        """Test that image_data is None when no image is attached."""
        mock_service = AsyncMock()
        captured_kwargs = {}

        async def mock_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield 'data: {"type": "content", "content": "Hello!"}\n\n'
            yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

        mock_service.send_message_stream = mock_stream

        with patch("blueprints.ai_chat.get_chat_service", return_value=mock_service):
            request, response = await app.asgi_client.post(
                f"/ai/chats/{sample_chat.id}/message",
                headers=auth_headers,
                json={"message": "Hello"},
            )

        assert response.status_code == 200
        assert captured_kwargs.get("image_data") is None

    def test_send_message_invalid_mime_type(self, test_client, sample_chat, auth_headers):
        """Test that invalid MIME type is rejected by schema validation."""
        request, response = test_client.post(
            f"/ai/chats/{sample_chat.id}/message",
            headers=auth_headers,
            json={
                "message": "Check this",
                "image": {
                    "data": self.TINY_JPEG_B64,
                    "mime_type": "application/pdf",
                },
            },
        )
        assert response.status_code == 422

    async def test_quick_chat_with_image(self, app, auth_headers):
        """Test quick chat with image attachment."""
        mock_service = AsyncMock()
        captured_kwargs = {}

        async def mock_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield 'data: {"type": "content", "content": "I see a receipt."}\n\n'
            yield 'data: {"type": "done", "finish_reason": "stop"}\n\n'

        mock_service.quick_chat_stream = mock_stream

        with patch("blueprints.ai_chat.get_chat_service", return_value=mock_service):
            request, response = await app.asgi_client.post(
                "/ai/quick-chat/stream",
                headers=auth_headers,
                json={
                    "message": "What is this?",
                    "image": {
                        "data": self.TINY_JPEG_B64,
                        "mime_type": "image/png",
                    },
                },
            )

        assert response.status_code == 200
        assert captured_kwargs.get("image_data") is not None
