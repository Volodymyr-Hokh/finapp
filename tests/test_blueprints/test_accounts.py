"""
API tests for account endpoints (blueprints/accounts.py).
"""
import pytest
from decimal import Decimal


@pytest.mark.api
class TestCreateAccount:
    """Test create account endpoint."""

    def test_create_account_success(self, test_client, auth_headers):
        """Test creating an account."""
        request, response = test_client.post(
            "/accounts/",
            headers=auth_headers,
            json={
                "name": "My Wallet",
                "currency": "USD",
                "balance": "100.00",
                "is_default": False
            }
        )

        assert response.status_code == 201
        assert response.json["name"] == "My Wallet"
        assert response.json["currency"] == "USD"
        assert response.json["balance"] == "100.00"

    def test_create_account_with_defaults(self, test_client, auth_headers):
        """Test creating account with default values."""
        request, response = test_client.post(
            "/accounts/",
            headers=auth_headers,
            json={"name": "Simple Wallet"}
        )

        assert response.status_code == 201
        assert response.json["currency"] == "UAH"
        assert response.json["balance"] == "0.00"
        assert response.json["is_default"] is False

    def test_create_account_unauthorized(self, test_client):
        """Test that creating account requires authentication."""
        request, response = test_client.post(
            "/accounts/",
            json={"name": "Wallet"}
        )

        assert response.status_code == 401

    def test_create_second_default_account(
        self, test_client, sample_account, auth_headers
    ):
        """Test creating a second account with is_default=True."""
        # sample_account is already default
        assert sample_account.is_default is True

        request, response = test_client.post(
            "/accounts/",
            headers=auth_headers,
            json={
                "name": "New Default",
                "is_default": True
            }
        )

        # Should succeed (the system accepts the creation)
        assert response.status_code == 201
        assert response.json["is_default"] is True


@pytest.mark.api
class TestListAccounts:
    """Test list accounts endpoint."""

    def test_list_accounts(self, test_client, sample_account, auth_headers):
        """Test listing user's accounts."""
        request, response = test_client.get(
            "/accounts/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "accounts" in response.json
        assert isinstance(response.json["accounts"], list)
        assert len(response.json["accounts"]) >= 1

        account_ids = [acc["id"] for acc in response.json["accounts"]]
        assert sample_account.id in account_ids

    async def test_list_accounts_only_shows_user_accounts(
        self, app, sample_account, another_user, auth_headers, repo
    ):
        """Test that users only see their own accounts."""
        # Create account for another user
        await repo.accounts.create(
            name="Other User Account",
            currency="EUR",
            user_id=another_user.id
        )

        request, response = await app.asgi_client.get(
            "/accounts/",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "accounts" in response.json

        # Should only see own accounts — verify the other user's account is not present
        account_names = [a["name"] for a in response.json["accounts"]]
        assert "Other User Account" not in account_names

    def test_list_accounts_unauthorized(self, test_client):
        """Test that listing accounts requires authentication."""
        request, response = test_client.get("/accounts/")

        assert response.status_code == 401


@pytest.mark.api
class TestGetAccount:
    """Test get account endpoint."""

    def test_get_account_success(self, test_client, sample_account, auth_headers):
        """Test getting a specific account."""
        request, response = test_client.get(
            f"/accounts/{sample_account.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["id"] == sample_account.id
        assert response.json["name"] == sample_account.name

    def test_get_account_not_found(self, test_client, auth_headers):
        """Test getting non-existent account."""
        request, response = test_client.get(
            "/accounts/99999",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json["error"]

    async def test_get_account_different_user(self, app, another_user, auth_headers, repo):
        """Test that users cannot access other users' accounts."""
        # Create account for another user
        other_account = await repo.accounts.create(
            name="Other Account",
            currency="USD",
            user_id=another_user.id
        )

        request, response = await app.asgi_client.get(
            f"/accounts/{other_account.id}",
            headers=auth_headers
        )

        assert response.status_code == 404


@pytest.mark.api
class TestUpdateAccount:
    """Test update account endpoint."""

    def test_update_account_name(self, test_client, sample_account, auth_headers):
        """Test updating account name."""
        request, response = test_client.patch(
            f"/accounts/{sample_account.id}",
            headers=auth_headers,
            json={"name": "Updated Wallet"}
        )

        assert response.status_code == 200
        assert response.json["name"] == "Updated Wallet"

    def test_update_account_balance(self, test_client, sample_account, auth_headers):
        """Test updating account balance."""
        request, response = test_client.patch(
            f"/accounts/{sample_account.id}",
            headers=auth_headers,
            json={"balance": "500.00"}
        )

        assert response.status_code == 200
        assert response.json["balance"] == "500.00"

    def test_update_account_partial(self, test_client, sample_account, auth_headers):
        """Test partial update."""
        original_name = sample_account.name

        request, response = test_client.patch(
            f"/accounts/{sample_account.id}",
            headers=auth_headers,
            json={"currency": "EUR"}
        )

        assert response.status_code == 200
        assert response.json["currency"] == "EUR"
        assert response.json["name"] == original_name

    def test_update_account_no_changes(self, test_client, sample_account, auth_headers):
        """Test update with no changes."""
        request, response = test_client.patch(
            f"/accounts/{sample_account.id}",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400
        assert "No changes" in response.json["message"]

    def test_update_account_not_found(self, test_client, auth_headers):
        """Test updating non-existent account."""
        request, response = test_client.patch(
            "/accounts/99999",
            headers=auth_headers,
            json={"name": "Updated"}
        )

        assert response.status_code == 404


@pytest.mark.api
class TestDeleteAccount:
    """Test delete account endpoint."""

    async def test_delete_account_success(self, app, sample_user, auth_headers, repo):
        """Test deleting an account."""
        # Create an account without transactions
        account = await repo.accounts.create(
            name="To Delete",
            currency="USD",
            user_id=sample_user.id
        )

        request, response = await app.asgi_client.delete(
            f"/accounts/{account.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json["message"]

    def test_delete_account_with_transactions(
        self, test_client, sample_account, sample_transaction, auth_headers
    ):
        """Test that account with transactions cannot be deleted."""
        request, response = test_client.delete(
            f"/accounts/{sample_account.id}",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "existing transactions" in response.json["error"]

    def test_delete_account_not_found(self, test_client, auth_headers):
        """Test deleting non-existent account."""
        request, response = test_client.delete(
            "/accounts/99999",
            headers=auth_headers
        )

        assert response.status_code == 404
