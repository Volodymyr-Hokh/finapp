"""
Tests for transaction AI tools.
"""
import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from services.ai_tools import AgentContext
from services.ai_tools.transaction_tools import (
    get_transactions,
    create_transaction,
    get_transaction_by_id,
    delete_transaction,
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


@pytest.fixture
def mock_transaction():
    """Create a mock transaction object."""
    txn = MagicMock()
    txn.id = 1
    txn.amount = Decimal("-50.00")
    txn.type = TransactionType.EXPENSE
    txn.description = "Groceries"
    txn.transaction_date = date.today()
    txn.category = MagicMock()
    txn.category.name = "Food"
    txn.account = MagicMock()
    txn.account.name = "Wallet"
    txn.tags = []
    txn.is_reviewed = False
    txn.created_at = date.today()
    return txn


class TestGetTransactions:
    """Tests for get_transactions tool."""

    @pytest.mark.asyncio
    async def test_returns_transactions(self, mock_context, mock_transaction):
        """Test getting transactions."""
        mock_context.repo.transactions.get_user_transactions.return_value = [mock_transaction]

        result = await get_transactions(mock_context)

        assert result["returned_count"] == 1
        assert result["total_count"] == 1
        assert result["transactions"][0]["id"] == 1
        assert result["transactions"][0]["description"] == "Groceries"

    @pytest.mark.asyncio
    async def test_respects_limit(self, mock_context, mock_transaction):
        """Test limit parameter."""
        transactions = [mock_transaction] * 30
        mock_context.repo.transactions.get_user_transactions.return_value = transactions

        result = await get_transactions(mock_context, limit=10)

        assert result["returned_count"] == 10
        assert result["total_count"] == 30

    @pytest.mark.asyncio
    async def test_passes_filters_to_repo(self, mock_context):
        """Test that filters are passed to repository."""
        mock_context.repo.transactions.get_user_transactions.return_value = []

        await get_transactions(
            mock_context,
            from_date="2024-01-01",
            to_date="2024-01-31",
            type="expense",
            category_id=1
        )

        call_kwargs = mock_context.repo.transactions.get_user_transactions.call_args.kwargs
        assert call_kwargs["from_date"] == date(2024, 1, 1)
        assert call_kwargs["to_date"] == date(2024, 1, 31)
        assert call_kwargs["type"] == TransactionType.EXPENSE
        assert call_kwargs["category_id"] == 1


class TestCreateTransaction:
    """Tests for create_transaction tool."""

    @pytest.mark.asyncio
    async def test_creates_expense_transaction(self, mock_context, mock_transaction):
        """Test creating an expense transaction."""
        mock_context.repo.transactions.create_with_tags.return_value = mock_transaction
        mock_context.repo.transactions.get_with_relations.return_value = mock_transaction

        result = await create_transaction(
            mock_context,
            amount="50.00",
            type="expense",
            description="Groceries"
        )

        assert result["success"] is True
        assert result["transaction"]["description"] == "Groceries"
        call_kwargs = mock_context.repo.transactions.create_with_tags.call_args.kwargs
        # Expense amounts should be negative
        assert call_kwargs["data"]["amount"] == Decimal("-50.00")

    @pytest.mark.asyncio
    async def test_creates_income_transaction(self, mock_context):
        """Test creating an income transaction."""
        income_txn = MagicMock()
        income_txn.id = 2
        income_txn.amount = Decimal("1000.00")
        income_txn.type = TransactionType.INCOME
        income_txn.description = "Salary"
        income_txn.transaction_date = date.today()
        income_txn.category = None
        income_txn.account = MagicMock()
        income_txn.account.name = "Wallet"
        income_txn.tags = []

        mock_context.repo.transactions.create_with_tags.return_value = income_txn
        mock_context.repo.transactions.get_with_relations.return_value = income_txn

        result = await create_transaction(
            mock_context,
            amount="1000.00",
            type="income",
            description="Salary"
        )

        assert result["success"] is True
        assert result["transaction"]["type"] == "income"

    @pytest.mark.asyncio
    async def test_handles_creation_error(self, mock_context):
        """Test handling creation errors."""
        mock_context.repo.transactions.create_with_tags.side_effect = ValueError("Invalid data")

        result = await create_transaction(
            mock_context,
            amount="50.00",
            type="expense",
            description="Test"
        )

        assert "error" in result


class TestGetTransactionById:
    """Tests for get_transaction_by_id tool."""

    @pytest.mark.asyncio
    async def test_returns_transaction(self, mock_context, mock_transaction):
        """Test getting transaction by ID."""
        mock_context.repo.transactions.get_by_id_and_user.return_value = mock_transaction

        result = await get_transaction_by_id(mock_context, transaction_id=1)

        assert result["id"] == 1
        assert result["description"] == "Groceries"

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent(self, mock_context):
        """Test error for nonexistent transaction."""
        mock_context.repo.transactions.get_by_id_and_user.return_value = None

        result = await get_transaction_by_id(mock_context, transaction_id=999)

        assert "error" in result


class TestDeleteTransaction:
    """Tests for delete_transaction tool."""

    @pytest.mark.asyncio
    async def test_deletes_transaction(self, mock_context, mock_transaction):
        """Test deleting a transaction."""
        mock_context.repo.transactions.get_by_id_and_user.return_value = mock_transaction
        mock_context.repo.transactions.soft_delete.return_value = True

        result = await delete_transaction(mock_context, transaction_id=1)

        assert result["success"] is True
        assert "deleted successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent(self, mock_context):
        """Test error when transaction not found."""
        mock_context.repo.transactions.get_by_id_and_user.return_value = None

        result = await delete_transaction(mock_context, transaction_id=999)

        assert "error" in result
