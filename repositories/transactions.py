from typing import List, Optional
from datetime import date
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .accounts import AccountRepository
from .categories import CategoryRepository
from .base import BaseRepository
from db.models import Transaction, Tag, Category
from db.session import get_session
from schemas.enums import TransactionType


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession = None):
        super().__init__(Transaction, session)

    async def get_user_transactions(
        self,
        user_id: uuid.UUID,
        include_deleted: bool = False,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        type: Optional[TransactionType] = None,
        account_id: Optional[int] = None,
        category_id: Optional[int] = None,
        tag_name: Optional[str] = None,
        search: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> List[Transaction]:
        async with self._get_session() as session:
            stmt = select(Transaction).where(Transaction.user_id == user_id)

            if not include_deleted:
                stmt = stmt.where(Transaction.is_deleted == False)

            # Apply filters
            if from_date:
                stmt = stmt.where(Transaction.transaction_date >= from_date)
            if to_date:
                stmt = stmt.where(Transaction.transaction_date <= to_date)
            if type:
                stmt = stmt.where(Transaction.type == type)
            if account_id:
                stmt = stmt.where(Transaction.account_id == account_id)
            if category_id:
                stmt = stmt.where(Transaction.category_id == category_id)
            if search:
                stmt = stmt.where(Transaction.description.ilike(f"%{search}%"))

            # Apply sorting
            sort_mapping = {
                "date_asc": Transaction.transaction_date.asc(),
                "date_desc": Transaction.transaction_date.desc(),
                "amount_asc": Transaction.amount.asc(),
                "amount_desc": Transaction.amount.desc(),
            }
            order_by = sort_mapping.get(sort, Transaction.transaction_date.desc())
            stmt = stmt.order_by(order_by)

            # Eager load relationships
            stmt = stmt.options(
                selectinload(Transaction.category),
                selectinload(Transaction.account),
                selectinload(Transaction.tags),
            )

            result = await session.execute(stmt)
            transactions = list(result.scalars().all())

            # Filter by tag name (post-query since tags is M2M)
            if tag_name:
                transactions = [
                    t for t in transactions if any(tag.name == tag_name for tag in t.tags)
                ]

            return transactions

    async def create_with_tags(
        self, user_id: uuid.UUID, data: dict, tag_names: List[str]
    ) -> Transaction:
        """
        Create a transaction.
        If 'account' is not in data, find and assign the user's default account.
        Validates that account and category exist and are accessible to the user.
        All operations use a shared session for atomicity.
        """
        async with get_session() as session:
            # Create session-scoped repositories for atomic operations
            account_repo = AccountRepository(session)
            category_repo = CategoryRepository(session)

            # Validate and resolve account
            if data.get("account") is None:
                default_acc = await account_repo.get_default_for_user(user_id)

                if not default_acc:
                    raise ValueError(
                        "No account found for user. Cannot create transaction."
                    )

                data["account_id"] = default_acc.id
            else:
                # Validate that the provided account exists and belongs to the user
                account = await account_repo.get_by_id_and_user(
                    data["account"], user_id
                )
                if not account:
                    raise ValueError(f"Account with id {data['account']} not found")
                data["account_id"] = account.id

            # Remove 'account' key, we use account_id
            data.pop("account", None)

            # Validate and resolve category if provided
            if data.get("category") is not None:
                category = await category_repo.get(id=data["category"])
                if not category:
                    raise ValueError(f"Category with id {data['category']} not found")
                # Category must be either a system category (user=None) or belong to the user
                if category.user_id is not None and str(category.user_id) != str(user_id):
                    raise ValueError(f"Category with id {data['category']} not found")
                data["category_id"] = category.id

            # Remove 'category' key, we use category_id
            data.pop("category", None)

            # Create the transaction
            transaction = Transaction(user_id=user_id, **data)
            session.add(transaction)
            await session.flush()

            # Handle Many-to-Many tags
            for name in tag_names:
                # Get or create tag
                stmt = select(Tag).where(
                    and_(Tag.name == name, Tag.user_id == str(user_id))
                )
                result = await session.execute(stmt)
                tag = result.scalar_one_or_none()

                if not tag:
                    tag = Tag(name=name, user_id=str(user_id))
                    session.add(tag)
                    await session.flush()

                transaction.tags.append(tag)

            await session.flush()
            await session.refresh(transaction)
            return transaction

    async def update_tags(
        self, transaction_id: int, user_id: uuid.UUID, tag_names: List[str]
    ) -> None:
        """Replace all tags on a transaction with the given tag names."""
        async with get_session() as session:
            # Load transaction with tags
            stmt = (
                select(Transaction)
                .where(and_(Transaction.id == transaction_id, Transaction.user_id == user_id))
                .options(selectinload(Transaction.tags))
            )
            result = await session.execute(stmt)
            transaction = result.scalar_one_or_none()

            if not transaction:
                return

            # Clear existing tags
            transaction.tags.clear()

            # Add new tags
            for name in tag_names:
                tag_stmt = select(Tag).where(
                    and_(Tag.name == name, Tag.user_id == str(user_id))
                )
                tag_result = await session.execute(tag_stmt)
                tag = tag_result.scalar_one_or_none()

                if not tag:
                    tag = Tag(name=name, user_id=str(user_id))
                    session.add(tag)
                    await session.flush()

                transaction.tags.append(tag)

            await session.flush()

    async def soft_delete(self, id: int) -> bool:
        async with self._get_session() as session:
            stmt = select(Transaction).filter_by(id=id)
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if instance:
                instance.is_deleted = True
                await session.flush()
                return True
            return False

    async def get_with_relations(self, transaction_id: int) -> Optional[Transaction]:
        """Get a transaction with all related entities (category, account, tags)."""
        async with self._get_session() as session:
            stmt = (
                select(Transaction)
                .where(Transaction.id == transaction_id)
                .options(
                    selectinload(Transaction.category),
                    selectinload(Transaction.account),
                    selectinload(Transaction.tags),
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self, transaction_id: int, user_id: uuid.UUID
    ) -> Optional[Transaction]:
        """Get a transaction by ID and user with all related entities."""
        async with self._get_session() as session:
            stmt = (
                select(Transaction)
                .where(
                    and_(
                        Transaction.id == transaction_id,
                        Transaction.user_id == user_id,
                    )
                )
                .options(
                    selectinload(Transaction.category),
                    selectinload(Transaction.account),
                    selectinload(Transaction.tags),
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
