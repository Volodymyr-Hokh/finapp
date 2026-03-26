"""Shared schemas for nested objects in API responses."""

from typing import Optional, List, Any, Dict
from .base import BaseSchema


class CategorySummary(BaseSchema):
    """Simplified category for nested responses."""
    id: int
    name: str
    icon: Optional[str] = None


class AccountSummary(BaseSchema):
    """Simplified account for nested responses (only name and currency)."""
    name: str
    currency: str


class ErrorResponse(BaseSchema):
    """Canonical error response schema for all API errors.

    Example:
        {
            "error": "VALIDATION_ERROR",
            "message": "Invalid email format",
            "details": {"field": "email", "value": "invalid"}
        }
    """
    error: str
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationErrorResponse(BaseSchema):
    """Error response for 422 validation errors (Pydantic validation failures).

    Example:
        {
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": [{"loc": ["body", "amount"], "msg": "value is not a valid decimal", "type": "decimal_parsing"}]
        }
    """
    error: str = "VALIDATION_ERROR"
    message: str = "Request validation failed"
    details: Optional[List[Dict[str, Any]]] = None


class UnauthorizedResponse(BaseSchema):
    """Error response for 401 unauthorized access.

    Example:
        {"error": "UNAUTHORIZED", "message": "Invalid or expired token"}
    """
    error: str = "UNAUTHORIZED"
    message: str = "Invalid or expired token"


class MessageResponse(BaseSchema):
    """Standard success message response schema."""
    message: str


class LoginResponse(BaseSchema):
    """Login response with access token."""
    access_token: str
    token_type: str
    expires_in: int


class TagListResponse(BaseSchema):
    """Response schema for list of tag names."""
    tags: List[str]
