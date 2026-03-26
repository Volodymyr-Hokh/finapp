"""
API tests for transaction endpoints (blueprints/transactions.py).
"""
import pytest
import datetime
from decimal import Decimal

from schemas.enums import TransactionType


@pytest.mark.api
class TestCreateTransaction:
    """Test create transaction endpoint."""

    def test_create_transaction_success(
        self, test_client, sample_account, system_category, auth_headers
    ):
        """Test creating a transaction."""
        request, response = test_client.post(
            "/transactions/",
            headers=auth_headers,
            json={
                "amount": "-50.00",
                "type": "expense",
                "description": "Groceries",
                "account_id": sample_account.id,
                "category_id": system_category.id,
                "tags": ["food", "weekly"]
            }
        )

        assert response.status_code == 201
        assert response.json["amount"] == "-50.00"
        assert response.json["type"] == "expense"
        assert response.json["description"] == "Groceries"
        assert len(response.json["tags"]) == 2

    def test_create_transaction_uses_default_account(
        self, test_client, sample_account, auth_headers
    ):
        """Test that default account is used when not specified."""
        request, response = test_client.post(
            "/transactions/",
            headers=auth_headers,
            json={
                "amount": "100.00",
                "type": "income",
                "description": "Salary"
            }
        )

        assert response.status_code == 201
        assert response.json["account"]["name"] == sample_account.name

    def test_create_transaction_without_category(
        self, test_client, sample_account, auth_headers
    ):
        """Test creating transaction without category."""
        request, response = test_client.post(
            "/transactions/",
            headers=auth_headers,
            json={
                "amount": "75.00",
                "type": "income",
                "account_id": sample_account.id
            }
        )

        assert response.status_code == 201
        assert response.json["category"] is None

    def test_create_transaction_with_empty_tags(
        self, test_client, sample_account, auth_headers
    ):
        """Test creating transaction with empty tags list."""
        request, response = test_client.post(
            "/transactions/",
            headers=auth_headers,
            json={
                "amount": "-20.00",
                "type": "expense",
                "account_id": sample_account.id,
                "tags": []
            }
        )

        assert response.status_code == 201
        assert response.json["tags"] == []

    def test_create_transaction_unauthorized(self, test_client):
        """Test that creating transaction requires authentication."""
        request, response = test_client.post(
            "/transactions/",
            json={
                "amount": "100.00",
                "type": "income"
            }
        )

        assert response.status_code == 401


@pytest.mark.api
class TestListTransactions:
    """Test list transactions endpoint."""

    def test_list_transactions(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test listing user's transactions."""
        request, response = test_client.get(
            "/transactions/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert isinstance(response.json["transactions"], list)
        assert len(response.json["transactions"]) == 1

    async def test_list_transactions_excludes_deleted(
        self, app, sample_account, sample_user, auth_headers, repo
    ):
        """Test that deleted transactions are excluded."""
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

        request, response = await app.asgi_client.get(
            "/transactions/",
            headers=auth_headers
        )

        assert response.status_code == 200

        transaction_ids = [t["id"] for t in response.json["transactions"]]
        assert t1.id in transaction_ids
        assert t2.id not in transaction_ids

    async def test_list_transactions_only_user_transactions(
        self, app, sample_transaction, another_user, auth_headers, repo
    ):
        """Test that users only see their own transactions."""
        # Create account and transaction for another user
        other_account = await repo.accounts.create(
            name="Other Account",
            currency="USD",
            user_id=another_user.id
        )
        await repo.transactions.create(
            amount=Decimal("200.00"),
            type=TransactionType.INCOME,
            user_id=another_user.id,
            account_id=other_account.id,
            transaction_date=datetime.date.today()
        )

        request, response = await app.asgi_client.get(
            "/transactions/",
            headers=auth_headers
        )

        # Should only see own transactions
        assert response.status_code == 200
        assert sample_transaction.id in [t["id"] for t in response.json["transactions"]]

    def test_list_transactions_unauthorized(self, test_client):
        """Test that listing transactions requires authentication."""
        request, response = test_client.get("/transactions/")

        assert response.status_code == 401

    async def test_list_transactions_filter_by_type(
        self, app, sample_user, sample_account, auth_headers, repo
    ):
        """Test filtering transactions by type."""
        await repo.transactions.create(
            amount=Decimal("500.00"),
            type=TransactionType.INCOME,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        await repo.transactions.create(
            amount=Decimal("-30.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        request, response = await app.asgi_client.get(
            "/transactions/?type=income",
            headers=auth_headers
        )

        assert response.status_code == 200
        for t in response.json["transactions"]:
            assert t["type"] == "income"

    async def test_list_transactions_filter_by_date_range(
        self, app, sample_user, sample_account, auth_headers, repo
    ):
        """Test filtering transactions by date range."""
        await repo.transactions.create(
            amount=Decimal("-20.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date(2024, 6, 15)
        )
        await repo.transactions.create(
            amount=Decimal("-10.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date(2024, 8, 1)
        )

        request, response = await app.asgi_client.get(
            "/transactions/?from_date=2024-06-01&to_date=2024-06-30",
            headers=auth_headers
        )

        assert response.status_code == 200
        for t in response.json["transactions"]:
            assert "2024-06" in t["transaction_date"]

    async def test_list_transactions_filter_by_category(
        self, app, sample_user, sample_account, system_category, auth_headers, repo
    ):
        """Test filtering transactions by category."""
        await repo.transactions.create(
            amount=Decimal("-40.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            category_id=system_category.id,
            transaction_date=datetime.date.today()
        )

        request, response = await app.asgi_client.get(
            f"/transactions/?category_id={system_category.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert len(response.json["transactions"]) >= 1

    def test_list_transactions_invalid_date_format(self, test_client, auth_headers):
        """Test that invalid date format returns 400."""
        request, response = test_client.get(
            "/transactions/?from_date=not-a-date",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "error" in response.json

    def test_list_transactions_invalid_type(self, test_client, auth_headers):
        """Test that invalid transaction type returns 400."""
        request, response = test_client.get(
            "/transactions/?type=transfer",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "error" in response.json

    def test_list_transactions_invalid_account_id(self, test_client, auth_headers):
        """Test that invalid account_id returns 400."""
        request, response = test_client.get(
            "/transactions/?account_id=abc",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "error" in response.json

    def test_list_transactions_invalid_limit(self, test_client, auth_headers):
        """Test that invalid limit returns 400."""
        request, response = test_client.get(
            "/transactions/?limit=abc",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "error" in response.json

    async def test_list_transactions_pagination(
        self, app, sample_user, sample_account, auth_headers, repo
    ):
        """Test pagination returns correct metadata."""
        for i in range(5):
            await repo.transactions.create(
                amount=Decimal(f"-{10 + i}.00"),
                type=TransactionType.EXPENSE,
                user_id=sample_user.id,
                account_id=sample_account.id,
                transaction_date=datetime.date.today()
            )

        request, response = await app.asgi_client.get(
            "/transactions/?limit=2&offset=0",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "pagination" in response.json
        assert len(response.json["transactions"]) == 2
        assert response.json["pagination"]["total"] == 5
        assert response.json["pagination"]["limit"] == 2
        assert response.json["pagination"]["offset"] == 0
        assert response.json["pagination"]["has_more"] is True

    async def test_list_transactions_pagination_last_page(
        self, app, sample_user, sample_account, auth_headers, repo
    ):
        """Test pagination on last page."""
        for i in range(3):
            await repo.transactions.create(
                amount=Decimal(f"-{10 + i}.00"),
                type=TransactionType.EXPENSE,
                user_id=sample_user.id,
                account_id=sample_account.id,
                transaction_date=datetime.date.today()
            )

        request, response = await app.asgi_client.get(
            "/transactions/?limit=10&offset=0",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["pagination"]["has_more"] is False

    async def test_list_transactions_sort_by_amount(
        self, app, sample_user, sample_account, auth_headers, repo
    ):
        """Test sorting transactions by amount."""
        await repo.transactions.create(
            amount=Decimal("-100.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )
        await repo.transactions.create(
            amount=Decimal("-5.00"),
            type=TransactionType.EXPENSE,
            user_id=sample_user.id,
            account_id=sample_account.id,
            transaction_date=datetime.date.today()
        )

        request, response = await app.asgi_client.get(
            "/transactions/?sort=amount_asc",
            headers=auth_headers
        )

        assert response.status_code == 200
        amounts = [Decimal(t["amount"]) for t in response.json["transactions"]]
        assert amounts == sorted(amounts)


@pytest.mark.api
class TestGetTransaction:
    """Test get transaction endpoint."""

    def test_get_transaction_success(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test getting a specific transaction."""
        request, response = test_client.get(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["id"] == sample_transaction.id
        assert response.json["description"] == sample_transaction.description

    async def test_get_transaction_includes_relations(
        self, app, sample_transaction, sample_tag, auth_headers, setup_database
    ):
        """Test that transaction includes related entities."""
        from db.models import Transaction
        
        # Add tag to transaction within a session
        async with setup_database() as session:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            stmt = select(Transaction).options(selectinload(Transaction.tags)).filter_by(id=sample_transaction.id)
            result = await session.execute(stmt)
            tx = result.scalar_one()
            tx.tags.append(sample_tag)
            await session.commit()

        request, response = await app.asgi_client.get(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "account" in response.json
        assert "category" in response.json
        assert len(response.json["tags"]) == 1

    def test_get_transaction_not_found(self, test_client, auth_headers):
        """Test getting non-existent transaction."""
        request, response = test_client.get(
            "/transactions/99999",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_get_transaction_different_user(
        self, app, another_user, auth_headers, repo
    ):
        """Test that users cannot access other users' transactions."""
        other_account = await repo.accounts.create(
            name="Other Account",
            currency="USD",
            user_id=another_user.id
        )
        other_transaction = await repo.transactions.create(
            amount=Decimal("100.00"),
            type=TransactionType.INCOME,
            user_id=another_user.id,
            account_id=other_account.id,
            transaction_date=datetime.date.today()
        )

        request, response = await app.asgi_client.get(
            f"/transactions/{other_transaction.id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestUpdateTransaction:
    """Test update transaction endpoint."""

    def test_update_transaction_amount(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test updating transaction amount."""
        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={"amount": "-75.00"}
        )

        assert response.status_code == 200
        assert response.json["amount"] == "-75.00"

    def test_update_transaction_description(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test updating transaction description."""
        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={"description": "Updated description"}
        )

        assert response.status_code == 200
        assert response.json["description"] == "Updated description"

    def test_update_transaction_mark_reviewed(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test marking transaction as reviewed."""
        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={"is_reviewed": True}
        )

        assert response.status_code == 200
        assert response.json["is_reviewed"] is True

    def test_update_transaction_partial(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test partial update."""
        original_amount = sample_transaction.amount

        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={"description": "Partial update"}
        )

        assert response.status_code == 200
        assert response.json["description"] == "Partial update"
        assert Decimal(response.json["amount"]) == original_amount

    def test_update_transaction_no_changes(
        self, test_client, sample_transaction, auth_headers
    ):
        """Test update with no changes."""
        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400

    def test_update_transaction_not_found(self, test_client, auth_headers):
        """Test updating non-existent transaction."""
        request, response = test_client.patch(
            "/transactions/99999",
            headers=auth_headers,
            json={"amount": "100.00"}
        )

        assert response.status_code == 404

    def test_update_transaction_category(
        self, test_client, sample_transaction, user_category, auth_headers
    ):
        """Test updating transaction category."""
        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={"category_id": user_category.id}
        )

        assert response.status_code == 200
        assert response.json["category"]["name"] == user_category.name

    def test_update_transaction_account(
        self, test_client, sample_transaction, another_account, auth_headers
    ):
        """Test updating transaction account."""
        request, response = test_client.patch(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers,
            json={"account_id": another_account.id}
        )

        assert response.status_code == 200
        assert response.json["account"]["name"] == another_account.name


@pytest.mark.api
class TestDeleteTransaction:
    """Test delete transaction endpoint (soft delete)."""

    async def test_delete_transaction_success(
        self, app, sample_transaction, auth_headers, repo
    ):
        """Test soft deleting a transaction."""
        request, response = await app.asgi_client.delete(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json["message"]

        # Verify soft delete
        deleted = await repo.transactions.get(id=sample_transaction.id)
        assert deleted.is_deleted is True

    async def test_delete_transaction_already_deleted(
        self, app, sample_transaction, auth_headers, repo
    ):
        """Test deleting already deleted transaction."""
        # Soft delete first
        await repo.transactions.soft_delete(sample_transaction.id)

        request, response = await app.asgi_client.delete(
            f"/transactions/{sample_transaction.id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_transaction_not_found(self, test_client, auth_headers):
        """Test deleting non-existent transaction."""
        request, response = test_client.delete(
            "/transactions/99999",
            headers=auth_headers
        )

        assert response.status_code == 404
