"""
Tests for ChatMessageRepository.
"""
import pytest
import json
import asyncio

from db.models import Chat, ChatMessage


@pytest.mark.integration
class TestChatMessageRepository:
    """Test ChatMessageRepository."""

    async def test_get_messages_by_chat_returns_ordered(
        self, repo, sample_chat, create_model
    ):
        """Test that messages are returned ordered by sequence_number."""
        # Create messages out of order
        msg3 = await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg3"}', role="user", sequence_number=3
        )
        msg1 = await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg1"}', role="user", sequence_number=1
        )
        msg2 = await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg2"}', role="assistant", sequence_number=2
        )

        messages = await repo.chat_messages.get_messages_by_chat(sample_chat.id)

        assert len(messages) == 3
        assert messages[0].sequence_number == 1
        assert messages[1].sequence_number == 2
        assert messages[2].sequence_number == 3

    async def test_get_messages_by_chat_with_limit_and_offset(
        self, repo, sample_chat, create_model
    ):
        """Test pagination with limit and offset."""
        # Create 5 messages
        for i in range(1, 6):
            await create_model(
                ChatMessage,
                chat_id=sample_chat.id,
                message_json=f'{{"text":"msg{i}"}}',
                role="user",
                sequence_number=i
            )

        # Get messages with offset=2, limit=2
        messages = await repo.chat_messages.get_messages_by_chat(
            sample_chat.id, limit=2, offset=2
        )

        assert len(messages) == 2
        assert messages[0].sequence_number == 3
        assert messages[1].sequence_number == 4

    async def test_get_messages_by_chat_and_user_validates_ownership(
        self, repo, sample_user, another_user, sample_chat, create_model
    ):
        """Test that messages are only returned if user owns the chat."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"hello"}', role="user", sequence_number=1
        )

        # Should return messages for correct user
        messages = await repo.chat_messages.get_messages_by_chat_and_user(
            sample_chat.id, sample_user.id
        )
        assert len(messages) == 1

        # Should return empty for wrong user
        messages = await repo.chat_messages.get_messages_by_chat_and_user(
            sample_chat.id, another_user.id
        )
        assert len(messages) == 0

    async def test_get_messages_by_chat_and_user_empty_for_deleted_chat(
        self, repo, sample_user, create_model
    ):
        """Test that empty list is returned for deleted chat."""
        deleted_chat = await create_model(
            Chat, user_id=sample_user.id, name="Deleted", is_deleted=True
        )
        await create_model(
            ChatMessage, chat_id=deleted_chat.id, message_json='{"text":"hello"}', role="user", sequence_number=1
        )

        messages = await repo.chat_messages.get_messages_by_chat_and_user(
            deleted_chat.id, sample_user.id
        )

        assert len(messages) == 0

    async def test_get_latest_messages_returns_recent(self, repo, sample_chat, create_model):
        """Test that get_latest_messages returns the most recent messages."""
        # Create 10 messages
        for i in range(1, 11):
            await create_model(
                ChatMessage,
                chat_id=sample_chat.id,
                message_json=f'{{"text":"msg{i}"}}',
                role="user",
                sequence_number=i
            )

        # Get latest 5
        messages = await repo.chat_messages.get_latest_messages(sample_chat.id, limit=5)

        assert len(messages) == 5
        # Should be messages 6-10
        sequence_numbers = [m.sequence_number for m in messages]
        assert sequence_numbers == [6, 7, 8, 9, 10]

    async def test_get_latest_messages_in_correct_order(self, repo, sample_chat, create_model):
        """Test that latest messages are returned in ascending sequence order."""
        for i in range(1, 6):
            await create_model(
                ChatMessage,
                chat_id=sample_chat.id,
                message_json=f'{{"text":"msg{i}"}}',
                role="user",
                sequence_number=i
            )

        messages = await repo.chat_messages.get_latest_messages(sample_chat.id, limit=3)

        # Should be in ascending order (oldest first within window)
        assert messages[0].sequence_number == 3
        assert messages[1].sequence_number == 4
        assert messages[2].sequence_number == 5

    async def test_get_next_sequence_number_starts_at_one(self, repo, sample_chat):
        """Test that sequence number starts at 1 for empty chat."""
        next_seq = await repo.chat_messages.get_next_sequence_number(sample_chat.id)

        assert next_seq == 1

    async def test_get_next_sequence_number_increments(self, repo, sample_chat, create_model):
        """Test that sequence number increments correctly."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg1"}', role="user", sequence_number=1
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg2"}', role="assistant", sequence_number=2
        )

        next_seq = await repo.chat_messages.get_next_sequence_number(sample_chat.id)

        assert next_seq == 3

    async def test_create_message_auto_sequences(self, repo, sample_chat):
        """Test that create_message automatically assigns sequence numbers."""
        msg1 = await repo.chat_messages.create_message(
            sample_chat.id, '{"text":"hello"}', "user"
        )
        msg2 = await repo.chat_messages.create_message(
            sample_chat.id, '{"text":"hi there"}', "assistant"
        )
        msg3 = await repo.chat_messages.create_message(
            sample_chat.id, '{"text":"how are you"}', "user"
        )

        assert msg1.sequence_number == 1
        assert msg2.sequence_number == 2
        assert msg3.sequence_number == 3

    async def test_create_message_with_token_count(self, repo, sample_chat):
        """Test creating message with token count."""
        msg = await repo.chat_messages.create_message(
            sample_chat.id, '{"text":"hello"}', "user", token_count=10
        )

        assert msg.token_count == 10

    async def test_create_message_without_token_count(self, repo, sample_chat):
        """Test creating message without token count."""
        msg = await repo.chat_messages.create_message(
            sample_chat.id, '{"text":"hello"}', "user"
        )

        assert msg.token_count is None

    async def test_get_message_by_id_and_chat(self, repo, sample_chat, create_model):
        """Test getting specific message by ID and chat."""
        msg = await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"hello"}', role="user", sequence_number=1
        )

        found = await repo.chat_messages.get_message_by_id_and_chat(
            msg.id, sample_chat.id
        )

        assert found is not None
        assert found.id == msg.id

    async def test_get_message_by_id_and_chat_wrong_chat(
        self, repo, sample_user, sample_chat, create_model
    ):
        """Test that None is returned for wrong chat."""
        msg = await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"hello"}', role="user", sequence_number=1
        )

        # Create another chat
        other_chat = await create_model(Chat, user_id=sample_user.id, name="Other Chat")

        found = await repo.chat_messages.get_message_by_id_and_chat(
            msg.id, other_chat.id
        )

        assert found is None

    async def test_get_messages_by_role(self, repo, sample_chat, create_model):
        """Test filtering messages by role."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"q1"}', role="user", sequence_number=1
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"a1"}', role="assistant", sequence_number=2
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"q2"}', role="user", sequence_number=3
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"system"}', role="system", sequence_number=4
        )

        user_messages = await repo.chat_messages.get_messages_by_role(
            sample_chat.id, "user"
        )
        assistant_messages = await repo.chat_messages.get_messages_by_role(
            sample_chat.id, "assistant"
        )

        assert len(user_messages) == 2
        assert len(assistant_messages) == 1

    async def test_get_message_count(self, repo, sample_chat, create_model):
        """Test counting messages in a chat."""
        for i in range(1, 6):
            await create_model(
                ChatMessage,
                chat_id=sample_chat.id,
                message_json=f'{{"text":"msg{i}"}}',
                role="user",
                sequence_number=i
            )

        count = await repo.chat_messages.get_message_count(sample_chat.id)

        assert count == 5

    async def test_get_message_count_empty_chat(self, repo, sample_chat):
        """Test that count is 0 for empty chat."""
        count = await repo.chat_messages.get_message_count(sample_chat.id)

        assert count == 0

    async def test_get_total_tokens(self, repo, sample_chat, create_model):
        """Test summing token counts."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg1"}', role="user",
            sequence_number=1, token_count=10
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg2"}', role="assistant",
            sequence_number=2, token_count=25
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg3"}', role="user",
            sequence_number=3, token_count=15
        )

        total = await repo.chat_messages.get_total_tokens(sample_chat.id)

        assert total == 50

    async def test_get_total_tokens_handles_nulls(self, repo, sample_chat, create_model):
        """Test that null token counts are treated as 0."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg1"}', role="user",
            sequence_number=1, token_count=10
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg2"}', role="assistant",
            sequence_number=2, token_count=None
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg3"}', role="user",
            sequence_number=3, token_count=20
        )

        total = await repo.chat_messages.get_total_tokens(sample_chat.id)

        assert total == 30

    async def test_delete_messages_after_sequence(self, repo, sample_chat, create_model):
        """Test deleting messages after a specific sequence number."""
        for i in range(1, 6):
            await create_model(
                ChatMessage,
                chat_id=sample_chat.id,
                message_json=f'{{"text":"msg{i}"}}',
                role="user",
                sequence_number=i
            )

        # Delete messages after sequence 2
        deleted_count = await repo.chat_messages.delete_messages_after_sequence(
            sample_chat.id, 2
        )

        assert deleted_count == 3

        # Verify only messages 1 and 2 remain
        remaining = await repo.chat_messages.get_messages_by_chat(sample_chat.id)
        assert len(remaining) == 2
        assert remaining[0].sequence_number == 1
        assert remaining[1].sequence_number == 2

    async def test_delete_messages_after_sequence_none_to_delete(
        self, repo, sample_chat, create_model
    ):
        """Test that 0 is returned when no messages to delete."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"msg1"}', role="user", sequence_number=1
        )

        deleted_count = await repo.chat_messages.delete_messages_after_sequence(
            sample_chat.id, 5
        )

        assert deleted_count == 0

    async def test_get_last_message(self, repo, sample_chat, create_model):
        """Test getting the most recent message."""
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"first"}', role="user", sequence_number=1
        )
        await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"second"}', role="assistant", sequence_number=2
        )
        last_msg = await create_model(
            ChatMessage, chat_id=sample_chat.id, message_json='{"text":"third"}', role="user", sequence_number=3
        )

        last = await repo.chat_messages.get_last_message(sample_chat.id)

        assert last is not None
        assert last.id == last_msg.id
        assert last.sequence_number == 3

    async def test_get_last_message_empty_chat(self, repo, sample_chat):
        """Test that None is returned for empty chat."""
        last = await repo.chat_messages.get_last_message(sample_chat.id)

        assert last is None

    async def test_delete_all_messages(self, repo, sample_chat, create_model):
        """Test deleting all messages in a chat."""
        for i in range(1, 6):
            await create_model(
                ChatMessage,
                chat_id=sample_chat.id,
                message_json=f'{{"text":"msg{i}"}}',
                role="user",
                sequence_number=i
            )

        deleted_count = await repo.chat_messages.delete_all_messages(sample_chat.id)

        assert deleted_count == 5

        # Verify chat is empty
        remaining = await repo.chat_messages.get_messages_by_chat(sample_chat.id)
        assert len(remaining) == 0

    async def test_delete_all_messages_empty_chat(self, repo, sample_chat):
        """Test that 0 is returned for empty chat."""
        deleted_count = await repo.chat_messages.delete_all_messages(sample_chat.id)

        assert deleted_count == 0
