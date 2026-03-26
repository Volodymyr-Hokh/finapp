from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from db.models import User


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(email=email)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_base_currency(self, user_id: uuid.UUID, currency: str):
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.base_currency = currency.upper()
                await session.flush()
                await session.refresh(user)
                return user
            return None
