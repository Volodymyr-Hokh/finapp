"""
Tests for specific repository implementations.
"""
import pytest
import uuid
import datetime
from decimal import Decimal

from repositories.users import UserRepository
from repositories.accounts import AccountRepository
from repositories.transactions import TransactionRepository
from repositories.categories import CategoryRepository
from repositories.budgets import BudgetRepository
from repositories.tags import TagRepository
from repositories.ai_logs import AILogRepository
from schemas.enums import TransactionType


@pytest.mark.integration
class TestUserRepository:
    """Test UserRepository."""

    async def test_get_by_email(self, repo, sample_user):
        """Test retrieving user by email."""
        user = await repo.users.get_by_email(sample_user.email)

        assert user is not None
        assert user.id == sample_user.id

    async def test_get_by_email_nonexistent(self, repo):
        """Test that non-existent email returns None."""
        user = await repo.users.get_by_email("nonexistent@example.com")

        assert user is None

    async def test_update_base_currency(self, repo, sample_user):
        """Test updating user's base currency."""
        updated = await repo.users.update_base_currency(sample_user.id, "eur")

        assert updated.base_currency == "EUR"  # Should be uppercased

    async def test_update_base_currency_uppercase(self, repo, sample_user):
        """Test that currency is converted to uppercase."""
        await repo.users.update_base_currency(sample_user.id, "gbp")
        user = await repo.users.get(id=sample_user.id)

        assert user.base_currency == "GBP"


@pytest.mark.integration
class TestAccountRepository:
    """Test AccountRepository."""

    async def test_get_default_for_user(self, repo, sample_user, sample_account):
        """Test getting default account for user."""
        default = await repo.accounts.get_default_for_user(sample_user.id)

        assert default is not None
        assert default.id == sample_account.id
        assert default.is_default is True

    async def test_get_default_returns_none_if_no_default(self, repo, sample_user):
        """Test that None is returned when user has no default account."""
        # Create non-default account
        await repo.accounts.create(
            name="Not Default",
            currency="USD",
            is_default=False,
            user_id=sample_user.id
        )

        default = await repo.accounts.get_default_for_user(sample_user.id)
        assert default is None

    async def test_update_balance(self, repo, sample_account):
        """Test updating account balance."""
        original_balance = sample_account.balance

        await repo.accounts.update_balance(sample_account.id, Decimal("50.00"))

        updated = await repo.accounts.get(id=sample_account.id)
        assert updated.balance == original_balance + Decimal("50.00")

    async def test_update_balance_negative_change(self, repo, sample_account):
        """Test updating balance with negative amount."""
        original_balance = sample_account.balance

        await repo.accounts.update_balance(sample_account.id, Decimal("-25.00"))

        updated = await repo.accounts.get(id=sample_account.id)
        assert updated.balance == original_balance - Decimal("25.00")

    async def test_get_user_accounts(self, repo, sample_user):
        """Test getting all accounts for a user."""
        await repo.accounts.create(name="Account 1", currency="USD", user_id=sample_user.id)
        await repo.accounts.create(name="Account 2", currency="EUR", user_id=sample_user.id)

        accounts = await repo.accounts.get_user_accounts(sample_user.id)

        assert len(accounts) == 2

    async def test_get_by_id_and_user(self, repo, sample_account, sample_user, another_user):
        """Test getting account by ID and user."""
        # Should find account for correct user
        account = await repo.accounts.get_by_id_and_user(sample_account.id, sample_user.id)
        assert account is not None

        # Should not find account for different user
        account = await repo.accounts.get_by_id_and_user(sample_account.id, another_user.id)
        assert account is None


@pytest.mark.integration
class TestTransactionRepository:
    """Test TransactionRepository."""

    async def test_get_user_transactions_excludes_deleted_by_default(self, repo, sample_user, sample_account):
        """Test that deleted transactions are excluded by default."""
        # Create normal transaction
        t1 = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.INCOME,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        # Create deleted transaction
        t2 = await repo.transactions.create(
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today(),
            is_deleted=True
        )

        transactions = await repo.transactions.get_user_transactions(sample_user.id)

        transaction_ids = [t.id for t in transactions]
        assert t1.id in transaction_ids
        assert t2.id not in transaction_ids

    async def test_get_user_transactions_include_deleted(self, repo, sample_user, sample_account):
        """Test including deleted transactions."""
        t1 = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.INCOME,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today(),
            is_deleted=True
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            include_deleted=True
        )

        transaction_ids = [t.id for t in transactions]
        assert t1.id in transaction_ids

    async def test_create_with_tags(self, repo, sample_user, sample_account):
        """Test creating transaction with tags."""
        transaction = await repo.transactions.create_with_tags(
            user_id=sample_user.id,
            data={
                "amount": Decimal("-30.00"),
                "type": TransactionType.EXPENSE,
                "description": "Groceries",
                "transaction_date": datetime.date.today(),
                "account": sample_account.id
            },
            tag_names=["food", "grocery", "weekly"]
        )

        assert transaction.id is not None

        # Verify tags were created and associated by fetching with relations
        full_txn = await repo.transactions.get_with_relations(transaction.id)
        tag_names = {tag.name for tag in full_txn.tags}
        assert tag_names == {"food", "grocery", "weekly"}

    async def test_create_with_tags_uses_default_account(self, repo, sample_user, sample_account):
        """Test that default account is used when none specified."""
        transaction = await repo.transactions.create_with_tags(
            user_id=sample_user.id,
            data={
                "amount": Decimal("200.00"),
                "type": TransactionType.INCOME,
                "transaction_date": datetime.date.today(),
                "account": None  # No account specified
            },
            tag_names=[]
        )

        assert transaction.account_id == sample_account.id

    async def test_create_with_tags_fails_without_account(self, repo, another_user):
        """Test that creating transaction fails when user has no default account."""
        with pytest.raises(ValueError, match="No account found"):
            await repo.transactions.create_with_tags(
                user_id=another_user.id,
                data={
                    "amount": Decimal("100.00"),
                    "type": TransactionType.INCOME,
                    "transaction_date": datetime.date.today(),
                    "account": None
                },
                tag_names=[]
            )

    async def test_soft_delete(self, repo, sample_transaction):
        """Test soft deleting a transaction."""
        result = await repo.transactions.soft_delete(sample_transaction.id)

        assert result is True

        updated = await repo.transactions.get(id=sample_transaction.id)
        assert updated.is_deleted is True

    async def test_get_with_relations(self, repo, sample_transaction):
        """Test getting transaction with all relations loaded."""
        transaction = await repo.transactions.get_with_relations(sample_transaction.id)

        assert transaction is not None
        # Verify relations are loaded (won't cause additional queries)
        assert transaction.account is not None
        assert transaction.category is not None

    async def test_get_by_id_and_user(self, repo, sample_transaction, sample_user, another_user):
        """Test getting transaction by ID and user."""
        # Should find for correct user
        transaction = await repo.transactions.get_by_id_and_user(
            sample_transaction.id,
            sample_user.id
        )
        assert transaction is not None

        # Should not find for different user
        transaction = await repo.transactions.get_by_id_and_user(
            sample_transaction.id,
            another_user.id
        )
        assert transaction is None


@pytest.mark.integration
class TestCategoryRepository:
    """Test CategoryRepository."""

    async def test_get_available_categories_includes_system_and_user(
        self, repo, sample_user, system_category, user_category
    ):
        """Test that available categories includes both system and user categories."""
        categories = await repo.categories.get_available_categories(sample_user.id)

        category_ids = [c.id for c in categories]
        assert system_category.id in category_ids
        assert user_category.id in category_ids

    async def test_get_available_categories_excludes_other_users(
        self, repo, sample_user, another_user
    ):
        """Test that other users' categories are excluded."""
        # Create category for another user
        other_category = await repo.categories.create(
            name="Other User Category",
            user_id=another_user.id
        )

        categories = await repo.categories.get_available_categories(sample_user.id)
        category_ids = [c.id for c in categories]

        assert other_category.id not in category_ids

    async def test_validate_unique_name_rejects_duplicate_user_category(
        self, repo, sample_user, user_category
    ):
        """Test that duplicate user category names are rejected."""
        with pytest.raises(ValueError, match="already have a category"):
            await repo.categories.validate_unique_name(
                user_category.name,
                sample_user.id
            )

    async def test_validate_unique_name_rejects_system_category_name(
        self, repo, sample_user, system_category
    ):
        """Test that system category names cannot be reused."""
        with pytest.raises(ValueError, match="system category"):
            await repo.categories.validate_unique_name(
                system_category.name,
                sample_user.id
            )

    async def test_validate_unique_name_allows_unique_name(self, repo, sample_user):
        """Test that unique name passes validation."""
        # Should not raise
        await repo.categories.validate_unique_name("Unique Category", sample_user.id)

    async def test_validate_unique_name_excludes_current_category_on_update(
        self, repo, sample_user, user_category
    ):
        """Test that current category is excluded when updating."""
        # Should not raise when updating category with same name
        await repo.categories.validate_unique_name(
            user_category.name,
            sample_user.id,
            category_id=user_category.id
        )

    async def test_get_with_user(self, repo, user_category):
        """Test getting category with user relationship loaded."""
        category = await repo.categories.get_with_user(user_category.id)

        assert category is not None
        # With selectinload, user should be loaded
        assert category.user_id is not None

    async def test_get_by_id_and_user(self, repo, user_category, sample_user, another_user):
        """Test getting category by ID and user."""
        # Should find for correct user
        category = await repo.categories.get_by_id_and_user(
            user_category.id,
            sample_user.id
        )
        assert category is not None

        # Should not find for different user
        category = await repo.categories.get_by_id_and_user(
            user_category.id,
            another_user.id
        )
        assert category is None


@pytest.mark.integration
class TestBudgetRepository:
    """Test BudgetRepository."""

    async def test_get_current_budget(self, repo, sample_user, system_category):
        """Test getting current budget for user and category."""
        now = datetime.datetime.now()
        budget = await repo.budgets.create(
            limit_amount=Decimal("500.00"),
            month=now.month,
            year=now.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        retrieved = await repo.budgets.get_current_budget(
            sample_user.id,
            system_category.id
        )

        assert retrieved is not None
        assert retrieved.id == budget.id

    async def test_get_current_budget_returns_none_for_different_month(
        self, repo, sample_user, system_category
    ):
        """Test that budget from different month is not returned."""
        # Create budget for a different month
        await repo.budgets.create(
            limit_amount=Decimal("300.00"),
            month=1,
            year=2020,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        # Should not find budget for current month
        current = await repo.budgets.get_current_budget(
            sample_user.id,
            system_category.id
        )

        # Will be None unless current month is January 2020
        if datetime.datetime.now().month != 1 or datetime.datetime.now().year != 2020:
            assert current is None

    async def test_get_with_category(self, repo, sample_budget):
        """Test getting budget with category relationship loaded."""
        budget = await repo.budgets.get_with_category(sample_budget.id)

        assert budget is not None
        assert budget.category is not None

    async def test_get_user_budgets(self, repo, sample_user, system_category, user_category):
        """Test getting all budgets for a user."""
        await repo.budgets.create(
            limit_amount=Decimal("100.00"),
            month=1,
            year=2024,
            user_id=sample_user.id,
            category_id=system_category.id
        )
        await repo.budgets.create(
            limit_amount=Decimal("200.00"),
            month=2,
            year=2024,
            user_id=sample_user.id,
            category_id=user_category.id
        )

        budgets = await repo.budgets.get_user_budgets(sample_user.id)

        assert len(budgets) == 2

    async def test_get_by_id_and_user(self, repo, sample_budget, sample_user, another_user):
        """Test getting budget by ID and user."""
        # Should find for correct user
        budget = await repo.budgets.get_by_id_and_user(sample_budget.id, sample_user.id)
        assert budget is not None

        # Should not find for different user
        budget = await repo.budgets.get_by_id_and_user(sample_budget.id, another_user.id)
        assert budget is None

    async def test_get_spent_amount_sums_expenses(
        self, repo, sample_user, system_category, sample_account, create_model
    ):
        """Test that get_spent_amount sums expense transactions correctly."""
        from db.models import Transaction

        today = datetime.date.today()

        # Create expense transactions
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )
        await create_model(
            Transaction,
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        spent, count = await repo.budgets.get_spent_amount(
            sample_user.id, system_category.id, today.month, today.year
        )

        assert spent == Decimal("150.00")
        assert count == 2

    async def test_get_spent_amount_excludes_income(
        self, repo, sample_user, system_category, sample_account, create_model
    ):
        """Test that income transactions are not counted in spent amount."""
        from db.models import Transaction

        today = datetime.date.today()

        # Create expense and income
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )
        await create_model(
            Transaction,
            amount=Decimal("500.00"),
            type=TransactionType.INCOME,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        spent, count = await repo.budgets.get_spent_amount(
            sample_user.id, system_category.id, today.month, today.year
        )

        assert spent == Decimal("100.00")
        assert count == 1

    async def test_get_spent_amount_excludes_deleted(
        self, repo, sample_user, system_category, sample_account, create_model
    ):
        """Test that soft-deleted transactions are excluded from spent amount."""
        from db.models import Transaction

        today = datetime.date.today()

        # Create normal and deleted transactions
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            is_deleted=False
        )
        await create_model(
            Transaction,
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            is_deleted=True
        )

        spent, count = await repo.budgets.get_spent_amount(
            sample_user.id, system_category.id, today.month, today.year
        )

        assert spent == Decimal("100.00")
        assert count == 1

    async def test_get_spent_amount_filters_by_category(
        self, repo, sample_user, system_category, user_category, sample_account, create_model
    ):
        """Test that only transactions from the specified category are counted."""
        from db.models import Transaction

        today = datetime.date.today()

        # Transaction in target category
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )
        # Transaction in different category
        await create_model(
            Transaction,
            amount=Decimal("-200.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=user_category.id
        )

        spent, count = await repo.budgets.get_spent_amount(
            sample_user.id, system_category.id, today.month, today.year
        )

        assert spent == Decimal("100.00")
        assert count == 1

    async def test_get_spent_amount_filters_by_month(
        self, repo, sample_user, system_category, sample_account, create_model
    ):
        """Test that only transactions from the specified month are counted."""
        from db.models import Transaction

        today = datetime.date.today()
        last_month = today.replace(day=1) - datetime.timedelta(days=1)

        # Transaction in current month
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )
        # Transaction in previous month
        await create_model(
            Transaction,
            amount=Decimal("-200.00"),
            type=TransactionType.EXPENSE,
            transaction_date=last_month,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        spent, count = await repo.budgets.get_spent_amount(
            sample_user.id, system_category.id, today.month, today.year
        )

        assert spent == Decimal("100.00")
        assert count == 1

    async def test_get_spent_amount_no_transactions(
        self, repo, sample_user, system_category
    ):
        """Test that zero is returned when no transactions exist."""
        today = datetime.date.today()

        spent, count = await repo.budgets.get_spent_amount(
            sample_user.id, system_category.id, today.month, today.year
        )

        assert spent == Decimal("0")
        assert count == 0

    async def test_get_budget_with_progress(
        self, repo, sample_user, system_category, sample_account, create_model
    ):
        """Test getting budget with progress data."""
        from db.models import Transaction

        today = datetime.date.today()
        budget = await repo.budgets.create(
            limit_amount=Decimal("500.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )

        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )

        result_budget, spent, count = await repo.budgets.get_budget_with_progress(
            budget.id, sample_user.id
        )

        assert result_budget is not None
        assert result_budget.id == budget.id
        assert spent == Decimal("100.00")
        assert count == 1

    async def test_get_budget_with_progress_not_found(self, repo, sample_user):
        """Test that None is returned when budget is not found."""
        budget, spent, count = await repo.budgets.get_budget_with_progress(
            99999, sample_user.id
        )

        assert budget is None
        assert spent == Decimal("0")
        assert count == 0

    async def test_get_user_budgets_with_progress(
        self, repo, sample_user, system_category, user_category, sample_account, create_model
    ):
        """Test getting all user budgets with progress."""
        from db.models import Transaction

        today = datetime.date.today()

        # Create budgets
        budget1 = await repo.budgets.create(
            limit_amount=Decimal("500.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=system_category.id
        )
        budget2 = await repo.budgets.create(
            limit_amount=Decimal("300.00"),
            month=today.month,
            year=today.year,
            user_id=sample_user.id,
            category_id=user_category.id
        )

        # Create transactions
        await create_model(
            Transaction,
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id
        )
        await create_model(
            Transaction,
            amount=Decimal("-50.00"),
            type=TransactionType.EXPENSE,
            transaction_date=today,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=user_category.id
        )

        results = await repo.budgets.get_user_budgets_with_progress(sample_user.id)

        assert len(results) == 2

        # Find results by budget ID
        result_dict = {b.id: (b, s, c) for b, s, c in results}

        assert budget1.id in result_dict
        assert result_dict[budget1.id][1] == Decimal("100.00")
        assert result_dict[budget1.id][2] == 1

        assert budget2.id in result_dict
        assert result_dict[budget2.id][1] == Decimal("50.00")
        assert result_dict[budget2.id][2] == 1


@pytest.mark.integration
class TestTagRepository:
    """Test TagRepository."""

    async def test_get_or_create_tags_creates_new_tags(self, repo, sample_user):
        """Test creating new tags."""
        tags = await repo.tags.get_or_create_tags(
            sample_user.id,
            ["work", "urgent", "important"]
        )

        assert len(tags) == 3
        tag_names = {tag.name for tag in tags}
        assert tag_names == {"work", "urgent", "important"}

    async def test_get_or_create_tags_normalizes_case(self, repo, sample_user):
        """Test that tag names are normalized to lowercase."""
        tags = await repo.tags.get_or_create_tags(
            sample_user.id,
            ["WORK", "Personal", "UrgEnt"]
        )

        tag_names = {tag.name for tag in tags}
        assert tag_names == {"work", "personal", "urgent"}

    async def test_get_or_create_tags_reuses_existing(self, repo, sample_user, sample_tag):
        """Test that existing tags are reused."""
        existing_name = sample_tag.name

        tags = await repo.tags.get_or_create_tags(
            sample_user.id,
            [existing_name, "newtag"]
        )

        # Should return 2 tags, one existing and one new
        assert len(tags) == 2
        tag_ids = [tag.id for tag in tags]
        assert sample_tag.id in tag_ids

    async def test_get_user_tags(self, repo, sample_user, sample_tags):
        """Test getting all tags for a user."""
        tags = await repo.tags.get_user_tags(sample_user.id)

        assert len(tags) >= len(sample_tags)
        tag_names = {tag.name for tag in tags}
        expected_names = {tag.name for tag in sample_tags}
        assert expected_names.issubset(tag_names)

    async def test_get_by_name(self, repo, sample_tag, sample_user):
        """Test getting tag by name."""
        tag = await repo.tags.get_by_name(sample_tag.name, sample_user.id)

        assert tag is not None
        assert tag.id == sample_tag.id

    async def test_get_by_name_returns_none_for_nonexistent(self, repo, sample_user):
        """Test that non-existent tag name returns None."""
        tag = await repo.tags.get_by_name("nonexistent", sample_user.id)

        assert tag is None

    async def test_create_tag(self, repo, sample_user):
        """Test creating a new tag."""
        tag = await repo.tags.create_tag("newtag", sample_user.id)

        assert tag.id is not None
        assert tag.name == "newtag"

    async def test_get_by_id(self, repo, sample_tag, sample_user, another_user):
        """Test getting tag by ID and user."""
        # Should find for correct user
        tag = await repo.tags.get_by_id(sample_tag.id, sample_user.id)
        assert tag is not None

        # Should not find for different user
        tag = await repo.tags.get_by_id(sample_tag.id, another_user.id)
        assert tag is None

    async def test_delete_tag(self, repo, sample_user):
        """Test deleting a tag."""
        tag = await repo.tags.create_tag("to_delete", sample_user.id)
        tag_id = tag.id

        await repo.tags.delete_tag(tag)

        deleted = await repo.tags.get(id=tag_id)
        assert deleted is None


@pytest.mark.integration
class TestAILogRepository:
    """Test AILogRepository."""

    async def test_get_recent_logs_returns_limited_results(self, repo, sample_ai_log, sample_user):
        """Test that recent logs are limited correctly."""
        ai_log_repo = AILogRepository()
        logs = await ai_log_repo.get_recent_logs(sample_user.id, limit=10)

        assert len(logs) >= 1
        assert any(log.id == sample_ai_log.id for log in logs)

    async def test_get_recent_logs_orders_by_created_at_desc(self, repo, multiple_ai_logs, sample_user):
        """Test logs are ordered by creation date descending."""
        ai_log_repo = AILogRepository()
        logs = await ai_log_repo.get_recent_logs(sample_user.id, limit=10)

        # Verify ordering - most recent first
        for i in range(len(logs) - 1):
            assert logs[i].created_at >= logs[i + 1].created_at

    async def test_get_recent_logs_respects_custom_limit(self, repo, multiple_ai_logs, sample_user):
        """Test custom limit parameter works."""
        ai_log_repo = AILogRepository()
        logs = await ai_log_repo.get_recent_logs(sample_user.id, limit=2)

        assert len(logs) <= 2

    async def test_get_recent_logs_filters_by_user(
        self, repo, sample_ai_log, sample_user, another_user, create_model
    ):
        """Test logs are filtered by user ID."""
        from db.models import AILog

        # Create log for another user
        other_log = await create_model(
            AILog,
            user_id=another_user.id,
            prompt="Other user prompt",
            response="Other user response",
            ai_model="gpt-4o-mini",
            tokens_used=50
        )

        ai_log_repo = AILogRepository()
        logs = await ai_log_repo.get_recent_logs(sample_user.id, limit=100)

        log_ids = [log.id for log in logs]
        assert sample_ai_log.id in log_ids
        assert other_log.id not in log_ids

    async def test_get_token_usage_stats_sums_tokens(self, repo, multiple_ai_logs, sample_user):
        """Test token usage aggregation."""
        ai_log_repo = AILogRepository()
        total = await ai_log_repo.get_token_usage_stats(sample_user.id)

        # multiple_ai_logs creates 5 logs with 100, 200, 300, 400, 500 tokens
        expected = sum(100 * (i + 1) for i in range(5))
        assert total == expected

    async def test_get_token_usage_stats_returns_zero_for_no_logs(self, repo, another_user):
        """Test returns 0 when no logs exist."""
        ai_log_repo = AILogRepository()
        total = await ai_log_repo.get_token_usage_stats(another_user.id)

        assert total == 0

    async def test_get_token_usage_stats_filters_by_user(
        self, repo, sample_ai_log, sample_user, another_user, create_model
    ):
        """Test token stats are user-specific."""
        from db.models import AILog

        # Create log for another user with different token count
        await create_model(
            AILog,
            user_id=another_user.id,
            prompt="Other prompt",
            response="Other response",
            ai_model="gpt-4o-mini",
            tokens_used=9999
        )

        ai_log_repo = AILogRepository()
        total = await ai_log_repo.get_token_usage_stats(sample_user.id)

        # Should only count sample_user's tokens (100 from sample_ai_log)
        assert total == 100


@pytest.mark.integration
class TestTransactionRepositoryFilters:
    """Test TransactionRepository filter and sort functionality."""

    async def test_get_user_transactions_filters_by_from_date(self, repo, sample_user, sample_account):
        """Test from_date filter works correctly."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        last_week = today - datetime.timedelta(days=7)

        # Create transactions on different dates
        old_txn = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=last_week
        )
        recent_txn = await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=today
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            from_date=yesterday
        )

        txn_ids = [t.id for t in transactions]
        assert recent_txn.id in txn_ids
        assert old_txn.id not in txn_ids

    async def test_get_user_transactions_filters_by_to_date(self, repo, sample_user, sample_account):
        """Test to_date filter works correctly."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        last_week = today - datetime.timedelta(days=7)

        old_txn = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=last_week
        )
        recent_txn = await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=today
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            to_date=yesterday
        )

        txn_ids = [t.id for t in transactions]
        assert old_txn.id in txn_ids
        assert recent_txn.id not in txn_ids

    async def test_get_user_transactions_filters_by_type(self, repo, sample_user, sample_account):
        """Test transaction type filter."""
        income_txn = await repo.transactions.create(
            amount=Decimal("1000.00"),
            type=TransactionType.INCOME,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        expense_txn = await repo.transactions.create(
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            type=TransactionType.INCOME
        )

        txn_ids = [t.id for t in transactions]
        assert income_txn.id in txn_ids
        assert expense_txn.id not in txn_ids

    async def test_get_user_transactions_filters_by_account_id(
        self, repo, sample_user, sample_account, another_account
    ):
        """Test account_id filter."""
        txn1 = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        txn2 = await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=another_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            account_id=sample_account.id
        )

        txn_ids = [t.id for t in transactions]
        assert txn1.id in txn_ids
        assert txn2.id not in txn_ids

    async def test_get_user_transactions_filters_by_category_id(
        self, repo, sample_user, sample_account, system_category, user_category
    ):
        """Test category_id filter."""
        txn1 = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            transaction_date=datetime.date.today()
        )
        txn2 = await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=user_category.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            category_id=system_category.id
        )

        txn_ids = [t.id for t in transactions]
        assert txn1.id in txn_ids
        assert txn2.id not in txn_ids

    async def test_get_user_transactions_filters_by_description_search(
        self, repo, sample_user, sample_account
    ):
        """Test description search filter."""
        txn1 = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            description="Coffee at Starbucks",
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        txn2 = await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            description="Grocery shopping",
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            search="coffee"
        )

        txn_ids = [t.id for t in transactions]
        assert txn1.id in txn_ids
        assert txn2.id not in txn_ids

    async def test_get_user_transactions_sort_date_asc(self, repo, sample_user, sample_account):
        """Test date ascending sort."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=today
        )
        await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=yesterday
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            sort="date_asc"
        )

        # First transaction should have earlier date
        assert transactions[0].transaction_date <= transactions[-1].transaction_date

    async def test_get_user_transactions_sort_date_desc(self, repo, sample_user, sample_account):
        """Test date descending sort."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=yesterday
        )
        await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=today
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            sort="date_desc"
        )

        # First transaction should have later date
        assert transactions[0].transaction_date >= transactions[-1].transaction_date

    async def test_get_user_transactions_sort_amount_asc(self, repo, sample_user, sample_account):
        """Test amount ascending sort."""
        await repo.transactions.create(
            amount=Decimal("500.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            sort="amount_asc"
        )

        amounts = [t.amount for t in transactions]
        assert amounts == sorted(amounts)

    async def test_get_user_transactions_sort_amount_desc(self, repo, sample_user, sample_account):
        """Test amount descending sort."""
        await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        await repo.transactions.create(
            amount=Decimal("500.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            sort="amount_desc"
        )

        amounts = [t.amount for t in transactions]
        assert amounts == sorted(amounts, reverse=True)

    async def test_get_user_transactions_default_sort(self, repo, sample_user, sample_account):
        """Test default sort is date descending."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=yesterday
        )
        await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=today
        )

        transactions = await repo.transactions.get_user_transactions(sample_user.id)

        # Default should be date descending - most recent first
        assert transactions[0].transaction_date >= transactions[-1].transaction_date

    async def test_get_user_transactions_filters_by_tag_name(
        self, repo, sample_user, sample_account, sample_tag
    ):
        """Test tag name filtering."""
        # Create transaction with tag using create_with_tags
        txn_with_tag = await repo.transactions.create_with_tags(
            user_id=sample_user.id,
            data={
                "amount": Decimal("100.00"),
                "type": TransactionType.EXPENSE,
                "account": sample_account.id,
                "transaction_date": datetime.date.today()
            },
            tag_names=[sample_tag.name]
        )

        txn_without_tag = await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            tag_name=sample_tag.name
        )

        txn_ids = [t.id for t in transactions]
        assert txn_with_tag.id in txn_ids
        assert txn_without_tag.id not in txn_ids

    async def test_get_user_transactions_tag_filter_no_match(self, repo, sample_user, sample_account):
        """Test tag filter with no matching tags."""
        await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        transactions = await repo.transactions.get_user_transactions(
            sample_user.id,
            tag_name="nonexistent_tag"
        )

        assert transactions == []

    async def test_soft_delete_returns_false_when_not_found(self, repo):
        """Test soft_delete returns False for non-existent transaction."""
        result = await repo.transactions.soft_delete(999999)

        assert result is False
