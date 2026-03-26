"""
Tests for base repository (repositories/base.py).
"""
import pytest
from decimal import Decimal

from repositories.base import BaseRepository
from db.models import Account


@pytest.mark.integration
class TestBaseRepository:
    """Test generic CRUD operations in BaseRepository."""

    async def test_create(self, repo, sample_user):
        """Test creating an entity."""
        account = await repo.accounts.create(
            name="Test Account",
            currency="USD",
            balance=Decimal("100.00"),
            user_id=sample_user.id
        )

        assert account.id is not None
        assert account.name == "Test Account"

    async def test_get_by_id(self, repo, sample_account):
        """Test retrieving entity by ID."""
        retrieved = await repo.accounts.get(id=sample_account.id)

        assert retrieved is not None
        assert retrieved.id == sample_account.id
        assert retrieved.name == sample_account.name

    async def test_get_returns_none_for_nonexistent(self, repo):
        """Test that get returns None for non-existent ID."""
        result = await repo.accounts.get(id=99999)

        assert result is None

    async def test_get_all_without_filter(self, repo, sample_user):
        """Test retrieving all entities."""
        # Create multiple accounts
        await repo.accounts.create(name="Account 1", currency="USD", user_id=sample_user.id)
        await repo.accounts.create(name="Account 2", currency="EUR", user_id=sample_user.id)

        all_accounts = await repo.accounts.get_all()

        assert len(all_accounts) >= 2

    async def test_get_all_with_user_filter(self, repo, sample_user, another_user):
        """Test retrieving entities filtered by user."""
        # Create accounts for different users
        await repo.accounts.create(name="User1 Account", currency="USD", user_id=sample_user.id)
        await repo.accounts.create(name="User2 Account", currency="EUR", user_id=another_user.id)

        user1_accounts = await repo.accounts.get_all(user_id=sample_user.id)

        assert len(user1_accounts) >= 1
        assert all(acc.user_id == sample_user.id for acc in user1_accounts)

    async def test_update(self, repo, sample_account):
        """Test updating an entity."""
        updated = await repo.accounts.update(
            id=sample_account.id,
            name="Updated Name"
        )

        assert updated.name == "Updated Name"
        assert updated.id == sample_account.id

    async def test_delete(self, repo, sample_user):
        """Test deleting an entity."""
        account = await repo.accounts.create(
            name="To Delete",
            currency="USD",
            user_id=sample_user.id
        )
        account_id = account.id

        result = await repo.accounts.delete(id=account_id)

        assert result is True

        deleted = await repo.accounts.get(id=account_id)
        assert deleted is None
