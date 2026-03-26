
from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal
from typing import Optional, List
from schemas.enums import TransactionType

from .base import BaseSchema, TimestampSchema, MoneyDecimal
from .shared import CategorySummary, AccountSummary


class TagRead(BaseSchema):
    id: int
    name: str


class TransactionBase(BaseSchema):
    amount: MoneyDecimal = Field(..., description="Transaction amount as decimal string, e.g. '123.45'")
    type: TransactionType
    description: Optional[str] = None
    transaction_date: date = Field(default_factory=date.today)


class TransactionCreate(TransactionBase):
    account: Optional[int] = Field(default=None, validation_alias="account_id")
    category: Optional[int] = Field(default=None, validation_alias="category_id")
    tags: List[str] = []


class TransactionRead(TransactionBase, TimestampSchema):
    id: int
    account: AccountSummary
    category: Optional[CategorySummary] = None
    tags: List[TagRead] = []
    is_reviewed: bool
    ai_confidence: Optional[float] = None
    raw_input: Optional[str] = None


class TransactionUpdate(BaseSchema):
    amount: Optional[MoneyDecimal] = Field(None, description="Transaction amount as decimal string")
    type: Optional[TransactionType] = None
    description: Optional[str] = None
    transaction_date: Optional[date] = None
    category: Optional[int] = Field(default=None, validation_alias="category_id", serialization_alias="category_id")
    account: Optional[int] = Field(default=None, validation_alias="account_id", serialization_alias="account_id")
    is_reviewed: Optional[bool] = None
    tags: Optional[List[str]] = None


class TransactionAIRequest(BaseModel):
    prompt: str = Field(..., min_length=2)