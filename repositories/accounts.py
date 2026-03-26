from decimal import Decimal
import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseRepository
from db.models import Account, Transaction


class AccountRepository(BaseRepository[Account]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Account, session)

    async def get_default_for_user(self, user_id: uuid.UUID) -> Optional[Account]:
        """Find the account marked as default for the user."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(user_id=user_id, is_default=True)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_balance(self, id: int, amount_change: Decimal):
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            if account:
                account.balance = account.balance + amount_change
                await session.flush()
                await session.refresh(account)

    async def get_user_accounts(self, user_id: uuid.UUID) -> List[Account]:
        """Get all accounts for a specific user."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(user_id=user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id_and_user(
        self, account_id: int, user_id: uuid.UUID
    ) -> Optional[Account]:
        """Get an account by ID for a specific user."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=account_id, user_id=user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def has_transactions(self, account) -> bool:
        """Check if an account has any transactions."""
        async with self._get_session() as session:
            stmt = (
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.account_id == account.id)
            )
            result = await session.execute(stmt)
            count = result.scalar()
            return count > 0

    async def delete_account(self, account) -> None:
        """Delete an account."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=account.id)
            result = await session.execute(stmt)
            account_to_delete = result.scalar_one()
            await session.delete(account_to_delete)
