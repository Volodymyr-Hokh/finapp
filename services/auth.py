from datetime import datetime, timedelta, UTC
from functools import wraps

import bcrypt
import jwt
from sanic import json, Request

# --- Password Security ---

def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a stored hash.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

# --- JWT Logic ---

def create_access_token(user_id: str, secret: str, expires_delta: int = 3600) -> str:
    """
    Creates a JWT access token with a sub (subject) and exp (expiration).
    """
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(seconds=expires_delta),
        "iat": datetime.now(UTC)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def get_token_data(request: Request) -> dict | None:
    """
    Decodes the JWT from the request header and returns the payload.
    """
    if not request.token:
        return None

    try:
        payload = jwt.decode(
            request.token, 
            request.app.config.SECRET.get_secret_value(), 
            algorithms=["HS256"]
        )
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# --- Sanic Decorator ---

def protected(f):
    """
    Decorator to protect Sanic endpoints.
    It verifies the token and injects user_id into request.ctx.
    """
    @wraps(f)
    async def decorated_function(request: Request, *args, **kwargs):
        token_data = get_token_data(request)

        if token_data and "sub" in token_data:
            # Inject user_id into the request context for use in blueprints
            # Keep as string since the database stores UUIDs as String(36)
            request.ctx.user_id = token_data["sub"]
            return await f(request, *args, **kwargs)

        return json({
            "error": "UNAUTHORIZED",
            "message": "Invalid or expired token. Please login again."
        }, status=401)

    return decorated_function