"""Response schemas for API endpoints."""

from typing import List, Optional
from pydantic import Field
from .base import BaseSchema
from .transactions import TransactionRead
from .accounts import AccountRead
from .categories import CategoryRead
from .budgets import BudgetRead
from .tags import TagRead
from .shared import CategorySummary


class PaginationMeta(BaseSchema):
    """Pagination metadata for list responses."""
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(..., description="Number of items skipped")
    has_more: bool = Field(..., description="Whether more items exist after this page")


class TransactionListResponse(BaseSchema):
    """Response schema for list of transactions."""
    transactions: List[TransactionRead]
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination metadata (included when limit/offset provided)")


class AccountListResponse(BaseSchema):
    """Response schema for list of accounts."""
    accounts: List[AccountRead]
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination metadata (included when limit/offset provided)")


class CategoryListResponse(BaseSchema):
    """Response schema for list of categories."""
    categories: List[CategorySummary]
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination metadata (included when limit/offset provided)")


class BudgetListResponse(BaseSchema):
    """Response schema for list of budgets."""
    budgets: List[BudgetRead]
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination metadata (included when limit/offset provided)")


class TagReadListResponse(BaseSchema):
    """Response schema for list of tags with full details."""
    tags: List[TagRead]
    pagination: Optional[PaginationMeta] = Field(None, description="Pagination metadata (included when limit/offset provided)")
