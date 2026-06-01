from datetime import UTC, datetime
from decimal import Decimal

from fastapi import Depends

from app.db.repositories.store import InMemoryStore, TopupRecord, WalletRecord, get_store
from app.services.errors import ConflictError


class WalletRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def get_wallet(self, user_id: int) -> WalletRecord | None:
        return self.store.wallets_by_user.get(user_id)

    def get_or_create_wallet(self, user_id: int) -> WalletRecord:
        wallet = self.get_wallet(user_id)
        if wallet is not None:
            return wallet

        self.store._wallet_seq += 1
        wallet = WalletRecord(
            id=self.store._wallet_seq,
            user_id=user_id,
            currency_code="GLD",
            balance=Decimal("0.00"),
            updated_at=datetime.now(UTC),
        )
        self.store.wallets_by_user[user_id] = wallet
        return wallet

    def topup(self, user_id: int, amount: Decimal, reason: str, external_ref: str | None) -> TopupRecord:
        with self.store.transaction():
            if external_ref and external_ref in self.store.topups_by_external_ref:
                raise ConflictError("TOPUP_EXTERNAL_REF_EXISTS", "Topup with this external_ref already exists")

            wallet = self.get_or_create_wallet(user_id)

            self.store._topup_seq += 1
            now = datetime.now(UTC)
            topup = TopupRecord(
                id=self.store._topup_seq,
                wallet_id=wallet.id,
                amount=amount,
                reason=reason,
                status="applied",
                external_ref=external_ref,
                created_at=now,
                applied_at=now,
            )
            self.store.topups[topup.id] = topup

            if external_ref:
                self.store.topups_by_external_ref[external_ref] = topup.id

            wallet_balance_before = wallet.balance
            wallet.balance += amount
            wallet.updated_at = now

            self.store.create_wallet_transaction(
                wallet_id=wallet.id,
                user_id=user_id,
                purchase_id=None,
                refund_id=None,
                operation="topup_credit",
                amount=amount,
                balance_before=wallet_balance_before,
                balance_after=wallet.balance,
                currency_code=wallet.currency_code,
                metadata={"topup_id": topup.id},
            )
            return topup


def get_wallet_repository(store: InMemoryStore = Depends(get_store)) -> WalletRepository:
    return WalletRepository(store)
