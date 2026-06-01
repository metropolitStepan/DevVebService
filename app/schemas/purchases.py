from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, conint


class PurchaseCreateRequest(BaseModel):
    item_id: int
    quantity: conint(gt=0)


class PurchaseResponse(BaseModel):
    id: int
    user_id: int
    wallet_id: int
    item_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    status: str
    idempotency_key: UUID
    created_at: datetime
    completed_at: datetime | None


class PurchaseListResponse(BaseModel):
    purchases: list[PurchaseResponse]
    total: int
    limit: int
    offset: int
