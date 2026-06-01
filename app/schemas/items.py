from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, condecimal


class ItemResponse(BaseModel):
    id: int
    sku: str
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    stock: int | None
    created_at: datetime
    updated_at: datetime


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    limit: int
    offset: int


class AdminItemCreateRequest(BaseModel):
    sku: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    price: condecimal(ge=0, max_digits=18, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)


class AdminItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    price: condecimal(ge=0, max_digits=18, decimal_places=2) | None = None
    stock: int | None = Field(default=None, ge=0)


class AdminItemToggleActiveRequest(BaseModel):
    is_active: bool
