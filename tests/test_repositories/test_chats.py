"""
Tests for ChatRepository.
"""
import pytest
import uuid
import asyncio

from db.models import Chat


@pytest.mark.integration
class TestChatRepository:
    """Test ChatRepository."""

    async def test_get_user_chats_returns_user_chats_only(
        self, repo, sample_user, another_user, sample_chat, create_model
    ):
        """Test that get_user_chats only returns chats for the specified user."""
        # Create chat for another user
        other_chat = await create_model(Chat, user_id=another_user.id, name="Other User Chat")

        # Get chats for sample_user
        chats = await repo.chats.get_user_chats(sample_user.id)

        chat_ids = [c.id for c in chats]
        assert sample_chat.id in chat_ids
        assert other_chat.id not in chat_ids

    async def test_get_user_chats_excludes_deleted_by_default(
        self, repo, sample_user, sample_chat, create_model
    ):
        """Test that deleted chats are excluded by default."""
        # Create and soft-delete a chat
        deleted_chat = await create_model(
            Chat, user_id=sample_user.id, name="Deleted Chat", is_deleted=True
        )

        chats = await repo.chats.get_user_chats(sample_user.id)

        chat_ids = [c.id for c in chats]
        assert sample_chat.id in chat_ids
        assert deleted_chat.id not in chat_ids

    async def test_get_user_chats_includes_deleted_when_requested(
        self, repo, sample_user, sample_chat, create_model
    ):
        """Test that deleted chats are included when include_deleted=True."""
        deleted_chat = await create_model(
            Chat, user_id=sample_user.id, name="Deleted Chat", is_deleted=True
        )

        chats = await repo.chats.get_user_chats(sample_user.id, include_deleted=True)

        chat_ids = [c.id for c in chats]
        assert sample_chat.id in chat_ids
        assert deleted_chat.id in chat_ids

    async def test_get_user_chats_respects_limit(self, repo, sample_user, create_model):
        """Test that limit parameter is respected."""
        # Create multiple chats
        for i in range(5):
            await create_model(Chat, user_id=sample_user.id, name=f"Chat {i}")

        chats = await repo.chats.get_user_chats(sample_user.id, limit=3)

        assert len(chats) == 3

    async def test_get_user_chats_ordered_by_updated_at_desc(self, repo, sample_user, create_model):
        """Test that chats are ordered by updated_at descending."""
        chat1 = await create_model(Chat, user_id=sample_user.id, name="Chat 1")
        await asyncio.sleep(0.01)
        chat2 = await create_model(Chat, user_id=sample_user.id, name="Chat 2")
        await asyncio.sleep(0.01)
        chat3 = await create_model(Chat, user_id=sample_user.id, name="Chat 3")

        chats = await repo.chats.get_user_chats(sample_user.id)

        # Most recently created should be first
        assert chats[0].id == chat3.id
        assert chats[1].id == chat2.id
        assert chats[2].id == chat1.id

    async def test_get_by_id_and_user_returns_chat(self, repo, sample_user, sample_chat):
        """Test getting a chat by ID for the correct user."""
        chat = await repo.chats.get_by_id_and_user(sample_chat.id, sample_user.id)

        assert chat is not None
        assert chat.id == sample_chat.id

    async def test_get_by_id_and_user_returns_none_for_wrong_user(
        self, repo, sample_user, another_user, sample_chat
    ):
        """Test that None is returned when chat belongs to different user."""
        chat = await repo.chats.get_by_id_and_user(sample_chat.id, another_user.id)

        assert chat is None

    async def test_get_by_id_and_user_returns_none_for_deleted(
        self, repo, sample_user, create_model
    ):
        """Test that None is returned for deleted chats by default."""
        deleted_chat = await create_model(
            Chat, user_id=sample_user.id, name="Deleted", is_deleted=True
        )

        chat = await repo.chats.get_by_id_and_user(deleted_chat.id, sample_user.id)

        assert chat is None

    async def test_get_by_id_and_user_returns_deleted_when_requested(
        self, repo, sample_user, create_model
    ):
        """Test that deleted chats are returned when include_deleted=True."""
        deleted_chat = await create_model(
            Chat, user_id=sample_user.id, name="Deleted", is_deleted=True
        )

        chat = await repo.chats.get_by_id_and_user(
            deleted_chat.id, sample_user.id, include_deleted=True
        )

        assert chat is not None
        assert chat.id == deleted_chat.id

    async def test_get_recent_chats(self, repo, sample_user, create_model):
        """Test getting recent chats with limit."""
        # Create multiple chats
        for i in range(5):
            await create_model(Chat, user_id=sample_user.id, name=f"Chat {i}")
            await asyncio.sleep(0.01)

        chats = await repo.chats.get_recent_chats(sample_user.id, limit=3)

        assert len(chats) == 3
        # Should be ordered by updated_at desc
        assert chats[0].name == "Chat 4"

    async def test_soft_delete_marks_chat_deleted(self, repo, sample_user, sample_chat):
        """Test that soft_delete sets is_deleted=True."""
        result = await repo.chats.soft_delete(sample_chat.id, sample_user.id)

        assert result is True

        # Verify chat is deleted
        chat = await repo.chats.get_by_id_and_user(
            sample_chat.id, sample_user.id, include_deleted=True
        )
        assert chat.is_deleted is True

    async def test_soft_delete_returns_false_for_nonexistent(self, repo, sample_user):
        """Test that soft_delete returns False for non-existent chat."""
        fake_id = uuid.uuid4()
        result = await repo.chats.soft_delete(fake_id, sample_user.id)

        assert result is False

    async def test_soft_delete_returns_false_for_wrong_user(
        self, repo, sample_user, another_user, sample_chat
    ):
        """Test that soft_delete returns False when user doesn't own chat."""
        result = await repo.chats.soft_delete(sample_chat.id, another_user.id)

        assert result is False

        # Verify chat is not deleted
        chat = await repo.chats.get_by_id_and_user(sample_chat.id, sample_user.id)
        assert chat.is_deleted is False

    async def test_restore_undeletes_chat(self, repo, sample_user, create_model):
        """Test that restore sets is_deleted=False."""
        deleted_chat = await create_model(
            Chat, user_id=sample_user.id, name="Deleted", is_deleted=True
        )

        result = await repo.chats.restore(deleted_chat.id, sample_user.id)

        assert result is True

        # Verify chat is restored
        chat = await repo.chats.get_by_id_and_user(deleted_chat.id, sample_user.id)
        assert chat is not None
        assert chat.is_deleted is False

    async def test_restore_returns_false_for_non_deleted(
        self, repo, sample_user, sample_chat
    ):
        """Test that restore returns False for non-deleted chat."""
        result = await repo.chats.restore(sample_chat.id, sample_user.id)

        assert result is False

    async def test_update_name(self, repo, sample_user, sample_chat):
        """Test updating chat name."""
        updated = await repo.chats.update_name(
            sample_chat.id, sample_user.id, "New Name"
        )

        assert updated is not None
        assert updated.name == "New Name"

    async def test_update_name_returns_none_for_wrong_user(
        self, repo, sample_user, another_user, sample_chat
    ):
        """Test that update_name returns None for wrong user."""
        updated = await repo.chats.update_name(
            sample_chat.id, another_user.id, "New Name"
        )

        assert updated is None

        # Verify name unchanged
        chat = await repo.chats.get_by_id_and_user(sample_chat.id, sample_user.id)
        assert chat.name == "Test Chat"

    async def test_create_for_user(self, repo, sample_user):
        """Test creating a new chat for a user."""
        chat = await repo.chats.create_for_user(sample_user.id, "My New Chat")

        assert chat is not None
        assert chat.name == "My New Chat"
        assert chat.user_id == sample_user.id
        assert chat.is_deleted is False

    async def test_create_for_user_with_default_name(self, repo, sample_user):
        """Test creating a new chat with default name."""
        chat = await repo.chats.create_for_user(sample_user.id)

        assert chat.name == "New Chat"

    async def test_get_chat_count(self, repo, sample_user, sample_chat, create_model):
        """Test getting chat count for user."""
        # Create additional chats
        await create_model(Chat, user_id=sample_user.id, name="Chat 2")
        await create_model(Chat, user_id=sample_user.id, name="Chat 3")

        count = await repo.chats.get_chat_count(sample_user.id)

        assert count == 3

    async def test_get_chat_count_excludes_deleted(self, repo, sample_user, sample_chat, create_model):
        """Test that chat count excludes deleted chats by default."""
        await create_model(
            Chat, user_id=sample_user.id, name="Deleted", is_deleted=True
        )

        count = await repo.chats.get_chat_count(sample_user.id)

        assert count == 1

    async def test_get_chat_count_includes_deleted_when_requested(
        self, repo, sample_user, sample_chat, create_model
    ):
        """Test that chat count includes deleted when requested."""
        await create_model(
            Chat, user_id=sample_user.id, name="Deleted", is_deleted=True
        )

        count = await repo.chats.get_chat_count(sample_user.id, include_deleted=True)

        assert count == 2
