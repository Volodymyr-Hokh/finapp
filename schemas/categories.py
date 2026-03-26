from pydantic import Field, computed_field
from typing import Optional, Any
import uuid

from .base import BaseSchema, TimestampSchema

class CategoryBase(BaseSchema):
    name: str = Field(..., max_length=50)
    icon: Optional[str] = Field(None, max_length=20)

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=50)
    icon: Optional[str] = Field(None, max_length=20)

class CategoryRead(CategoryBase, TimestampSchema):
    id: int
    # Read user_id directly from the model's FK column (not from lazy-loaded relationship)
    user_id: Optional[str] = None
