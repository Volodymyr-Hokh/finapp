from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from db.models import Tag


class TagRepository(BaseRepository[Tag]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Tag, session)

    async def get_or_create_tags(
        self, user_id: uuid.UUID, names: List[str]
    ) -> List[Tag]:
        tags = []
        async with self._get_session() as session:
            for name in names:
                normalized_name = name.strip().lower()
                stmt = select(self.model).filter_by(
                    name=normalized_name, user_id=user_id
                )
                result = await session.execute(stmt)
                tag = result.scalar_one_or_none()

                if not tag:
                    tag = Tag(name=normalized_name, user_id=user_id)
                    session.add(tag)
                    await session.flush()
                    await session.refresh(tag)

                tags.append(tag)
        return tags

    async def get_user_tags(self, user_id: uuid.UUID) -> List[Tag]:
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(user_id=user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_name(self, name: str, user_id: uuid.UUID) -> Optional[Tag]:
        """Get a tag by name for a specific user."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(name=name, user_id=user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_tag(self, name: str, user_id: uuid.UUID) -> Tag:
        """Create a new tag for a user."""
        async with self._get_session() as session:
            tag = Tag(name=name, user_id=user_id)
            session.add(tag)
            await session.flush()
            await session.refresh(tag)
            return tag

    async def get_by_id(self, tag_id: int, user_id: uuid.UUID) -> Optional[Tag]:
        """Get a tag by ID for a specific user."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=tag_id, user_id=user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_tag(self, tag: Tag) -> None:
        """Delete a tag."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=tag.id)
            result = await session.execute(stmt)
            tag_to_delete = result.scalar_one()
            await session.delete(tag_to_delete)
