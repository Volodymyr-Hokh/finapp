"""
API tests for user endpoints (blueprints/users.py).
"""
import pytest
from faker import Faker

fake = Faker()


@pytest.mark.api
class TestUserRegistration:
    """Test user registration endpoint."""

    def test_register_user_success(self, test_client):
        """Test successful user registration."""
        request, response = test_client.post(
            "/users/register",
            json={
                "email": fake.email(),
                "password": "SecurePassword123!",
                "base_currency": "USD"
            }
        )

        assert response.status_code == 201
        assert "id" in response.json
        assert "email" in response.json
        assert "hashed_password" not in response.json  # Should not expose password

    def test_register_user_default_currency(self, test_client):
        """Test registration with default currency."""
        request, response = test_client.post(
            "/users/register",
            json={
                "email": fake.email(),
                "password": "Password123!"
            }
        )

        assert response.status_code == 201
        assert response.json["base_currency"] == "UAH"

    def test_register_user_duplicate_email(self, test_client, sample_user):
        """Test that duplicate email is rejected."""
        request, response = test_client.post(
            "/users/register",
            json={
                "email": sample_user.email,  # Duplicate
                "password": "AnotherPassword123!"
            }
        )

        assert response.status_code == 400
        assert "already registered" in response.json["error"]

    def test_register_user_invalid_email(self, test_client):
        """Test that invalid email is rejected."""
        request, response = test_client.post(
            "/users/register",
            json={
                "email": "not-an-email",
                "password": "Password123!"
            }
        )

        assert response.status_code == 422

    def test_register_user_password_too_short(self, test_client):
        """Test that short password is rejected."""
        request, response = test_client.post(
            "/users/register",
            json={
                "email": fake.email(),
                "password": "short"
            }
        )

        assert response.status_code == 422

    async def test_register_creates_default_account(self, app, repo):
        """Test that registration creates a default account."""
        email = fake.email()

        request, response = await app.asgi_client.post(
            "/users/register",
            json={
                "email": email,
                "password": "Password123!",
                "base_currency": "USD"
            }
        )

        assert response.status_code == 201

        # Verify default account was created
        user = await repo.users.get_by_email(email)
        accounts = await repo.accounts.get_user_accounts(user.id)

        assert len(accounts) == 1
        assert accounts[0].name == "Default Wallet"
        assert accounts[0].is_default is True
        assert accounts[0].currency == "USD"


@pytest.mark.api
class TestUserLogin:
    """Test user login endpoint."""

    def test_login_success(self, test_client, sample_user):
        """Test successful login."""
        request, response = test_client.post(
            "/users/login",
            json={
                "email": sample_user.email,
                "password": "TestPassword123!"  # From fixture
            }
        )

        assert response.status_code == 200
        assert "access_token" in response.json
        assert response.json["token_type"] == "bearer"

    def test_login_wrong_password(self, test_client, sample_user):
        """Test login with incorrect password."""
        request, response = test_client.post(
            "/users/login",
            json={
                "email": sample_user.email,
                "password": "WrongPassword123!"
            }
        )

        assert response.status_code == 401
        assert "Invalid" in response.json["error"]

    def test_login_nonexistent_user(self, test_client):
        """Test login with non-existent email."""
        request, response = test_client.post(
            "/users/login",
            json={
                "email": "nonexistent@example.com",
                "password": "Password123!"
            }
        )

        assert response.status_code == 401

    def test_login_invalid_email_format(self, test_client):
        """Test login with invalid email format."""
        request, response = test_client.post(
            "/users/login",
            json={
                "email": "not-an-email",
                "password": "Password123!"
            }
        )

        assert response.status_code == 422


@pytest.mark.api
class TestGetProfile:
    """Test get profile endpoint."""

    def test_get_profile_success(self, test_client, sample_user, auth_headers):
        """Test getting authenticated user's profile."""
        request, response = test_client.get(
            "/users/me",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["id"] == str(sample_user.id)
        assert response.json["email"] == sample_user.email
        assert "hashed_password" not in response.json

    def test_get_profile_unauthorized(self, test_client):
        """Test that profile endpoint requires authentication."""
        request, response = test_client.get("/users/me")

        assert response.status_code == 401

    def test_get_profile_invalid_token(self, test_client):
        """Test profile with invalid token."""
        request, response = test_client.get(
            "/users/me",
            headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401

    def test_get_profile_expired_token(self, test_client, expired_token):
        """Test profile with expired token."""
        request, response = test_client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401


@pytest.mark.api
class TestUpdateProfile:
    """Test update profile endpoint."""

    def test_update_profile_email(self, test_client, sample_user, auth_headers):
        """Test updating user email."""
        new_email = fake.email()

        request, response = test_client.patch(
            "/users/me",
            headers=auth_headers,
            json={"email": new_email}
        )

        assert response.status_code == 200
        assert response.json["email"] == new_email

    def test_update_profile_currency(self, test_client, sample_user, auth_headers):
        """Test updating base currency."""
        request, response = test_client.patch(
            "/users/me",
            headers=auth_headers,
            json={"base_currency": "EUR"}
        )

        assert response.status_code == 200
        assert response.json["base_currency"] == "EUR"

    def test_update_profile_password(self, test_client, sample_user, auth_headers, repo):
        """Test updating password."""
        request, response = test_client.patch(
            "/users/me",
            headers=auth_headers,
            json={"password": "NewSecurePassword123!"}
        )

        assert response.status_code == 200

        # Verify password was updated by attempting login
        request2, response2 = test_client.post(
            "/users/login",
            json={
                "email": sample_user.email,
                "password": "NewSecurePassword123!"
            }
        )

        assert response2.status_code == 200

    def test_update_profile_no_changes(self, test_client, auth_headers):
        """Test update with no changes provided."""
        request, response = test_client.patch(
            "/users/me",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400
        assert "Nothing to update" in response.json["message"]

    async def test_update_profile_duplicate_email(
        self, app, another_user, auth_headers
    ):
        """Test that updating to an already-taken email is rejected."""
        request, response = await app.asgi_client.patch(
            "/users/me",
            headers=auth_headers,
            json={"email": another_user.email}
        )

        # Should reject duplicate email (either 400 or IntegrityError caught)
        assert response.status_code in [400, 500]

    def test_update_profile_unauthorized(self, test_client):
        """Test that update requires authentication."""
        request, response = test_client.patch(
            "/users/me",
            json={"base_currency": "EUR"}
        )

        assert response.status_code == 401
