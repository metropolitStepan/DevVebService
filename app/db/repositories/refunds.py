from datetime import UTC, datetime

from fastapi import Depends

from app.core.config import settings
from app.db.repositories.store import InMemoryStore, RefundRecord, get_store
from app.services.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class RefundRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def request_refund(self, *, actor_user_id: int, purchase_id: int, reason: str, is_admin: bool) -> RefundRecord:
        if not reason.strip():
            raise BadRequestError("REFUND_REASON_REQUIRED", "Refund reason is required")

        with self.store.transaction():
            purchase = self.store.purchases.get(purchase_id)
            if purchase is None:
                raise NotFoundError("PURCHASE_NOT_FOUND", "Purchase not found")

            if not is_admin and purchase.user_id != actor_user_id:
                raise ForbiddenError("REFUND_FORBIDDEN", "You can refund only your purchases")

            if purchase.status != "completed":
                raise BadRequestError("REFUND_NOT_ALLOWED", "Refund is available only for completed purchases")

            if purchase_id in self.store.refunds_by_purchase:
                raise ConflictError("REFUND_ALREADY_EXISTS", "Refund already requested for this purchase")

            now = datetime.now(UTC)
            purchase_age_minutes = (now - purchase.created_at).total_seconds() / 60
            if purchase_age_minutes > settings.refund_window_minutes:
                if not (is_admin and settings.allow_admin_refund_after_window):
                    raise BadRequestError(
                        "REFUND_WINDOW_EXPIRED",
                        f"Refund window is {settings.refund_window_minutes} minutes",
                    )

            inventory_key = (purchase.user_id, purchase.item_id)
            current_quantity = self.store.inventory.get(inventory_key, 0)
            if settings.require_inventory_for_refund and current_quantity < purchase.quantity:
                raise ConflictError(
                    "REFUND_INVENTORY_CONDITION_FAILED",
                    "Refund requires enough quantity of item in inventory",
                )

            wallet = self.store.wallets_by_user.get(purchase.user_id)
            if wallet is None:
                raise NotFoundError("WALLET_NOT_FOUND", "Wallet not found")

            wallet_balance_before = wallet.balance
            wallet.balance += purchase.total_amount
            wallet.updated_at = now

            self.store.inventory[inventory_key] = max(0, current_quantity - purchase.quantity)

            item = self.store.items.get(purchase.item_id)
            if item is not None and item.stock is not None:
                item.stock += purchase.quantity
                item.updated_at = now

            purchase.status = "refunded"

            self.store._refund_seq += 1
            refund = RefundRecord(
                id=self.store._refund_seq,
                purchase_id=purchase.id,
                wallet_id=wallet.id,
                amount=purchase.total_amount,
                reason=reason.strip(),
                status="applied",
                created_at=now,
                processed_at=now,
            )
            self.store.refunds[refund.id] = refund
            self.store.refunds_by_purchase[purchase.id] = refund.id

            self.store.create_wallet_transaction(
                wallet_id=wallet.id,
                user_id=purchase.user_id,
                purchase_id=purchase.id,
                refund_id=refund.id,
                operation="refund_credit",
                amount=purchase.total_amount,
                balance_before=wallet_balance_before,
                balance_after=wallet.balance,
                currency_code=wallet.currency_code,
                metadata={
                    "purchase_id": purchase.id,
                    "refund_id": refund.id,
                    "item_id": purchase.item_id,
                    "quantity": purchase.quantity,
                },
            )
            return refund


def get_refund_repository(store: InMemoryStore = Depends(get_store)) -> RefundRepository:
    return RefundRepository(store)
