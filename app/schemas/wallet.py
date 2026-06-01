from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, condecimal


class WalletBalanceResponse(BaseModel):
    wallet_id: int
    user_id: int
    currency_code: str
    balance: Decimal
    updated_at: datetime


class WalletTopupRequest(BaseModel):
    amount: condecimal(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=255)
    external_ref: str | None = Field(default=None, max_length=128)


class TopupResponse(BaseModel):
    id: int
    wallet_id: int
    amount: Decimal
    status: str
    reason: str
    external_ref: str | None
    created_at: datetime
    applied_at: datetime | None
