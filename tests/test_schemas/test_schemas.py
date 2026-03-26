"""
Tests for Pydantic schema validation.
"""
import pytest
import uuid
import datetime
from decimal import Decimal
from pydantic import ValidationError

from schemas.users import UserCreate, UserUpdate, UserLogin, UserRead
from schemas.accounts import AccountCreate, AccountUpdate, AccountRead
from schemas.transactions import (
    TransactionCreate, TransactionUpdate, TransactionRead, TransactionAIRequest
)
from schemas.categories import CategoryCreate, CategoryUpdate, CategoryRead
from schemas.budgets import BudgetCreate, BudgetUpdate, BudgetRead
from schemas.tags import TagCreate, TagUpdate, TagRead
from schemas.enums import TransactionType


@pytest.mark.unit
class TestUserSchemas:
    """Test User schema validation."""

    def test_user_create_valid(self):
        """Test creating valid UserCreate schema."""
        user = UserCreate(
            email="test@example.com",
            password="SecurePassword123!",
            base_currency="USD"
        )

        assert user.email == "test@example.com"
        assert user.password == "SecurePassword123!"
        assert user.base_currency == "USD"

    def test_user_create_default_currency(self):
        """Test default base_currency is UAH."""
        user = UserCreate(
            email="test@example.com",
            password="Password123!"
        )

        assert user.base_currency == "UAH"

    def test_user_create_invalid_email(self):
        """Test that invalid email is rejected."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="not-an-email",
                password="Password123!"
            )

    def test_user_create_password_too_short(self):
        """Test that password must be at least 8 characters."""
        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                password="short"
            )

    def test_user_create_missing_password(self):
        """Test that password is required."""
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com")

    def test_user_update_all_optional(self):
        """Test that all UserUpdate fields are optional."""
        user = UserUpdate()

        assert user.email is None
        assert user.password is None
        assert user.base_currency is None

    def test_user_update_partial(self):
        """Test partial update."""
        user = UserUpdate(base_currency="EUR")

        assert user.base_currency == "EUR"
        assert user.email is None

    def test_user_login_valid(self):
        """Test valid login schema."""
        login = UserLogin(
            email="test@example.com",
            password="Password123!"
        )

        assert login.email == "test@example.com"
        assert login.password == "Password123!"

    def test_user_read_serialization(self, sample_user):
        """Test reading user data."""
        user_read = UserRead.model_validate(sample_user)

        # user_read.id is UUID, sample_user.id is String(36)
        assert str(user_read.id) == sample_user.id
        assert user_read.email == sample_user.email
        assert user_read.base_currency == sample_user.base_currency


@pytest.mark.unit
class TestAccountSchemas:
    """Test Account schema validation."""

    def test_account_create_valid(self):
        """Test valid account creation."""
        account = AccountCreate(
            name="My Wallet",
            currency="USD",
            balance=Decimal("100.00"),
            is_default=True
        )

        assert account.name == "My Wallet"
        assert account.currency == "USD"
        assert account.balance == Decimal("100.00")
        assert account.is_default is True

    def test_account_create_defaults(self):
        """Test default values."""
        account = AccountCreate(name="Wallet")

        assert account.currency == "UAH"
        assert account.balance == Decimal("0.00")
        assert account.is_default is False

    def test_account_create_name_required(self):
        """Test that name is required."""
        with pytest.raises(ValidationError):
            AccountCreate()

    def test_account_update_all_optional(self):
        """Test that all update fields are optional."""
        update = AccountUpdate()

        assert update.name is None
        assert update.currency is None
        assert update.balance is None

    def test_account_update_partial(self):
        """Test partial update."""
        update = AccountUpdate(name="New Name", balance=Decimal("500.00"))

        assert update.name == "New Name"
        assert update.balance == Decimal("500.00")
        assert update.currency is None

    def test_account_read_serialization(self, sample_account):
        """Test serializing account to read schema."""
        account_read = AccountRead.model_validate(sample_account)

        assert account_read.id == sample_account.id
        assert account_read.name == sample_account.name
        assert account_read.balance == sample_account.balance


@pytest.mark.unit
class TestTransactionSchemas:
    """Test Transaction schema validation."""

    def test_transaction_create_valid(self):
        """Test valid transaction creation."""
        transaction = TransactionCreate(
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            description="Groceries",
            account=1,
            category=2,
            tags=["food", "weekly"]
        )

        assert transaction.amount == Decimal("-50.00")
        assert transaction.type == TransactionType.EXPENSE
        assert transaction.description == "Groceries"
        assert transaction.account == 1
        assert transaction.category == 2
        assert transaction.tags == ["food", "weekly"]

    def test_transaction_create_defaults(self):
        """Test default values."""
        transaction = TransactionCreate(
            amount=Decimal("100.00"),
            type=TransactionType.INCOME
        )

        assert transaction.description is None
        assert transaction.account is None
        assert transaction.category is None
        assert transaction.tags == []
        assert transaction.transaction_date == datetime.date.today()

    def test_transaction_create_invalid_type(self):
        """Test that invalid transaction type is rejected."""
        with pytest.raises(ValidationError):
            TransactionCreate(
                amount=Decimal("100.00"),
                type="invalid_type"
            )

    def test_transaction_create_validation_alias(self):
        """Test that validation aliases work."""
        # Should accept both 'account' and 'account_id'
        transaction = TransactionCreate(
            amount=Decimal("50.00"),
            type=TransactionType.INCOME,
            account_id=5
        )

        assert transaction.account == 5

    def test_transaction_update_all_optional(self):
        """Test that all update fields are optional."""
        update = TransactionUpdate()

        assert update.amount is None
        assert update.type is None
        assert update.description is None

    def test_transaction_update_partial(self):
        """Test partial update."""
        update = TransactionUpdate(
            amount=Decimal("75.00"),
            is_reviewed=True
        )

        assert update.amount == Decimal("75.00")
        assert update.is_reviewed is True
        assert update.type is None

    def test_transaction_ai_request_valid(self):
        """Test AI request schema."""
        request = TransactionAIRequest(prompt="coffee 5 dollars")

        assert request.prompt == "coffee 5 dollars"

    def test_transaction_ai_request_too_short(self):
        """Test that prompt must be at least 2 characters."""
        with pytest.raises(ValidationError):
            TransactionAIRequest(prompt="a")


@pytest.mark.unit
class TestCategorySchemas:
    """Test Category schema validation."""

    def test_category_create_valid(self):
        """Test valid category creation."""
        category = CategoryCreate(
            name="Food",
            icon="🍔"
        )

        assert category.name == "Food"
        assert category.icon == "🍔"

    def test_category_create_without_icon(self):
        """Test creating category without icon."""
        category = CategoryCreate(name="Transport")

        assert category.name == "Transport"
        assert category.icon is None

    def test_category_create_name_required(self):
        """Test that name is required."""
        with pytest.raises(ValidationError):
            CategoryCreate()

    def test_category_update_all_optional(self):
        """Test that all update fields are optional."""
        update = CategoryUpdate()

        assert update.name is None
        assert update.icon is None

    def test_category_update_partial(self):
        """Test partial update."""
        update = CategoryUpdate(name="Updated Name")

        assert update.name == "Updated Name"
        assert update.icon is None

    def test_category_read_serialization(self, user_category):
        """Test serializing category."""
        category_read = CategoryRead.model_validate(user_category)

        assert category_read.id == user_category.id
        assert category_read.name == user_category.name
        # Compare against user_id directly (user relationship is lazy-loaded)
        assert category_read.user_id == user_category.user_id


@pytest.mark.unit
class TestBudgetSchemas:
    """Test Budget schema validation."""

    def test_budget_create_valid(self):
        """Test valid budget creation."""
        budget = BudgetCreate(
            limit_amount=Decimal("500.00"),
            category=1,
            month=12,
            year=2024
        )

        assert budget.limit_amount == Decimal("500.00")
        assert budget.category == 1
        assert budget.month == 12
        assert budget.year == 2024

    def test_budget_create_validation_alias(self):
        """Test that category_id alias works."""
        budget = BudgetCreate(
            limit_amount=Decimal("300.00"),
            category_id=2,
            month=6,
            year=2024
        )

        assert budget.category == 2

    def test_budget_create_month_validation(self):
        """Test that month must be between 1 and 12."""
        with pytest.raises(ValidationError):
            BudgetCreate(
                limit_amount=Decimal("100.00"),
                category=1,
                month=13,  # Invalid
                year=2024
            )

        with pytest.raises(ValidationError):
            BudgetCreate(
                limit_amount=Decimal("100.00"),
                category=1,
                month=0,  # Invalid
                year=2024
            )

    def test_budget_create_all_required(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            BudgetCreate()

    def test_budget_update_all_optional(self):
        """Test that all update fields are optional."""
        update = BudgetUpdate()

        assert update.limit_amount is None
        assert update.category is None
        assert update.month is None
        assert update.year is None

    def test_budget_update_partial(self):
        """Test partial update."""
        update = BudgetUpdate(limit_amount=Decimal("600.00"))

        assert update.limit_amount == Decimal("600.00")
        assert update.month is None


@pytest.mark.unit
class TestTagSchemas:
    """Test Tag schema validation."""

    def test_tag_create_valid(self):
        """Test valid tag creation."""
        tag = TagCreate(name="groceries")

        assert tag.name == "groceries"

    def test_tag_create_name_required(self):
        """Test that name is required."""
        with pytest.raises(ValidationError):
            TagCreate()

    def test_tag_update_optional(self):
        """Test that update name is optional."""
        update = TagUpdate()

        assert update.name is None

    def test_tag_update_with_name(self):
        """Test updating tag name."""
        update = TagUpdate(name="updated")

        assert update.name == "updated"

    def test_tag_read_serialization(self, sample_tag):
        """Test serializing tag."""
        tag_read = TagRead.model_validate(sample_tag)

        assert tag_read.id == sample_tag.id
        assert tag_read.name == sample_tag.name
        # Compare against user_id directly (user relationship is lazy-loaded)
        assert tag_read.user_id == sample_tag.user_id


@pytest.mark.unit
class TestEnums:
    """Test enum validation."""

    def test_transaction_type_values(self):
        """Test TransactionType enum values."""
        assert TransactionType.INCOME == "income"
        assert TransactionType.EXPENSE == "expense"

    def test_transaction_type_from_string(self):
        """Test creating TransactionType from string."""
        income = TransactionType("income")
        expense = TransactionType("expense")

        assert income == TransactionType.INCOME
        assert expense == TransactionType.EXPENSE

    def test_transaction_type_invalid_value(self):
        """Test that invalid value raises error."""
        with pytest.raises(ValueError):
            TransactionType("invalid")
