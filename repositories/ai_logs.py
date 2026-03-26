import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from db.models import AILog


class AILogRepository(BaseRepository[AILog]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(AILog, session)

    async def get_recent_logs(self, user_id: uuid.UUID, limit: int = 10) -> List[AILog]:
        async with self._get_session() as session:
            stmt = (
                select(self.model)
                .filter_by(user_id=user_id)
                .order_by(AILog.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_token_usage_stats(self, user_id: uuid.UUID) -> int:
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(user_id=user_id)
            result = await session.execute(stmt)
            logs = list(result.scalars().all())
            return sum(log.tokens_used for log in logs)
