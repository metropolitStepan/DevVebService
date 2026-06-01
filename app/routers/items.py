from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.schemas.items import ItemListResponse, ItemResponse
from app.services.item_service import ItemService, get_item_service


router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=ItemListResponse)
async def list_items(
    service: Annotated[ItemService, Depends(get_item_service)],
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ItemListResponse:
    return await service.list_items(active_only=active_only, limit=limit, offset=offset)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    service: Annotated[ItemService, Depends(get_item_service)],
) -> ItemResponse:
    return await service.get_item(item_id)
