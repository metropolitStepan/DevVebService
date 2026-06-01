from decimal import Decimal

from fastapi import Depends

from app.db.repositories.admin_items import AdminItemsRepository, get_admin_items_repository
from app.schemas.items import ItemResponse


class AdminItemService:
    def __init__(self, repo: AdminItemsRepository) -> None:
        self.repo = repo

    async def create_item(
        self,
        *,
        sku: str,
        name: str,
        description: str | None,
        price: Decimal,
        stock: int | None,
    ) -> ItemResponse:
        item = self.repo.create_item(
            sku=sku,
            name=name,
            description=description,
            price=price,
            stock=stock,
        )
        return _map_item(item)

    async def update_item(
        self,
        *,
        item_id: int,
        name: str | None,
        description: str | None,
        price: Decimal | None,
        stock: int | None,
    ) -> ItemResponse:
        item = self.repo.update_item(
            item_id=item_id,
            name=name,
            description=description,
            price=price,
            stock=stock,
        )
        return _map_item(item)

    async def delete_item(self, *, item_id: int) -> ItemResponse:
        return _map_item(self.repo.delete_item(item_id))

    async def toggle_active(self, *, item_id: int, is_active: bool) -> ItemResponse:
        return _map_item(self.repo.toggle_active(item_id=item_id, is_active=is_active))


def _map_item(item: object) -> ItemResponse:
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


def get_admin_item_service(
    repo: AdminItemsRepository = Depends(get_admin_items_repository),
) -> AdminItemService:
    return AdminItemService(repo=repo)
