"""
Tests for authentication service (services/auth.py).
"""
import pytest
import jwt
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, AsyncMock

from services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_token_data,
    protected
)


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_creates_valid_hash(self):
        """Test that hash_password produces a valid bcrypt hash."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt hash format

    def test_hash_password_produces_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "SamePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_succeeds_with_correct_password(self):
        """Test password verification with correct password."""
        password = "CorrectPassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_fails_with_wrong_password(self):
        """Test password verification fails with incorrect password."""
        password = "CorrectPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_fails_with_empty_password(self):
        """Test password verification fails with empty password."""
        password = "RealPassword123!"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False


@pytest.mark.unit
class TestJWTTokenCreation:
    """Test JWT token creation."""

    def test_create_access_token_returns_valid_jwt(self):
        """Test that create_access_token returns a valid JWT string."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = "test-secret-key"

        token = create_access_token(user_id, secret)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_user_id(self):
        """Test that JWT token contains the correct user_id in 'sub' claim."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = "test-secret-key"

        token = create_access_token(user_id, secret)
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        assert payload["sub"] == user_id

    def test_create_access_token_has_expiration(self):
        """Test that JWT token has an expiration time."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = "test-secret-key"
        expires_delta = 3600

        token = create_access_token(user_id, secret, expires_delta)
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        assert "exp" in payload
        assert "iat" in payload

        # Verify expiration is approximately expires_delta seconds from now
        exp_time = datetime.fromtimestamp(payload["exp"], UTC)
        iat_time = datetime.fromtimestamp(payload["iat"], UTC)
        time_diff = (exp_time - iat_time).total_seconds()

        assert abs(time_diff - expires_delta) < 5  # Allow 5 second tolerance

    def test_create_access_token_custom_expiration(self):
        """Test creating token with custom expiration."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = "test-secret-key"
        custom_expiration = 7200  # 2 hours

        token = create_access_token(user_id, secret, custom_expiration)
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        exp_time = datetime.fromtimestamp(payload["exp"], UTC)
        iat_time = datetime.fromtimestamp(payload["iat"], UTC)
        time_diff = (exp_time - iat_time).total_seconds()

        assert abs(time_diff - custom_expiration) < 5


@pytest.mark.unit
class TestGetTokenData:
    """Test JWT token decoding and validation."""

    def test_get_token_data_returns_valid_payload(self, app):
        """Test extracting payload from valid token."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = app.config.SECRET.get_secret_value()
        token = create_access_token(user_id, secret)

        # Mock request object
        request = Mock()
        request.token = token
        request.app.config.SECRET.get_secret_value.return_value = secret

        payload = get_token_data(request)

        assert payload is not None
        assert payload["sub"] == user_id

    def test_get_token_data_returns_none_without_token(self):
        """Test that missing token returns None."""
        request = Mock()
        request.token = None

        payload = get_token_data(request)

        assert payload is None

    def test_get_token_data_returns_none_for_expired_token(self, app):
        """Test that expired token returns None."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = app.config.SECRET.get_secret_value()

        # Create expired token
        token = create_access_token(user_id, secret, expires_delta=-100)

        request = Mock()
        request.token = token
        request.app.config.SECRET.get_secret_value.return_value = secret

        payload = get_token_data(request)

        assert payload is None

    def test_get_token_data_returns_none_for_invalid_signature(self, app):
        """Test that token with invalid signature returns None."""
        user_id = "12345678-1234-5678-1234-567812345678"
        wrong_secret = "wrong-secret-key"
        token = create_access_token(user_id, wrong_secret)

        request = Mock()
        request.token = token
        request.app.config.SECRET.get_secret_value.return_value = "correct-secret-key"

        payload = get_token_data(request)

        assert payload is None

    def test_get_token_data_returns_none_for_malformed_token(self, app):
        """Test that malformed token returns None."""
        request = Mock()
        request.token = "this-is-not-a-valid-jwt-token"
        request.app.config.SECRET.get_secret_value.return_value = "test-secret"

        payload = get_token_data(request)

        assert payload is None


@pytest.mark.unit
class TestProtectedDecorator:
    """Test the @protected decorator for route protection."""

    @pytest.mark.asyncio
    async def test_protected_allows_valid_token(self, app):
        """Test that @protected allows requests with valid token."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = app.config.SECRET.get_secret_value()
        token = create_access_token(user_id, secret)

        # Create mock request with valid token
        request = Mock()
        request.token = token
        request.app.config.SECRET.get_secret_value.return_value = secret
        request.ctx = Mock()

        # Mock handler function
        handler = AsyncMock(return_value={"message": "success"})
        protected_handler = protected(handler)

        # Call protected handler
        result = await protected_handler(request)

        # Verify handler was called and user_id was set in context
        handler.assert_called_once_with(request)
        assert hasattr(request.ctx, "user_id")
        assert str(request.ctx.user_id) == user_id

    @pytest.mark.asyncio
    async def test_protected_rejects_missing_token(self):
        """Test that @protected rejects requests without token."""
        request = Mock()
        request.token = None

        handler = AsyncMock()
        protected_handler = protected(handler)

        result = await protected_handler(request)

        # Verify handler was NOT called
        handler.assert_not_called()

        # Verify 401 response
        assert result.status == 401
        assert "UNAUTHORIZED" in result.body.decode()

    @pytest.mark.asyncio
    async def test_protected_rejects_expired_token(self, app):
        """Test that @protected rejects expired tokens."""
        user_id = "12345678-1234-5678-1234-567812345678"
        secret = app.config.SECRET.get_secret_value()
        expired_token = create_access_token(user_id, secret, expires_delta=-100)

        request = Mock()
        request.token = expired_token
        request.app.config.SECRET.get_secret_value.return_value = secret

        handler = AsyncMock()
        protected_handler = protected(handler)

        result = await protected_handler(request)

        handler.assert_not_called()
        assert result.status == 401

    @pytest.mark.asyncio
    async def test_protected_rejects_invalid_signature(self, app):
        """Test that @protected rejects tokens with invalid signature."""
        user_id = "12345678-1234-5678-1234-567812345678"
        wrong_secret = "wrong-secret"
        token = create_access_token(user_id, wrong_secret)

        request = Mock()
        request.token = token
        request.app.config.SECRET.get_secret_value.return_value = "correct-secret"

        handler = AsyncMock()
        protected_handler = protected(handler)

        result = await protected_handler(request)

        handler.assert_not_called()
        assert result.status == 401

    @pytest.mark.asyncio
    async def test_protected_rejects_malformed_token(self, app):
        """Test that @protected rejects malformed tokens."""
        request = Mock()
        request.token = "not-a-valid-jwt"
        request.app.config.SECRET.get_secret_value.return_value = "test-secret"

        handler = AsyncMock()
        protected_handler = protected(handler)

        result = await protected_handler(request)

        handler.assert_not_called()
        assert result.status == 401
