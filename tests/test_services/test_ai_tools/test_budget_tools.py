"""
Tests for budget AI tools.
"""
import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from services.ai_tools import AgentContext
from services.ai_tools.budget_tools import (
    get_budgets_with_progress,
    get_budget_details,
    get_category_spending,
    create_budget,
    update_budget_limit,
)


@pytest.fixture
def mock_repo():
    """Create mock repository container."""
    repo = MagicMock()
    repo.budgets = AsyncMock()
    repo.categories = AsyncMock()
    return repo


@pytest.fixture
def mock_context(mock_repo):
    """Create mock agent context."""
    return AgentContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        repo=mock_repo
    )


@pytest.fixture
def mock_budget():
    """Create a mock budget object."""
    budget = MagicMock()
    budget.id = 1
    budget.limit_amount = Decimal("500.00")
    budget.month = date.today().month
    budget.year = date.today().year
    budget.category = MagicMock()
    budget.category.id = 1
    budget.category.name = "Food"
    budget.update = AsyncMock()
    return budget


@pytest.fixture
def mock_category():
    """Create a mock category."""
    category = MagicMock()
    category.id = 1
    category.name = "Food"
    return category


class TestGetBudgetsWithProgress:
    """Tests for get_budgets_with_progress tool."""

    @pytest.mark.asyncio
    async def test_returns_budgets_with_progress(self, mock_context, mock_budget):
        """Test getting budgets with spending progress."""
        # Returns (budget, spent, count) tuples
        mock_context.repo.budgets.get_user_budgets_with_progress.return_value = [
            (mock_budget, Decimal("200.00"), 10)
        ]

        result = await get_budgets_with_progress(mock_context)

        assert result["count"] == 1
        budget = result["budgets"][0]
        assert budget["id"] == 1
        assert budget["spent_amount"] == "200.00"
        assert budget["remaining_amount"] == "300.00"
        assert budget["percentage_used"] == 40.0
        assert budget["status"] == "UNDER"

    @pytest.mark.asyncio
    async def test_calculates_warning_status(self, mock_context, mock_budget):
        """Test warning status when 80%+ spent."""
        mock_context.repo.budgets.get_user_budgets_with_progress.return_value = [
            (mock_budget, Decimal("450.00"), 15)  # 90% spent
        ]

        result = await get_budgets_with_progress(mock_context)

        assert result["budgets"][0]["status"] == "WARNING"

    @pytest.mark.asyncio
    async def test_calculates_over_status(self, mock_context, mock_budget):
        """Test over status when 100%+ spent."""
        mock_context.repo.budgets.get_user_budgets_with_progress.return_value = [
            (mock_budget, Decimal("600.00"), 20)  # 120% spent
        ]

        result = await get_budgets_with_progress(mock_context)

        assert result["budgets"][0]["status"] == "OVER"


class TestGetBudgetDetails:
    """Tests for get_budget_details tool."""

    @pytest.mark.asyncio
    async def test_returns_budget_details(self, mock_context, mock_budget):
        """Test getting budget details."""
        mock_context.repo.budgets.get_budget_with_progress.return_value = (
            mock_budget, Decimal("200.00"), 10
        )

        result = await get_budget_details(mock_context, budget_id=1)

        assert result["id"] == 1
        assert result["limit_amount"] == "500.00"
        assert result["spent_amount"] == "200.00"
        assert "daily_allowance" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent(self, mock_context):
        """Test error when budget not found."""
        mock_context.repo.budgets.get_budget_with_progress.return_value = None

        result = await get_budget_details(mock_context, budget_id=999)

        assert "error" in result


class TestGetCategorySpending:
    """Tests for get_category_spending tool."""

    @pytest.mark.asyncio
    async def test_returns_category_spending(self, mock_context, mock_category):
        """Test getting category spending."""
        mock_context.repo.budgets.get_spent_amount.return_value = (Decimal("150.00"), 5)
        mock_context.repo.categories.get.return_value = mock_category

        result = await get_category_spending(
            mock_context,
            category_id=1,
            month=1,
            year=2024
        )

        assert result["total_spent"] == "150.00"
        assert result["transaction_count"] == 5
        assert result["category_name"] == "Food"


class TestCreateBudget:
    """Tests for create_budget tool."""

    @pytest.mark.asyncio
    async def test_creates_budget(self, mock_context, mock_budget, mock_category):
        """Test creating a budget."""
        mock_context.repo.categories.get.return_value = mock_category
        mock_context.repo.budgets.get_current_budget.return_value = None
        mock_context.repo.budgets.create.return_value = mock_budget

        result = await create_budget(
            mock_context,
            category_id=1,
            limit_amount="500.00",
            month=1,
            year=2024
        )

        assert result["success"] is True
        assert result["budget"]["category"] == "Food"

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_category(self, mock_context):
        """Test error when category not found."""
        mock_context.repo.categories.get.return_value = None

        result = await create_budget(
            mock_context,
            category_id=999,
            limit_amount="500.00",
            month=1,
            year=2024
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_existing_budget(self, mock_context, mock_budget, mock_category):
        """Test error when budget already exists."""
        mock_context.repo.categories.get.return_value = mock_category
        mock_budget.month = 1
        mock_budget.year = 2024
        mock_context.repo.budgets.get_current_budget.return_value = mock_budget

        result = await create_budget(
            mock_context,
            category_id=1,
            limit_amount="500.00",
            month=1,
            year=2024
        )

        assert "error" in result
        assert "already exists" in result["error"]


class TestUpdateBudgetLimit:
    """Tests for update_budget_limit tool."""

    @pytest.mark.asyncio
    async def test_updates_budget_limit(self, mock_context, mock_budget):
        """Test updating budget limit."""
        mock_context.repo.budgets.get_by_id_and_user.return_value = mock_budget

        result = await update_budget_limit(mock_context, budget_id=1, new_limit="600.00")

        assert result["success"] is True
        assert result["old_limit"] == "500.00"
        assert result["new_limit"] == "600.00"
        mock_budget.update.assert_called_once_with(limit_amount=Decimal("600.00"))

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent(self, mock_context):
        """Test error when budget not found."""
        mock_context.repo.budgets.get_by_id_and_user.return_value = None

        result = await update_budget_limit(mock_context, budget_id=999, new_limit="600.00")

        assert "error" in result
