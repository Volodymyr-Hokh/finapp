"""
Tests for account AI tools.
"""
import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from services.ai_tools import AgentContext
from services.ai_tools.account_tools import (
    get_user_accounts,
    get_default_account,
    get_account_by_id,
    update_account_balance,
    create_account,
)


@pytest.fixture
def mock_repo():
    """Create mock repository container."""
    repo = MagicMock()
    repo.accounts = AsyncMock()
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
def mock_account():
    """Create a mock account object."""
    account = MagicMock()
    account.id = 1
    account.name = "Test Wallet"
    account.balance = Decimal("1000.00")
    account.currency = "UAH"
    account.is_default = True
    return account


class TestGetUserAccounts:
    """Tests for get_user_accounts tool."""

    @pytest.mark.asyncio
    async def test_returns_all_user_accounts(self, mock_context, mock_account):
        """Test getting all user accounts."""
        mock_context.repo.accounts.get_user_accounts.return_value = [mock_account]

        result = await get_user_accounts(mock_context)

        assert result["count"] == 1
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["id"] == 1
        assert result["accounts"][0]["name"] == "Test Wallet"
        assert result["accounts"][0]["balance"] == "1000.00"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_accounts(self, mock_context):
        """Test returns empty list when user has no accounts."""
        mock_context.repo.accounts.get_user_accounts.return_value = []

        result = await get_user_accounts(mock_context)

        assert result["count"] == 0
        assert result["accounts"] == []


class TestGetDefaultAccount:
    """Tests for get_default_account tool."""

    @pytest.mark.asyncio
    async def test_returns_default_account(self, mock_context, mock_account):
        """Test getting default account."""
        mock_context.repo.accounts.get_default_for_user.return_value = mock_account

        result = await get_default_account(mock_context)

        assert result["id"] == 1
        assert result["name"] == "Test Wallet"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_returns_error_when_no_default(self, mock_context):
        """Test returns error when no default account."""
        mock_context.repo.accounts.get_default_for_user.return_value = None

        result = await get_default_account(mock_context)

        assert "error" in result
        assert "No default account" in result["error"]


class TestGetAccountById:
    """Tests for get_account_by_id tool."""

    @pytest.mark.asyncio
    async def test_returns_account_by_id(self, mock_context, mock_account):
        """Test getting account by ID."""
        mock_context.repo.accounts.get_by_id_and_user.return_value = mock_account

        result = await get_account_by_id(mock_context, account_id=1)

        assert result["id"] == 1
        assert result["name"] == "Test Wallet"
        mock_context.repo.accounts.get_by_id_and_user.assert_called_once_with(
            1, mock_context.user_id
        )

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent_account(self, mock_context):
        """Test returns error for nonexistent account."""
        mock_context.repo.accounts.get_by_id_and_user.return_value = None

        result = await get_account_by_id(mock_context, account_id=999)

        assert "error" in result
        assert "999" in result["error"]


class TestUpdateAccountBalance:
    """Tests for update_account_balance tool."""

    @pytest.mark.asyncio
    async def test_updates_balance_successfully(self, mock_context, mock_account):
        """Test updating account balance."""
        mock_context.repo.accounts.get_by_id_and_user.return_value = mock_account

        # Create updated account mock
        updated_account = MagicMock()
        updated_account.balance = Decimal("1100.00")
        mock_context.repo.accounts.get_by_id_and_user.side_effect = [mock_account, updated_account]

        result = await update_account_balance(mock_context, account_id=1, amount_change="100.00")

        assert result["success"] is True
        assert result["old_balance"] == "1000.00"
        assert result["new_balance"] == "1100.00"

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent_account(self, mock_context):
        """Test returns error when account not found."""
        mock_context.repo.accounts.get_by_id_and_user.return_value = None

        result = await update_account_balance(mock_context, account_id=999, amount_change="100.00")

        assert "error" in result


class TestCreateAccount:
    """Tests for create_account tool."""

    @pytest.mark.asyncio
    async def test_creates_account_successfully(self, mock_context, mock_account):
        """Test creating a new account."""
        mock_context.repo.accounts.create.return_value = mock_account

        result = await create_account(
            mock_context,
            name="Test Wallet",
            currency="UAH",
            initial_balance="1000.00",
            is_default=True
        )

        assert result["success"] is True
        assert result["account"]["name"] == "Test Wallet"
        mock_context.repo.accounts.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_default_values(self, mock_context, mock_account):
        """Test creating account with default values."""
        mock_context.repo.accounts.create.return_value = mock_account

        await create_account(mock_context, name="New Account")

        call_kwargs = mock_context.repo.accounts.create.call_args.kwargs
        assert call_kwargs["currency"] == "UAH"
        assert call_kwargs["balance"] == Decimal("0.00")
        assert call_kwargs["is_default"] is False
