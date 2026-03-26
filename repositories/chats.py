from typing import List, Optional
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from db.models import Chat


class ChatRepository(BaseRepository[Chat]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Chat, session)

    async def get_user_chats(
        self,
        user_id: uuid.UUID,
        include_deleted: bool = False,
        limit: Optional[int] = None,
    ) -> List[Chat]:
        """Get all chats for a user, ordered by most recent first."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = select(self.model).where(Chat.user_id == str(user_id))

            if not include_deleted:
                stmt = stmt.where(Chat.is_deleted == False)

            stmt = stmt.order_by(Chat.updated_at.desc())

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id_and_user(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Optional[Chat]:
        """Get a chat by ID for a specific user."""
        async with self._get_session() as session:
            # Convert UUIDs to strings for comparison with String(36) columns
            stmt = select(self.model).where(
                and_(Chat.id == str(chat_id), Chat.user_id == str(user_id))
            )

            if not include_deleted:
                stmt = stmt.where(Chat.is_deleted == False)

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_recent_chats(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[Chat]:
        """Get the most recent chats for a user."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = (
                select(self.model)
                .where(
                    and_(
                        Chat.user_id == str(user_id),
                        Chat.is_deleted == False,
                    )
                )
                .order_by(Chat.updated_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def soft_delete(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Soft delete a chat (sets is_deleted=True)."""
        async with self._get_session() as session:
            # Convert UUIDs to strings for comparison with String(36) columns
            stmt = select(self.model).where(
                and_(
                    Chat.id == str(chat_id),
                    Chat.user_id == str(user_id),
                    Chat.is_deleted == False,
                )
            )
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()
            if chat:
                chat.is_deleted = True
                await session.flush()
                return True
            return False

    async def restore(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Restore a soft-deleted chat."""
        async with self._get_session() as session:
            # Convert UUIDs to strings for comparison with String(36) columns
            stmt = select(self.model).where(
                and_(Chat.id == str(chat_id), Chat.user_id == str(user_id))
            )
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()
            if chat and chat.is_deleted:
                chat.is_deleted = False
                await session.flush()
                return True
            return False

    async def update_name(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
    ) -> Optional[Chat]:
        """Update the name of a chat."""
        async with self._get_session() as session:
            # Convert UUIDs to strings for comparison with String(36) columns
            stmt = select(self.model).where(
                and_(
                    Chat.id == str(chat_id),
                    Chat.user_id == str(user_id),
                    Chat.is_deleted == False,
                )
            )
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()
            if chat:
                chat.name = name
                await session.flush()
                await session.refresh(chat)
                return chat
            return None

    async def create_for_user(
        self,
        user_id: uuid.UUID,
        name: str = "New Chat",
    ) -> Chat:
        """Create a new chat for a user."""
        async with self._get_session() as session:
            # Convert UUID to string for String(36) column
            chat = Chat(user_id=str(user_id), name=name)
            session.add(chat)
            await session.flush()
            await session.refresh(chat)
            return chat

    async def get_chat_count(
        self,
        user_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> int:
        """Get the count of chats for a user."""
        async with self._get_session() as session:
            # Convert UUID to string for comparison with String(36) column
            stmt = select(func.count()).select_from(self.model).where(
                Chat.user_id == str(user_id)
            )

            if not include_deleted:
                stmt = stmt.where(Chat.is_deleted == False)

            result = await session.execute(stmt)
            return result.scalar()

    async def touch(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Update the chat's updated_at timestamp to mark it as recently active."""
        async with self._get_session() as session:
            stmt = select(self.model).where(
                and_(
                    Chat.id == str(chat_id),
                    Chat.user_id == str(user_id),
                    Chat.is_deleted == False,
                )
            )
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()
            if chat:
                # Trigger the before_update listener which sets updated_at
                chat.name = chat.name
                await session.flush()
                return True
            return False
