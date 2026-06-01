from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.inventory import InventoryListResponse
from app.services.inventory_service import InventoryService, get_inventory_service


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=InventoryListResponse)
async def list_inventory(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
) -> InventoryListResponse:
    return await service.list_inventory(current_user.id)
