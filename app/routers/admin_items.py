from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import role_required
from app.schemas.auth import CurrentUser
from app.schemas.items import (
    AdminItemCreateRequest,
    AdminItemToggleActiveRequest,
    AdminItemUpdateRequest,
    ItemResponse,
)
from app.services.admin_item_service import AdminItemService, get_admin_item_service


router = APIRouter(prefix="/admin/items", tags=["admin-items"])

admin_required = role_required("admin")


@router.post("", response_model=ItemResponse)
async def create_item(
    payload: AdminItemCreateRequest,
    _: Annotated[CurrentUser, Depends(admin_required)],
    service: Annotated[AdminItemService, Depends(get_admin_item_service)],
) -> ItemResponse:
    return await service.create_item(
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        stock=payload.stock,
    )


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    payload: AdminItemUpdateRequest,
    _: Annotated[CurrentUser, Depends(admin_required)],
    service: Annotated[AdminItemService, Depends(get_admin_item_service)],
) -> ItemResponse:
    return await service.update_item(
        item_id=item_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        stock=payload.stock,
    )


@router.delete("/{item_id}", response_model=ItemResponse)
async def delete_item(
    item_id: int,
    _: Annotated[CurrentUser, Depends(admin_required)],
    service: Annotated[AdminItemService, Depends(get_admin_item_service)],
) -> ItemResponse:
    return await service.delete_item(item_id=item_id)


@router.post("/{item_id}/toggle-active", response_model=ItemResponse)
async def toggle_active(
    item_id: int,
    payload: AdminItemToggleActiveRequest,
    _: Annotated[CurrentUser, Depends(admin_required)],
    service: Annotated[AdminItemService, Depends(get_admin_item_service)],
) -> ItemResponse:
    return await service.toggle_active(item_id=item_id, is_active=payload.is_active)
