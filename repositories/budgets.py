from datetime import datetime, date
from decimal import Decimal
import uuid
import calendar
from typing import Optional, List, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from db.models import Budget, Transaction
from schemas.enums import TransactionType


class BudgetRepository(BaseRepository[Budget]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Budget, session)

    async def get_current_budget(
        self, user_id: uuid.UUID, category_id: int
    ) -> Optional[Budget]:
        now = datetime.now()
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(
                user_id=user_id,
                category_id=category_id,
                month=now.month,
                year=now.year,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_with_category(self, budget_id: int) -> Optional[Budget]:
        """Get a budget with category relationship."""
        async with self._get_session() as session:
            stmt = (
                select(self.model)
                .options(selectinload(Budget.category))
                .filter_by(id=budget_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_budgets(self, user_id: uuid.UUID) -> List[Budget]:
        """Get all budgets for a user with category relationship."""
        async with self._get_session() as session:
            stmt = (
                select(self.model)
                .options(selectinload(Budget.category))
                .filter_by(user_id=user_id)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id_and_user(
        self, budget_id: int, user_id: uuid.UUID
    ) -> Optional[Budget]:
        """Get a budget by ID for a specific user with category relationship."""
        async with self._get_session() as session:
            stmt = (
                select(self.model)
                .options(selectinload(Budget.category))
                .filter_by(id=budget_id, user_id=user_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_budget(self, budget) -> None:
        """Delete a budget."""
        async with self._get_session() as session:
            stmt = select(self.model).filter_by(id=budget.id)
            result = await session.execute(stmt)
            budget_to_delete = result.scalar_one()
            await session.delete(budget_to_delete)

    async def get_spent_amount(
        self,
        user_id: uuid.UUID,
        category_id: int,
        month: int,
        year: int,
    ) -> Tuple[Decimal, int]:
        """
        Calculate total spent for a category in a given month/year period.

        Returns:
            Tuple of (total_spent_amount, transaction_count)
        """
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        async with self._get_session() as session:
            stmt = select(Transaction).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.category_id == category_id,
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.is_deleted == False,
                    Transaction.transaction_date >= first_day,
                    Transaction.transaction_date <= last_day,
                )
            )
            result = await session.execute(stmt)
            transactions = list(result.scalars().all())

        total_spent = sum((abs(t.amount) for t in transactions), Decimal("0"))
        return total_spent, len(transactions)

    async def get_budget_with_progress(
        self, budget_id: int, user_id: uuid.UUID
    ) -> Tuple[Optional[Budget], Decimal, int]:
        """
        Get a budget with its spent amount and transaction count.

        Returns:
            Tuple of (budget, spent_amount, transaction_count) or (None, 0, 0) if not found
        """
        budget = await self.get_by_id_and_user(budget_id, user_id)
        if not budget:
            return None, Decimal("0"), 0

        spent, count = await self.get_spent_amount(
            user_id=user_id,
            category_id=budget.category.id,
            month=budget.month,
            year=budget.year,
        )
        return budget, spent, count

    async def get_user_budgets_with_progress(
        self, user_id: uuid.UUID
    ) -> List[Tuple[Budget, Decimal, int]]:
        """
        Get all user budgets with their spent amounts.
        Optimized to use batch aggregation instead of N+1 queries.

        Returns:
            List of tuples (budget, spent_amount, transaction_count)
        """
        async with self._get_session() as session:
            # Query 1: Get all budgets with categories
            budgets_stmt = (
                select(self.model)
                .options(selectinload(Budget.category))
                .filter_by(user_id=user_id)
            )
            budgets_result = await session.execute(budgets_stmt)
            budgets = list(budgets_result.scalars().all())

            if not budgets:
                return []

            # Query 2: Aggregate all spending data in a single query
            # Get spending grouped by category_id, month, year
            spending_stmt = (
                select(
                    Transaction.category_id,
                    func.extract('month', Transaction.transaction_date).label('month'),
                    func.extract('year', Transaction.transaction_date).label('year'),
                    func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label('total'),
                    func.count(Transaction.id).label('count')
                )
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.type == TransactionType.EXPENSE,
                        Transaction.is_deleted == False,
                    )
                )
                .group_by(
                    Transaction.category_id,
                    func.extract('month', Transaction.transaction_date),
                    func.extract('year', Transaction.transaction_date)
                )
            )

            spending_result = await session.execute(spending_stmt)
            spending_map = {
                (row.category_id, int(row.month), int(row.year)): (
                    Decimal(str(row.total)) if row.total else Decimal("0"),
                    row.count or 0
                )
                for row in spending_result
            }

            # Map spending data to budgets
            results = []
            for budget in budgets:
                key = (budget.category_id, budget.month, budget.year)
                spent, count = spending_map.get(key, (Decimal("0"), 0))
                results.append((budget, spent, count))

            return results
