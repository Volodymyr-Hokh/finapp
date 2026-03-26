"""
Tests for analytics AI tools.
"""
import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from services.ai_tools import AgentContext
from services.ai_tools.analytics_tools import (
    get_spending_summary,
    get_income_expense_comparison,
    get_category_breakdown,
    get_monthly_trend,
)
from schemas.enums import TransactionType


@pytest.fixture
def mock_repo():
    """Create mock repository container."""
    repo = MagicMock()
    repo.transactions = AsyncMock()
    return repo


@pytest.fixture
def mock_context(mock_repo):
    """Create mock agent context."""
    return AgentContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        repo=mock_repo
    )


def create_mock_transaction(amount, trans_type, category_name=None, trans_date=None):
    """Helper to create mock transactions."""
    txn = MagicMock()
    txn.amount = Decimal(str(amount))
    txn.type = trans_type
    txn.transaction_date = trans_date or date.today()
    if category_name:
        txn.category = MagicMock()
        txn.category.name = category_name
    else:
        txn.category = None
    return txn


class TestGetSpendingSummary:
    """Tests for get_spending_summary tool."""

    @pytest.mark.asyncio
    async def test_returns_spending_summary(self, mock_context):
        """Test getting spending summary."""
        transactions = [
            create_mock_transaction(-100, TransactionType.EXPENSE),
            create_mock_transaction(-50, TransactionType.EXPENSE),
            create_mock_transaction(500, TransactionType.INCOME),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_spending_summary(mock_context)

        assert result["total_income"] == "500.00"
        assert result["total_expenses"] == "150.00"
        assert result["net_change"] == "350.00"
        assert result["transaction_count"] == 3

    @pytest.mark.asyncio
    async def test_uses_date_filters(self, mock_context):
        """Test date filters are applied."""
        mock_context.repo.transactions.get_user_transactions.return_value = []

        await get_spending_summary(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31"
        )

        call_kwargs = mock_context.repo.transactions.get_user_transactions.call_args.kwargs
        assert call_kwargs["from_date"] == date(2024, 1, 1)
        assert call_kwargs["to_date"] == date(2024, 1, 31)

    @pytest.mark.asyncio
    async def test_defaults_to_current_month(self, mock_context):
        """Test defaults to current month if no dates provided."""
        mock_context.repo.transactions.get_user_transactions.return_value = []

        result = await get_spending_summary(mock_context)

        today = date.today()
        assert result["period"]["from"] == str(today.replace(day=1))
        assert result["period"]["to"] == str(today)


class TestGetIncomeExpenseComparison:
    """Tests for get_income_expense_comparison tool."""

    @pytest.mark.asyncio
    async def test_returns_comparison(self, mock_context):
        """Test income vs expense comparison."""
        transactions = [
            create_mock_transaction(-200, TransactionType.EXPENSE),
            create_mock_transaction(-100, TransactionType.EXPENSE),
            create_mock_transaction(1000, TransactionType.INCOME),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_income_expense_comparison(mock_context)

        assert result["income"]["total"] == "1000.00"
        assert result["income"]["count"] == 1
        assert result["expenses"]["total"] == "300.00"
        assert result["expenses"]["count"] == 2
        assert result["net_balance"] == "700.00"
        # Savings rate: (1000 - 300) / 1000 = 70%
        assert result["savings_rate"] == 70.0

    @pytest.mark.asyncio
    async def test_handles_zero_income(self, mock_context):
        """Test handles zero income (no division error)."""
        transactions = [
            create_mock_transaction(-100, TransactionType.EXPENSE),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_income_expense_comparison(mock_context)

        assert result["savings_rate"] == 0


class TestGetCategoryBreakdown:
    """Tests for get_category_breakdown tool."""

    @pytest.mark.asyncio
    async def test_returns_category_breakdown(self, mock_context):
        """Test category breakdown."""
        transactions = [
            create_mock_transaction(-100, TransactionType.EXPENSE, "Food"),
            create_mock_transaction(-50, TransactionType.EXPENSE, "Food"),
            create_mock_transaction(-75, TransactionType.EXPENSE, "Transport"),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_category_breakdown(mock_context, type="expense")

        assert result["total"] == "225.00"
        assert len(result["categories"]) == 2

        # Should be sorted by amount descending
        assert result["categories"][0]["category"] == "Food"
        assert result["categories"][0]["amount"] == "150.00"
        assert result["categories"][1]["category"] == "Transport"

    @pytest.mark.asyncio
    async def test_handles_uncategorized(self, mock_context):
        """Test handles transactions without category."""
        transactions = [
            create_mock_transaction(-100, TransactionType.EXPENSE, None),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_category_breakdown(mock_context, type="expense")

        assert result["categories"][0]["category"] == "Uncategorized"


class TestGetMonthlyTrend:
    """Tests for get_monthly_trend tool."""

    @pytest.mark.asyncio
    async def test_returns_monthly_trend(self, mock_context):
        """Test monthly trend analysis."""
        transactions = [
            create_mock_transaction(-100, TransactionType.EXPENSE, trans_date=date(2024, 1, 15)),
            create_mock_transaction(500, TransactionType.INCOME, trans_date=date(2024, 1, 10)),
            create_mock_transaction(-200, TransactionType.EXPENSE, trans_date=date(2024, 2, 15)),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_monthly_trend(mock_context, months=6, type="both")

        assert "trend" in result
        assert "averages" in result
        assert len(result["trend"]) > 0

    @pytest.mark.asyncio
    async def test_calculates_averages(self, mock_context):
        """Test average calculations."""
        transactions = [
            create_mock_transaction(-100, TransactionType.EXPENSE, trans_date=date(2024, 1, 15)),
            create_mock_transaction(500, TransactionType.INCOME, trans_date=date(2024, 1, 10)),
        ]
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_monthly_trend(mock_context, months=1)

        assert "monthly_income" in result["averages"]
        assert "monthly_expense" in result["averages"]
        assert "monthly_net" in result["averages"]
