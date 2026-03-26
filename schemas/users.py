from pydantic import BaseModel, EmailStr, Field, ConfigDict
import uuid
from typing import Optional
from .base import TimestampSchema

class UserBase(BaseModel):
    """Base fields for User schemas."""
    email: EmailStr
    base_currency: str = Field(default="UAH", min_length=3, max_length=3)

    model_config = ConfigDict(from_attributes=True)

class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, description="Plain text password")

class UserUpdate(BaseModel):
    """Schema for updating user profile (all fields optional)."""
    email: Optional[EmailStr] = None
    base_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    password: Optional[str] = Field(None, min_length=8)

class UserLogin(BaseModel):
    """Schema for user authentication."""
    email: EmailStr
    password: str

class UserRead(UserBase, TimestampSchema):
    """Schema for displaying user data (excludes sensitive fields)."""
    id: uuid.UUID

class Token(BaseModel):
    """Schema for JWT authentication response."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Schema for data stored within the JWT payload."""
    user_id: Optional[str] = None