from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Iterator


@dataclass(slots=True)
class UserRecord:
    id: int
    email: str
    username: str
    password_hash: str
    role: str
    status: str
    created_at: datetime


@dataclass(slots=True)
class WalletRecord:
    id: int
    user_id: int
    currency_code: str
    balance: Decimal
    updated_at: datetime


@dataclass(slots=True)
class ItemRecord:
    id: int
    sku: str
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    stock: int | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass(slots=True)
class TopupRecord:
    id: int
    wallet_id: int
    amount: Decimal
    reason: str
    status: str
    external_ref: str | None
    created_at: datetime
    applied_at: datetime | None


@dataclass(slots=True)
class PurchaseRecord:
    id: int
    user_id: int
    wallet_id: int
    item_id: int
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    status: str
    idempotency_key: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class RefundRecord:
    id: int
    purchase_id: int
    wallet_id: int
    amount: Decimal
    reason: str
    status: str
    created_at: datetime
    processed_at: datetime | None


@dataclass(slots=True)
class WalletTransactionRecord:
    id: int
    wallet_id: int
    user_id: int
    purchase_id: int | None
    refund_id: int | None
    operation: str
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    currency_code: str
    created_at: datetime
    metadata_hash: str


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    operation: str
    payload_hash: str
    status: str
    result_purchase_id: int | None
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None


@dataclass(slots=True)
class InMemoryStore:
    users: dict[int, UserRecord] = field(default_factory=dict)
    users_by_email: dict[str, int] = field(default_factory=dict)
    users_by_username: dict[str, int] = field(default_factory=dict)

    wallets_by_user: dict[int, WalletRecord] = field(default_factory=dict)

    items: dict[int, ItemRecord] = field(default_factory=dict)

    topups: dict[int, TopupRecord] = field(default_factory=dict)
    topups_by_external_ref: dict[str, int] = field(default_factory=dict)

    purchases: dict[int, PurchaseRecord] = field(default_factory=dict)
    purchases_by_idempotency: dict[str, tuple[int, tuple[int, int, int]]] = field(
        default_factory=dict
    )

    inventory: dict[tuple[int, int], int] = field(default_factory=dict)

    refunds: dict[int, RefundRecord] = field(default_factory=dict)
    refunds_by_purchase: dict[int, int] = field(default_factory=dict)

    wallet_transactions: dict[int, WalletTransactionRecord] = field(default_factory=dict)
    idempotency_records: dict[str, IdempotencyRecord] = field(default_factory=dict)

    refresh_tokens: dict[str, int] = field(default_factory=dict)

    _user_seq: int = 0
    _wallet_seq: int = 0
    _item_seq: int = 0
    _topup_seq: int = 0
    _purchase_seq: int = 0
    _refund_seq: int = 0
    _wallet_transaction_seq: int = 0

    _lock: RLock = field(default_factory=RLock)

    def reset(self) -> None:
        with self._lock:
            self.users.clear()
            self.users_by_email.clear()
            self.users_by_username.clear()
            self.wallets_by_user.clear()
            self.items.clear()
            self.topups.clear()
            self.topups_by_external_ref.clear()
            self.purchases.clear()
            self.purchases_by_idempotency.clear()
            self.inventory.clear()
            self.refunds.clear()
            self.refunds_by_purchase.clear()
            self.wallet_transactions.clear()
            self.idempotency_records.clear()
            self.refresh_tokens.clear()

            self._user_seq = 0
            self._wallet_seq = 0
            self._item_seq = 0
            self._topup_seq = 0
            self._purchase_seq = 0
            self._refund_seq = 0
            self._wallet_transaction_seq = 0

            now = datetime.now(UTC)
            self._item_seq += 1
            self.items[self._item_seq] = ItemRecord(
                id=self._item_seq,
                sku="starter_skin_red",
                name="Starter Red Skin",
                description="Basic cosmetic skin for new players",
                price=Decimal("199.00"),
                is_active=True,
                stock=None,
                created_at=now,
                updated_at=now,
            )

            self._item_seq += 1
            self.items[self._item_seq] = ItemRecord(
                id=self._item_seq,
                sku="booster_x2_24h",
                name="Booster x2 (24h)",
                description="Doubles rewards for 24 hours",
                price=Decimal("299.00"),
                is_active=True,
                stock=None,
                created_at=now,
                updated_at=now,
            )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            snapshot = self._snapshot_state()
            try:
                yield
            except Exception:
                self._restore_state(snapshot)
                raise

    def create_wallet_transaction(
        self,
        *,
        wallet_id: int,
        user_id: int,
        purchase_id: int | None,
        refund_id: int | None,
        operation: str,
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        currency_code: str,
        metadata: dict[str, int | str],
    ) -> WalletTransactionRecord:
        self._wallet_transaction_seq += 1
        metadata_hash = hashlib.sha256(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        record = WalletTransactionRecord(
            id=self._wallet_transaction_seq,
            wallet_id=wallet_id,
            user_id=user_id,
            purchase_id=purchase_id,
            refund_id=refund_id,
            operation=operation,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            currency_code=currency_code,
            created_at=datetime.now(UTC),
            metadata_hash=metadata_hash,
        )
        self.wallet_transactions[record.id] = record
        return record

    def _snapshot_state(self) -> dict[str, object]:
        return {
            "users": deepcopy(self.users),
            "users_by_email": deepcopy(self.users_by_email),
            "users_by_username": deepcopy(self.users_by_username),
            "wallets_by_user": deepcopy(self.wallets_by_user),
            "items": deepcopy(self.items),
            "topups": deepcopy(self.topups),
            "topups_by_external_ref": deepcopy(self.topups_by_external_ref),
            "purchases": deepcopy(self.purchases),
            "purchases_by_idempotency": deepcopy(self.purchases_by_idempotency),
            "inventory": deepcopy(self.inventory),
            "refunds": deepcopy(self.refunds),
            "refunds_by_purchase": deepcopy(self.refunds_by_purchase),
            "wallet_transactions": deepcopy(self.wallet_transactions),
            "idempotency_records": deepcopy(self.idempotency_records),
            "refresh_tokens": deepcopy(self.refresh_tokens),
            "_user_seq": self._user_seq,
            "_wallet_seq": self._wallet_seq,
            "_item_seq": self._item_seq,
            "_topup_seq": self._topup_seq,
            "_purchase_seq": self._purchase_seq,
            "_refund_seq": self._refund_seq,
            "_wallet_transaction_seq": self._wallet_transaction_seq,
        }

    def _restore_state(self, snapshot: dict[str, object]) -> None:
        self.users = snapshot["users"]  # type: ignore[assignment]
        self.users_by_email = snapshot["users_by_email"]  # type: ignore[assignment]
        self.users_by_username = snapshot["users_by_username"]  # type: ignore[assignment]
        self.wallets_by_user = snapshot["wallets_by_user"]  # type: ignore[assignment]
        self.items = snapshot["items"]  # type: ignore[assignment]
        self.topups = snapshot["topups"]  # type: ignore[assignment]
        self.topups_by_external_ref = snapshot["topups_by_external_ref"]  # type: ignore[assignment]
        self.purchases = snapshot["purchases"]  # type: ignore[assignment]
        self.purchases_by_idempotency = snapshot["purchases_by_idempotency"]  # type: ignore[assignment]
        self.inventory = snapshot["inventory"]  # type: ignore[assignment]
        self.refunds = snapshot["refunds"]  # type: ignore[assignment]
        self.refunds_by_purchase = snapshot["refunds_by_purchase"]  # type: ignore[assignment]
        self.wallet_transactions = snapshot["wallet_transactions"]  # type: ignore[assignment]
        self.idempotency_records = snapshot["idempotency_records"]  # type: ignore[assignment]
        self.refresh_tokens = snapshot["refresh_tokens"]  # type: ignore[assignment]
        self._user_seq = int(snapshot["_user_seq"])
        self._wallet_seq = int(snapshot["_wallet_seq"])
        self._item_seq = int(snapshot["_item_seq"])
        self._topup_seq = int(snapshot["_topup_seq"])
        self._purchase_seq = int(snapshot["_purchase_seq"])
        self._refund_seq = int(snapshot["_refund_seq"])
        self._wallet_transaction_seq = int(snapshot["_wallet_transaction_seq"])


STORE = InMemoryStore()
STORE.reset()


def get_store() -> InMemoryStore:
    return STORE
