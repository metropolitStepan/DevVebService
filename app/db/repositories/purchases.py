import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import Depends

from app.db.repositories.store import IdempotencyRecord, InMemoryStore, PurchaseRecord, get_store
from app.services.errors import BadRequestError, ConflictError, NotFoundError


class PurchaseRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_purchase(
        self,
        *,
        user_id: int,
        item_id: int,
        quantity: int,
        idempotency_key: str,
    ) -> tuple[PurchaseRecord, bool]:
        if not idempotency_key.strip():
            raise BadRequestError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required")

        payload = (user_id, item_id, quantity)
        payload_hash = self._build_purchase_payload_hash(user_id=user_id, item_id=item_id, quantity=quantity)

        with self.store.transaction():
            now = datetime.now(UTC)
            idempotency_record = self.store.idempotency_records.get(idempotency_key)

            if idempotency_record is not None:
                if idempotency_record.operation != "purchase":
                    raise ConflictError("IDEMPOTENCY_CONFLICT", "Idempotency key is used by another operation")
                if idempotency_record.payload_hash != payload_hash:
                    raise ConflictError(
                        "IDEMPOTENCY_CONFLICT",
                        "Idempotency key is already used with another payload",
                    )
                if idempotency_record.status == "completed" and idempotency_record.result_purchase_id is not None:
                    purchase = self.store.purchases.get(idempotency_record.result_purchase_id)
                    if purchase is None:
                        raise ConflictError(
                            "IDEMPOTENCY_CONFLICT",
                            "Idempotency record points to missing purchase",
                        )
                    return purchase, False
                if idempotency_record.status == "in_progress":
                    raise ConflictError("IDEMPOTENCY_IN_PROGRESS", "Purchase request is already in progress")

                idempotency_record.status = "in_progress"
                idempotency_record.updated_at = now
                idempotency_record.error_code = None
            else:
                idempotency_record = IdempotencyRecord(
                    key=idempotency_key,
                    operation="purchase",
                    payload_hash=payload_hash,
                    status="in_progress",
                    result_purchase_id=None,
                    created_at=now,
                    updated_at=now,
                )
                self.store.idempotency_records[idempotency_key] = idempotency_record

            item = self.store.items.get(item_id)
            if item is None or item.deleted_at is not None:
                raise NotFoundError("ITEM_NOT_FOUND", "Item not found")
            if not item.is_active:
                raise BadRequestError("ITEM_NOT_ACTIVE", "Item is not available for purchase")

            if item.stock is not None and item.stock < quantity:
                raise ConflictError("ITEM_OUT_OF_STOCK", "Not enough item stock")

            wallet = self.store.wallets_by_user.get(user_id)
            if wallet is None:
                raise NotFoundError("WALLET_NOT_FOUND", "Wallet not found")

            total = (item.price * Decimal(quantity)).quantize(Decimal("0.01"))
            if wallet.balance < total:
                raise BadRequestError("INSUFFICIENT_FUNDS", "Not enough balance")

            wallet_balance_before = wallet.balance
            wallet.balance -= total
            wallet.updated_at = now

            if item.stock is not None:
                item.stock -= quantity
                item.updated_at = now

            inventory_key = (user_id, item_id)
            self.store.inventory[inventory_key] = self.store.inventory.get(inventory_key, 0) + quantity

            self.store._purchase_seq += 1
            purchase = PurchaseRecord(
                id=self.store._purchase_seq,
                user_id=user_id,
                wallet_id=wallet.id,
                item_id=item_id,
                quantity=quantity,
                unit_price=item.price,
                total_amount=total,
                status="completed",
                idempotency_key=idempotency_key,
                created_at=now,
                completed_at=now,
            )
            self.store.purchases[purchase.id] = purchase
            self.store.purchases_by_idempotency[idempotency_key] = (purchase.id, payload)

            self.store.create_wallet_transaction(
                wallet_id=wallet.id,
                user_id=user_id,
                purchase_id=purchase.id,
                refund_id=None,
                operation="purchase_debit",
                amount=-total,
                balance_before=wallet_balance_before,
                balance_after=wallet.balance,
                currency_code=wallet.currency_code,
                metadata={"item_id": item_id, "quantity": quantity, "purchase_id": purchase.id},
            )

            idempotency_record.status = "completed"
            idempotency_record.result_purchase_id = purchase.id
            idempotency_record.updated_at = now
            return purchase, True

    def list_purchases(self, *, user_id: int, limit: int, offset: int) -> tuple[list[PurchaseRecord], int]:
        purchases = [purchase for purchase in self.store.purchases.values() if purchase.user_id == user_id]
        purchases.sort(key=lambda row: row.id)
        total = len(purchases)
        return purchases[offset : offset + limit], total

    def get_purchase(self, *, purchase_id: int) -> PurchaseRecord:
        purchase = self.store.purchases.get(purchase_id)
        if purchase is None:
            raise NotFoundError("PURCHASE_NOT_FOUND", "Purchase not found")
        return purchase

    @staticmethod
    def _build_purchase_payload_hash(*, user_id: int, item_id: int, quantity: int) -> str:
        serialized = json.dumps(
            {"user_id": user_id, "item_id": item_id, "quantity": quantity},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_purchase_repository(store: InMemoryStore = Depends(get_store)) -> PurchaseRepository:
    return PurchaseRepository(store)
