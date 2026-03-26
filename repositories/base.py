from contextlib import asynccontextmanager
from typing import TypeVar, Generic, List, Optional, Any, Type, AsyncGenerator
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.config import Base
from db.session import get_session

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession = None):
        self.model = model
        self._injected_session = session

    @asynccontextmanager
    async def _get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Use injected session if available, otherwise create a new one."""
        if self._injected_session is not None:
            # Use injected session without managing its lifecycle
            yield self._injected_session
        else:
            async with get_session() as session:
                yield session

    async def get(self, **kwargs) -> Optional[ModelType]:
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(**kwargs)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all(
        self, user_id: Optional[uuid.UUID] = None, **kwargs
    ) -> List[ModelType]:
        async with self._get_session() as session:
            stmt = select(self.model)
            if user_id is not None:
                stmt = stmt.filter_by(user_id=user_id)
            if kwargs:
                stmt = stmt.filter_by(**kwargs)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        async with self._get_session() as session:
            instance = self.model(**kwargs)
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return instance

    async def update(self, id: Any, **kwargs) -> ModelType:
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=id)
            result = await session.execute(stmt)
            instance = result.scalar_one()

            for key, value in kwargs.items():
                setattr(instance, key, value)

            await session.flush()
            await session.refresh(instance)
            return instance

    async def delete(self, id: Any) -> bool:
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=id)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if instance is None:
                return False
            await session.delete(instance)
            return True
