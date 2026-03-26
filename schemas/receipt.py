"""Schemas for receipt/check scanning feature."""
from datetime import date
from typing import Optional, List

from pydantic import Field

from .base import BaseSchema, MoneyDecimal
from .enums import TransactionType


class ReceiptScanResponse(BaseSchema):
    """Response from receipt scanning - extracted data for user confirmation."""

    amount: MoneyDecimal = Field(..., description="Extracted amount (negative for expenses)")
    type: TransactionType
    description: str = Field(..., description="Extracted description")
    transaction_date: Optional[date] = Field(
        None, description="Date from receipt, or null if not found"
    )
    suggested_category: Optional[str] = Field(
        None, description="Suggested category name"
    )
    suggested_tags: List[str] = Field(
        default_factory=list, description="Suggested tags"
    )
    merchant_name: Optional[str] = Field(
        None, description="Merchant/store name if found"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="AI confidence score"
    )
