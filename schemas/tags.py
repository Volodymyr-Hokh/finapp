from pydantic import Field, AliasPath
from typing import Optional, Any
import uuid

from .base import BaseSchema, TimestampSchema


class TagBase(BaseSchema):
    name: str = Field(..., max_length=64, description="Tag name (will be normalized to lowercase)")


class TagCreate(TagBase):
    pass


class TagUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=64, description="Tag name (will be normalized to lowercase)")


class TagRead(TagBase, TimestampSchema):
    id: int
    # Read user_id directly from the model's FK column (not from lazy-loaded relationship)
    # user_id is stored as String(36) in the database
    user_id: Optional[str] = None