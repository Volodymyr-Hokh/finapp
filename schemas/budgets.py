from enum import Enum
from pydantic import Field
from decimal import Decimal
from typing import Optional

from .base import BaseSchema, TimestampSchema, MoneyDecimal
from .shared import CategorySummary


class BudgetStatus(str, Enum):
    """Budget status based on percentage used."""
    UNDER = "under"      # < 80% used
    WARNING = "warning"  # 80-100% used
    OVER = "over"        # > 100% used


class BudgetCreate(BaseSchema):
    limit_amount: MoneyDecimal = Field(..., description="Budget limit as decimal string, e.g. '5000.00'")
    category: int = Field(..., validation_alias="category_id", serialization_alias="category_id")
    month: int = Field(..., ge=1, le=12)
    year: int


class BudgetUpdate(BaseSchema):
    limit_amount: Optional[MoneyDecimal] = Field(None, description="Budget limit as decimal string")
    category: Optional[int] = Field(None, validation_alias="category_id", serialization_alias="category_id")
    month: Optional[int] = Field(None, ge=1, le=12)
    year: Optional[int] = None


class BudgetRead(TimestampSchema):
    id: int
    limit_amount: MoneyDecimal = Field(..., description="Budget limit as decimal string, e.g. '5000.00'")
    category: CategorySummary
    month: int
    year: int


class BudgetProgress(BaseSchema):
    """Budget progress information."""
    spent_amount: MoneyDecimal = Field(..., description="Total spent in this budget period")
    remaining_amount: MoneyDecimal = Field(..., description="Remaining budget (can be negative if over)")
    percentage_used: float = Field(..., ge=0, description="Percentage of budget used")
    status: BudgetStatus = Field(..., description="Budget status indicator")
    daily_allowance: Optional[MoneyDecimal] = Field(
        None,
        description="Daily spending allowance based on remaining days (None for future budgets)"
    )
    days_remaining: Optional[int] = Field(
        None,
        description="Days remaining in budget period (None for future budgets)"
    )
    transaction_count: int = Field(0, description="Number of transactions in this budget period")


class BudgetReadWithProgress(TimestampSchema):
    """Budget with progress tracking information."""
    id: int
    limit_amount: MoneyDecimal = Field(..., description="Budget limit as decimal string")
    category: CategorySummary
    month: int
    year: int
    progress: BudgetProgress
