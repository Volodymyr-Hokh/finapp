from decimal import Decimal
from typing import Optional
from pydantic import Field
from .base import BaseSchema, TimestampSchema, MoneyDecimal


class AccountBase(BaseSchema):
    name: str = Field(..., max_length=100, description="Account name. e.g. 'Cash', 'Monobank'")
    currency: str = Field("UAH", max_length=3)
    is_default: bool = Field(False)


class AccountCreate(AccountBase):
    balance: MoneyDecimal = Field(default=Decimal("0.00"), description="Initial balance as decimal string, e.g. '1000.00'")


class AccountUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=100)
    currency: Optional[str] = Field(None, max_length=3)
    balance: Optional[MoneyDecimal] = Field(None, description="Account balance as decimal string")
    is_default: Optional[bool] = Field(None)


class AccountRead(AccountBase, TimestampSchema):
    id: int
    balance: MoneyDecimal = Field(..., description="Current balance as decimal string, e.g. '1234.56'")