"""
API tests for chat endpoints (blueprints/chats.py).
"""
import pytest
import json
from uuid import uuid4


@pytest.mark.api
class TestCreateChat:
    """Tests for create chat endpoint."""

    def test_create_chat_success(self, test_client, auth_headers):
        """Test creating a chat."""
        request, response = test_client.post(
            "/chats/",
            headers=auth_headers,
            json={"name": "My Budget Chat"}
        )

        assert response.status_code == 201
        assert response.json["name"] == "My Budget Chat"
        assert "id" in response.json

    def test_create_chat_with_default_name(self, test_client, auth_headers):
        """Test creating chat with default name."""
        request, response = test_client.post(
            "/chats/",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 201
        assert response.json["name"] == "New Chat"

    def test_create_chat_unauthorized(self, test_client):
        """Test that creating chat requires authentication."""
        request, response = test_client.post(
            "/chats/",
            json={"name": "Test"}
        )

        assert response.status_code == 401


@pytest.mark.api
class TestListChats:
    """Tests for list chats endpoint."""

    def test_list_chats_empty(self, test_client, auth_headers):
        """Test listing chats when user has none."""
        request, response = test_client.get(
            "/chats/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "chats" in response.json
        assert response.json["total"] >= 0

    def test_list_chats_with_existing(self, test_client, sample_chat, auth_headers):
        """Test listing chats includes existing chats."""
        request, response = test_client.get(
            "/chats/",
            headers=auth_headers
        )

        assert response.status_code == 200
        chat_ids = [c["id"] for c in response.json["chats"]]
        assert str(sample_chat.id) in chat_ids

    def test_list_chats_unauthorized(self, test_client):
        """Test that listing chats requires authentication."""
        request, response = test_client.get("/chats/")

        assert response.status_code == 401


@pytest.mark.api
class TestGetChat:
    """Tests for get chat endpoint."""

    def test_get_chat_success(self, test_client, sample_chat, auth_headers):
        """Test getting a specific chat."""
        request, response = test_client.get(
            f"/chats/{sample_chat.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["id"] == str(sample_chat.id)
        assert response.json["name"] == sample_chat.name
        assert "messages" in response.json

    def test_get_chat_not_found(self, test_client, auth_headers):
        """Test getting nonexistent chat."""
        fake_id = uuid4()
        request, response = test_client.get(
            f"/chats/{fake_id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_get_chat_different_user(self, app, another_user, sample_chat, auth_headers, create_model):
        """Test that users cannot access other users' chats."""
        # sample_chat belongs to sample_user, auth_headers are for sample_user
        # Create a chat for another_user
        from db.models import Chat
        other_chat = await create_model(
            Chat,
            user_id=another_user.id,
            name="Other User Chat"
        )

        request, response = await app.asgi_client.get(
            f"/chats/{other_chat.id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestUpdateChat:
    """Tests for update chat endpoint."""

    def test_update_chat_name(self, test_client, sample_chat, auth_headers):
        """Test updating chat name."""
        request, response = test_client.patch(
            f"/chats/{sample_chat.id}",
            headers=auth_headers,
            json={"name": "Updated Chat Name"}
        )

        assert response.status_code == 200
        assert response.json["name"] == "Updated Chat Name"

    def test_update_chat_not_found(self, test_client, auth_headers):
        """Test updating nonexistent chat."""
        fake_id = uuid4()
        request, response = test_client.patch(
            f"/chats/{fake_id}",
            headers=auth_headers,
            json={"name": "New Name"}
        )

        assert response.status_code == 404

    def test_update_chat_validation(self, test_client, sample_chat, auth_headers):
        """Test validation on update."""
        request, response = test_client.patch(
            f"/chats/{sample_chat.id}",
            headers=auth_headers,
            json={"name": ""}  # Empty name should fail
        )

        assert response.status_code == 422


@pytest.mark.api
class TestDeleteChat:
    """Tests for delete chat endpoint."""

    async def test_delete_chat_success(self, app, sample_user, auth_headers, create_model):
        """Test deleting a chat."""
        from db.models import Chat
        chat = await create_model(
            Chat,
            user_id=sample_user.id,
            name="To Delete"
        )

        request, response = await app.asgi_client.delete(
            f"/chats/{chat.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted" in response.json["message"].lower()

    def test_delete_chat_not_found(self, test_client, auth_headers):
        """Test deleting nonexistent chat."""
        fake_id = uuid4()
        request, response = test_client.delete(
            f"/chats/{fake_id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestGenerateTitle:
    """Tests for generate title endpoint."""

    async def test_generate_title_no_messages(self, app, sample_chat, auth_headers):
        """Test generating title with no messages."""
        request, response = await app.asgi_client.post(
            f"/chats/{sample_chat.id}/generate-title",
            headers=auth_headers
        )

        # Should return 404 because no messages to generate from
        assert response.status_code == 404

    def test_generate_title_not_found(self, test_client, auth_headers):
        """Test generating title for nonexistent chat."""
        fake_id = uuid4()
        request, response = test_client.post(
            f"/chats/{fake_id}/generate-title",
            headers=auth_headers
        )

        assert response.status_code == 404
