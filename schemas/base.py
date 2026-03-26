from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, ConfigDict, PlainSerializer
from datetime import datetime


# Custom type for monetary amounts - always serializes as string for precision
MoneyDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json")
]


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime