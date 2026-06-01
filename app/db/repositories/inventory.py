from fastapi import Depends

from app.db.repositories.store import InMemoryStore, ItemRecord, get_store


class InventoryRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def list_user_inventory(self, user_id: int) -> list[tuple[ItemRecord, int]]:
        result: list[tuple[ItemRecord, int]] = []
        for (owner_id, item_id), quantity in self.store.inventory.items():
            if owner_id != user_id or quantity <= 0:
                continue

            item = self.store.items.get(item_id)
            if item is None or item.deleted_at is not None:
                continue

            result.append((item, quantity))

        result.sort(key=lambda row: row[0].id)
        return result


def get_inventory_repository(store: InMemoryStore = Depends(get_store)) -> InventoryRepository:
    return InventoryRepository(store)
