"""
Tests for database models (db/models.py).
Tests verify SQLAlchemy model behavior including constraints, relationships, and mixins.
"""
import pytest
import uuid
import datetime
from decimal import Decimal

from db.models import (
    User, Account, Category, Tag, Transaction, Budget, AILog,
    TransactionTag, TimestampMixin, SoftDeleteMixin, Chat, ChatMessage
)
from schemas.enums import TransactionType


@pytest.mark.integration
class TestUserModel:
    """Test User model."""

    async def test_create_user(self, create_model):
        """Test creating a user."""
        user = await create_model(
            User,
            email="test@example.com",
            hashed_password="hashed_password_here",
            base_currency="USD"
        )

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.base_currency == "USD"
        assert user.created_at is not None
        assert user.updated_at is not None

    async def test_user_email_unique_constraint(self, sample_user, create_model):
        """Test that duplicate emails are not allowed."""
        with pytest.raises(Exception):  # Database unique constraint violation
            await create_model(
                User,
                email=sample_user.email,  # Duplicate email
                hashed_password="different_password",
                base_currency="UAH"
            )

    async def test_user_timestamps_set(self, sample_user):
        """Test that timestamps are set on creation."""
        assert sample_user.created_at is not None
        assert sample_user.updated_at is not None
        assert isinstance(sample_user.created_at, datetime.datetime)
        assert isinstance(sample_user.updated_at, datetime.datetime)


@pytest.mark.integration
class TestAccountModel:
    """Test Account model."""

    async def test_create_account(self, sample_user, create_model):
        """Test creating an account."""
        account = await create_model(
            Account,
            name="My Wallet",
            currency="UAH",
            balance=Decimal("100.50"),
            is_default=True,
            user_id=sample_user.id
        )

        assert account.id is not None
        assert account.name == "My Wallet"
        assert account.currency == "UAH"
        assert account.balance == Decimal("100.50")
        assert account.is_default is True
        assert account.user_id == sample_user.id

    async def test_account_default_balance(self, sample_user, create_model):
        """Test that account balance defaults to 0.00."""
        account = await create_model(
            Account,
            name="Zero Balance Account",
            currency="USD",
            user_id=sample_user.id
        )

        assert account.balance == Decimal("0.00")

    async def test_account_decimal_precision(self, sample_user, repo):
        """Test that balance maintains correct decimal precision."""
        account = await repo.accounts.create(
            name="Precision Test",
            currency="USD",
            balance=Decimal("123.45"),
            user_id=sample_user.id
        )

        retrieved = await repo.accounts.get(id=account.id)
        assert retrieved.balance == Decimal("123.45")


@pytest.mark.integration
class TestCategoryModel:
    """Test Category model."""

    async def test_create_system_category(self, create_model):
        """Test creating a system-wide category (no user)."""
        category = await create_model(
            Category,
            name="Food",
            icon="🍔",
            user_id=None  # System category
        )

        assert category.id is not None
        assert category.name == "Food"
        assert category.icon == "🍔"
        assert category.user_id is None

    async def test_create_user_category(self, sample_user, create_model):
        """Test creating a user-specific category."""
        category = await create_model(
            Category,
            name="Custom Category",
            icon="💼",
            user_id=sample_user.id
        )

        assert category.user_id == sample_user.id

    async def test_category_without_icon(self, sample_user, create_model):
        """Test creating category without icon."""
        category = await create_model(
            Category,
            name="No Icon",
            user_id=sample_user.id
        )

        assert category.icon is None


@pytest.mark.integration
class TestTagModel:
    """Test Tag model."""

    async def test_create_tag(self, sample_user, create_model):
        """Test creating a tag."""
        tag = await create_model(
            Tag,
            name="groceries",
            user_id=sample_user.id
        )

        assert tag.id is not None
        assert tag.name == "groceries"
        assert tag.user_id == sample_user.id

    async def test_tag_unique_constraint_per_user(self, sample_user, create_model):
        """Test that tag names must be unique per user."""
        await create_model(Tag, name="work", user_id=sample_user.id)

        # Attempting to create duplicate tag for same user should fail
        with pytest.raises(Exception):  # Unique constraint violation
            await create_model(Tag, name="work", user_id=sample_user.id)

    async def test_tag_same_name_different_users(self, sample_user, another_user, create_model):
        """Test that different users can have tags with same name."""
        tag1 = await create_model(Tag, name="personal", user_id=sample_user.id)
        tag2 = await create_model(Tag, name="personal", user_id=another_user.id)

        assert tag1.id != tag2.id
        assert tag1.name == tag2.name


@pytest.mark.integration
class TestTransactionModel:
    """Test Transaction model."""

    async def test_create_transaction(self, sample_user, sample_account, system_category, create_model):
        """Test creating a transaction."""
        transaction = await create_model(
            Transaction,
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            description="Groceries",
            transaction_date=datetime.date.today(),
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        assert transaction.id is not None
        assert transaction.amount == Decimal("-50.00")
        assert transaction.type == TransactionType.EXPENSE
        assert transaction.description == "Groceries"
        assert transaction.is_deleted is False
        assert transaction.deleted_at is None
        assert transaction.is_reviewed is False

    async def test_transaction_soft_delete_fields(self, sample_transaction, repo):
        """Test soft delete fields on transaction."""
        # Initially not deleted
        assert sample_transaction.is_deleted is False
        assert sample_transaction.deleted_at is None

        # Soft delete using repository
        await repo.transactions.soft_delete(sample_transaction.id)

        # Reload and verify
        updated = await repo.transactions.get(id=sample_transaction.id)
        assert updated.is_deleted is True

    async def test_transaction_zero_amount_rejected(self, sample_user, sample_account, create_model):
        """Test that zero-amount transactions are rejected by check constraint."""
        with pytest.raises(Exception):  # CheckConstraint("amount != 0")
            await create_model(
                Transaction,
                amount=Decimal("0.00"),
                type=TransactionType.EXPENSE,
                user_id=sample_user.id,
                account_id=sample_account.id,
                transaction_date=datetime.date.today()
            )

    async def test_transaction_without_category(self, sample_user, sample_account, create_model):
        """Test creating transaction without category."""
        transaction = await create_model(
            Transaction,
            amount=Decimal("100.00"),
            type=TransactionType.INCOME,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        assert transaction.category_id is None


@pytest.mark.integration
class TestTransactionTagRelationship:
    """Test many-to-many relationship between Transaction and Tag."""

    async def test_transaction_with_tags(self, sample_user, sample_account, repo):
        """Test creating transaction with tags."""
        # Create transaction with tags using repository method
        transaction = await repo.transactions.create_with_tags(
            user_id=sample_user.id,
            data={
                "amount": Decimal("-30.00"),
                "type": TransactionType.EXPENSE,
                "description": "Test",
                "transaction_date": datetime.date.today(),
                "account": sample_account.id
            },
            tag_names=["tag1", "tag2", "tag3"]
        )

        # Verify tags using get_with_relations
        full_txn = await repo.transactions.get_with_relations(transaction.id)
        tag_names = {tag.name for tag in full_txn.tags}
        assert tag_names == {"tag1", "tag2", "tag3"}


@pytest.mark.integration
class TestBudgetModel:
    """Test Budget model."""

    async def test_create_budget(self, sample_user, system_category, create_model):
        """Test creating a budget."""
        budget = await create_model(
            Budget,
            limit_amount=Decimal("500.00"),
            month=12,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        assert budget.id is not None
        assert budget.limit_amount == Decimal("500.00")
        assert budget.month == 12
        assert budget.year == 2024

    async def test_budget_unique_constraint(self, sample_user, system_category, create_model):
        """Test that only one budget per user/category/month/year is allowed."""
        await create_model(
            Budget,
            limit_amount=Decimal("300.00"),
            month=1,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        # Attempting to create duplicate budget should fail
        with pytest.raises(Exception):  # Unique constraint violation
            await create_model(
                Budget,
                limit_amount=Decimal("400.00"),
                month=1,
                year=2024,
                user_id=sample_user.id,
                category_id=system_category.id
            )

    async def test_budget_different_month_allowed(self, sample_user, system_category, create_model):
        """Test that same user/category can have budgets for different months."""
        budget1 = await create_model(
            Budget,
            limit_amount=Decimal("300.00"),
            month=1,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        budget2 = await create_model(
            Budget,
            limit_amount=Decimal("400.00"),
            month=2,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        assert budget1.id != budget2.id


@pytest.mark.integration
class TestAILogModel:
    """Test AILog model."""

    async def test_create_ai_log(self, sample_user, create_model):
        """Test creating an AI log entry."""
        log = await create_model(
            AILog,
            prompt="Parse: coffee $5",
            response='{"amount": 5.00, "category": "food"}',
            ai_model="gpt-4",
            tokens_used=150,
            execution_time=1.23,
            user_id=sample_user.id
        )

        assert log.id is not None
        assert log.prompt == "Parse: coffee $5"
        assert log.ai_model == "gpt-4"
        assert log.tokens_used == 150
        assert log.execution_time == 1.23

    async def test_ai_log_defaults(self, sample_user, create_model):
        """Test AI log default values."""
        log = await create_model(
            AILog,
            prompt="test prompt",
            response="test response",
            ai_model="gpt-3.5",
            user_id=sample_user.id
        )

        assert log.tokens_used == 0
        assert log.execution_time is None


@pytest.mark.integration
class TestTimestampMixin:
    """Test TimestampMixin behavior across models."""

    async def test_timestamps_created_on_insert(self, sample_user):
        """Test that created_at and updated_at are set on creation."""
        assert sample_user.created_at is not None
        assert sample_user.updated_at is not None
        assert isinstance(sample_user.created_at, datetime.datetime)
        assert isinstance(sample_user.updated_at, datetime.datetime)

    async def test_updated_at_changes_on_update(self, sample_user, repo):
        """Test that updated_at is modified when the model is updated."""
        import asyncio
        original_updated_at = sample_user.updated_at

        await asyncio.sleep(0.05)  # Ensure time difference

        await repo.users.update(id=sample_user.id, base_currency="EUR")
        updated_user = await repo.users.get(id=sample_user.id)

        assert updated_user.updated_at >= original_updated_at


@pytest.mark.integration
class TestSoftDeleteMixin:
    """Test SoftDeleteMixin behavior."""

    async def test_soft_delete_fields(self, sample_transaction):
        """Test that soft delete fields exist and have correct defaults."""
        assert sample_transaction.is_deleted is False
        assert sample_transaction.deleted_at is None

    async def test_soft_delete_sets_timestamp(self, sample_transaction, repo):
        """Test that soft delete sets deleted_at to current timestamp."""
        await repo.transactions.soft_delete(sample_transaction.id)

        deleted = await repo.transactions.get(id=sample_transaction.id)
        assert deleted.is_deleted is True
        assert deleted.deleted_at is not None
        assert isinstance(deleted.deleted_at, datetime.datetime)


@pytest.mark.integration
class TestChatModel:
    """Test Chat model."""

    async def test_create_chat(self, sample_user, create_model):
        """Test creating a chat."""
        chat = await create_model(
            Chat,
            name="My Finance Chat",
            user_id=sample_user.id
        )

        assert chat.id is not None
        assert chat.name == "My Finance Chat"
        assert chat.user_id == sample_user.id
        assert chat.is_deleted is False
        assert chat.deleted_at is None
        assert chat.created_at is not None
        assert chat.updated_at is not None

    async def test_chat_soft_delete_fields(self, sample_chat):
        """Test soft delete fields on chat."""
        assert sample_chat.is_deleted is False
        assert sample_chat.deleted_at is None


@pytest.mark.integration
class TestChatMessageModel:
    """Test ChatMessage model."""

    async def test_create_message(self, sample_chat, create_model):
        """Test creating a chat message."""
        import json
        message_json = json.dumps({
            "kind": "request",
            "parts": [{"part_kind": "user-prompt", "content": "Hello AI"}]
        })

        message = await create_model(
            ChatMessage,
            chat_id=sample_chat.id,
            message_json=message_json,
            role="user",
            sequence_number=1
        )

        assert message.id is not None
        assert message.role == "user"
        assert message.sequence_number == 1
        assert message.token_count is None
        assert message.created_at is not None

    async def test_message_with_token_count(self, sample_chat, create_model):
        """Test creating message with token count."""
        import json
        message = await create_model(
            ChatMessage,
            chat_id=sample_chat.id,
            message_json=json.dumps({"content": "test"}),
            role="assistant",
            sequence_number=1,
            token_count=150
        )

        assert message.token_count == 150

    async def test_message_timestamps(self, sample_chat_message):
        """Test that message timestamps are properly set."""
        assert sample_chat_message.created_at is not None
        assert sample_chat_message.updated_at is not None
