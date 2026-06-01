from fastapi import Depends

from app.db.repositories.items import ItemsRepository, get_items_repository
from app.schemas.items import ItemListResponse, ItemResponse


class ItemService:
    def __init__(self, items_repo: ItemsRepository) -> None:
        self.items_repo = items_repo

    async def list_items(self, *, active_only: bool, limit: int, offset: int) -> ItemListResponse:
        items, total = self.items_repo.list_items(active_only=active_only, limit=limit, offset=offset)

        return ItemListResponse(
            items=[
                ItemResponse(
                    id=item.id,
                    sku=item.sku,
                    name=item.name,
                    description=item.description,
                    price=item.price,
                    is_active=item.is_active,
                    stock=item.stock,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in items
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_item(self, item_id: int) -> ItemResponse:
        item = self.items_repo.get_item(item_id)
        return ItemResponse(
            id=item.id,
            sku=item.sku,
            name=item.name,
            description=item.description,
            price=item.price,
            is_active=item.is_active,
            stock=item.stock,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


def get_item_service(items_repo: ItemsRepository = Depends(get_items_repository)) -> ItemService:
    return ItemService(items_repo=items_repo)
