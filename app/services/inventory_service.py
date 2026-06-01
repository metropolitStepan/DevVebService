from fastapi import Depends

from app.db.repositories.inventory import InventoryRepository, get_inventory_repository
from app.schemas.inventory import InventoryItemResponse, InventoryListResponse


class InventoryService:
    def __init__(self, inventory_repo: InventoryRepository) -> None:
        self.inventory_repo = inventory_repo

    async def list_inventory(self, user_id: int) -> InventoryListResponse:
        rows = self.inventory_repo.list_user_inventory(user_id)
        items = [
            InventoryItemResponse(
                item_id=item.id,
                sku=item.sku,
                name=item.name,
                quantity=quantity,
                updated_at=item.updated_at,
            )
            for item, quantity in rows
        ]
        return InventoryListResponse(items=items, total=len(items))


def get_inventory_service(
    inventory_repo: InventoryRepository = Depends(get_inventory_repository),
) -> InventoryService:
    return InventoryService(inventory_repo=inventory_repo)
