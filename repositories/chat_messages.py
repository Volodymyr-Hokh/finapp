from typing import List, Optional
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from db.models import ChatMessage, Chat


class ChatMessageRepository(BaseRepository[ChatMessage]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(ChatMessage, session)

    async def get_messages_by_chat(
        self,
        chat_id: uuid.UUID,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[ChatMessage]:
        """Get all messages for a chat, ordered by sequence number."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(self.model)
                .filter_by(chat_id=str(chat_id))
                .order_by(ChatMessage.sequence_number.asc())
            )

            if offset:
                stmt = stmt.offset(offset)

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_messages_by_chat_and_user(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: Optional[int] = None,
    ) -> List[ChatMessage]:
        """Get messages for a chat, validating user ownership."""
        async with self._get_session() as session:
            # Convert UUIDs to strings for comparison with String(36) columns
            stmt = select(Chat).where(
                and_(
                    Chat.id == str(chat_id),
                    Chat.user_id == str(user_id),
                    Chat.is_deleted == False,
                )
            )
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()

            if not chat:
                return []

        return await self.get_messages_by_chat(chat_id, limit=limit)

    async def get_latest_messages(
        self,
        chat_id: uuid.UUID,
        limit: int = 50,
    ) -> List[ChatMessage]:
        """Get the most recent messages for a chat (for context window)."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(self.model)
                .filter_by(chat_id=str(chat_id))
                .order_by(ChatMessage.sequence_number.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

        return list(reversed(messages))

    async def get_next_sequence_number(self, chat_id: uuid.UUID) -> int:
        """Get the next sequence number for a new message in a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(self.model)
                .filter_by(chat_id=str(chat_id))
                .order_by(ChatMessage.sequence_number.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            last_message = result.scalar_one_or_none()

            if last_message:
                return last_message.sequence_number + 1
            return 1

    async def create_message(
        self,
        chat_id: uuid.UUID,
        message_json: str,
        role: str,
        token_count: Optional[int] = None,
    ) -> ChatMessage:
        """Create a new message in a chat with auto-incrementing sequence number."""
        sequence_number = await self.get_next_sequence_number(chat_id)

        async with self._get_session() as session:
            # Convert UUID to string for String(36) column
            message = ChatMessage(
                chat_id=str(chat_id),
                message_json=message_json,
                role=role,
                sequence_number=sequence_number,
                token_count=token_count,
            )
            session.add(message)
            await session.flush()
            await session.refresh(message)
            return message

    async def get_message_by_id_and_chat(
        self,
        message_id: int,
        chat_id: uuid.UUID,
    ) -> Optional[ChatMessage]:
        """Get a specific message by ID within a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = select(self.model).filter_by(id=message_id, chat_id=str(chat_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_messages_by_role(
        self,
        chat_id: uuid.UUID,
        role: str,
    ) -> List[ChatMessage]:
        """Get all messages of a specific role in a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(self.model)
                .filter_by(chat_id=str(chat_id), role=role)
                .order_by(ChatMessage.sequence_number.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_message_count(self, chat_id: uuid.UUID) -> int:
        """Get the count of messages in a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(func.count()).select_from(self.model).filter_by(chat_id=str(chat_id))
            )
            result = await session.execute(stmt)
            return result.scalar()

    async def get_total_tokens(self, chat_id: uuid.UUID) -> int:
        """Get the total token count for all messages in a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = select(self.model).filter_by(chat_id=str(chat_id))
            result = await session.execute(stmt)
            messages = list(result.scalars().all())
            return sum(m.token_count or 0 for m in messages)

    async def delete_messages_after_sequence(
        self,
        chat_id: uuid.UUID,
        sequence_number: int,
    ) -> int:
        """Delete all messages after a given sequence number (for conversation rollback)."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = select(self.model).where(
                and_(
                    ChatMessage.chat_id == str(chat_id),
                    ChatMessage.sequence_number > sequence_number,
                )
            )
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            count = len(messages)
            for message in messages:
                await session.delete(message)

            return count

    async def get_last_message(self, chat_id: uuid.UUID) -> Optional[ChatMessage]:
        """Get the most recent message in a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(self.model)
                .filter_by(chat_id=str(chat_id))
                .order_by(ChatMessage.sequence_number.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_all_messages(self, chat_id: uuid.UUID) -> int:
        """Delete all messages in a chat."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = select(self.model).filter_by(chat_id=str(chat_id))
            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            count = len(messages)
            for message in messages:
                await session.delete(message)

            return count
