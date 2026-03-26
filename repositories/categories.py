from typing import List, Optional
import uuid

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from db.models import Category


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Category, session)

    async def get_available_categories(self, user_id: uuid.UUID) -> List[Category]:
        async with self._get_session() as session:
            stmt = select(self.model).where(
                or_(
                    Category.user_id == user_id,
                    Category.user_id.is_(None),
                )
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def validate_unique_name(
        self, name: str, user_id: uuid.UUID, category_id: Optional[int] = None
    ) -> None:
        """
        Validate that category name is unique for the user and doesn't duplicate system categories.

        Args:
            name: Category name to validate
            user_id: User ID
            category_id: Optional category ID (for updates, to exclude the category being updated)

        Raises:
            ValueError: If name already exists
        """
        async with self._get_session() as session:
            # Check if a system category with this name exists
            stmt = select(self.model).where(
                Category.user_id.is_(None),
                Category.name == name,
            )
            result = await session.execute(stmt)
            system_category = result.scalar_one_or_none()

            if system_category:
                raise ValueError(
                    f"Category '{name}' already exists as a system category"
                )

            # Check if user already has a category with this name
            stmt = select(self.model).where(
                Category.user_id == user_id,
                Category.name == name,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            # Exclude current category if updating
            if category_id:
                if existing and existing.id != category_id:
                    raise ValueError(f"You already have a category named '{name}'")
            else:
                if existing:
                    raise ValueError(f"You already have a category named '{name}'")

    async def get_with_user(self, category_id: int) -> Optional[Category]:
        """Get a category by ID with user relationship."""
        async with self._get_session() as session:
            stmt = (
                select(self.model)
                .options(selectinload(Category.user))
                .filter_by(id=category_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self, category_id: int, user_id: uuid.UUID
    ) -> Optional[Category]:
        """Get a category by ID for a specific user."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=category_id, user_id=user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_category(self, category) -> None:
        """Delete a category."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=category.id)
            result = await session.execute(stmt)
            category_to_delete = result.scalar_one()
            await session.delete(category_to_delete)
