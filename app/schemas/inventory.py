from datetime import datetime

from pydantic import BaseModel


class InventoryItemResponse(BaseModel):
    item_id: int
    sku: str
    name: str
    quantity: int
    updated_at: datetime


class InventoryListResponse(BaseModel):
    items: list[InventoryItemResponse]
    total: int
