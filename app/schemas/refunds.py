from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RefundRequestCreate(BaseModel):
    purchase_id: int
    reason: str = Field(min_length=5, max_length=500)


class RefundResponse(BaseModel):
    id: int
    purchase_id: int
    wallet_id: int
    amount: Decimal
    status: str
    reason: str
    created_at: datetime
    processed_at: datetime | None
