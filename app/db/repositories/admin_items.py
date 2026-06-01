from datetime import UTC, datetime
from decimal import Decimal

from fastapi import Depends

from app.db.repositories.store import InMemoryStore, ItemRecord, get_store
from app.services.errors import ConflictError, NotFoundError


class AdminItemsRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_item(
        self,
        *,
        sku: str,
        name: str,
        description: str | None,
        price: Decimal,
        stock: int | None,
    ) -> ItemRecord:
        sku_key = sku.strip().lower()
        for item in self.store.items.values():
            if item.sku.lower() == sku_key and item.deleted_at is None:
                raise ConflictError("ITEM_SKU_EXISTS", "Item with this SKU already exists")

        self.store._item_seq += 1
        now = datetime.now(UTC)
        item = ItemRecord(
            id=self.store._item_seq,
            sku=sku.strip(),
            name=name.strip(),
            description=description,
            price=price,
            is_active=True,
            stock=stock,
            created_at=now,
            updated_at=now,
        )
        self.store.items[item.id] = item
        return item

    def get_item(self, item_id: int) -> ItemRecord:
        item = self.store.items.get(item_id)
        if item is None or item.deleted_at is not None:
            raise NotFoundError("ITEM_NOT_FOUND", "Item not found")
        return item

    def update_item(
        self,
        *,
        item_id: int,
        name: str | None,
        description: str | None,
        price: Decimal | None,
        stock: int | None,
    ) -> ItemRecord:
        item = self.get_item(item_id)

        if name is not None:
            item.name = name.strip()
        if description is not None:
            item.description = description
        if price is not None:
            item.price = price
        if stock is not None:
            item.stock = stock

        item.updated_at = datetime.now(UTC)
        return item

    def delete_item(self, item_id: int) -> ItemRecord:
        item = self.get_item(item_id)
        now = datetime.now(UTC)
        item.deleted_at = now
        item.is_active = False
        item.updated_at = now
        return item

    def toggle_active(self, item_id: int, is_active: bool) -> ItemRecord:
        item = self.get_item(item_id)
        item.is_active = is_active
        item.updated_at = datetime.now(UTC)
        return item


def get_admin_items_repository(store: InMemoryStore = Depends(get_store)) -> AdminItemsRepository:
    return AdminItemsRepository(store)
