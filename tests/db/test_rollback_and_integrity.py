from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.repositories.store import STORE


def test_purchase_writes_consistent_records(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, user_id, _ = auth_headers(email="db_purchase@example.com", username="db_purchase")
    topup_balance(headers=headers, amount="1000.00")

    buy_response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 2},
    )
    assert buy_response.status_code == 201
    purchase_id = int(buy_response.json()["id"])

    purchase = STORE.purchases[purchase_id]
    wallet = STORE.wallets_by_user[user_id]

    assert purchase.user_id == user_id
    assert purchase.total_amount == Decimal("398.00")
    assert wallet.balance == Decimal("602.00")
    assert STORE.inventory[(user_id, 1)] == 2
    assert any(tx.operation == "purchase_debit" for tx in STORE.wallet_transactions.values())


def test_refund_writes_consistent_records(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, user_id, _ = auth_headers(email="db_refund@example.com", username="db_refund")
    topup_balance(headers=headers, amount="1000.00")

    buy_response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 1},
    )
    assert buy_response.status_code == 201
    purchase_id = int(buy_response.json()["id"])

    refund_response = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"purchase_id": purchase_id, "reason": "test refund flow"},
    )
    assert refund_response.status_code == 201

    purchase = STORE.purchases[purchase_id]
    wallet = STORE.wallets_by_user[user_id]

    assert purchase.status == "refunded"
    assert wallet.balance == Decimal("1000.00")
    assert STORE.inventory[(user_id, 1)] == 0
    assert len(STORE.refunds) == 1
    assert any(tx.operation == "refund_credit" for tx in STORE.wallet_transactions.values())


def test_purchase_rolls_back_state_when_error_happens_mid_transaction(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, user_id, _ = auth_headers(email="rollback_purchase@example.com", username="rollback_purchase")
    topup_balance(headers=headers, amount="1000.00")

    balance_before = STORE.wallets_by_user[user_id].balance
    item_stock_before = STORE.items[1].stock

    def _boom(*_: object, **__: object) -> None:
        raise RuntimeError("forced wallet tx error")

    monkeypatch.setattr(type(STORE), "create_wallet_transaction", _boom)

    idem_key = str(uuid4())
    with pytest.raises(RuntimeError, match="forced wallet tx error"):
        client.post(
            "/api/v1/purchases",
            headers={**headers, "Idempotency-Key": idem_key},
            json={"item_id": 1, "quantity": 1},
        )

    assert STORE.wallets_by_user[user_id].balance == balance_before
    assert STORE.purchases == {}
    assert STORE.inventory.get((user_id, 1), 0) == 0
    assert idem_key not in STORE.idempotency_records
    assert STORE.items[1].stock == item_stock_before


def test_refund_rolls_back_state_when_error_happens_mid_transaction(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, user_id, _ = auth_headers(email="rollback_refund@example.com", username="rollback_refund")
    topup_balance(headers=headers, amount="1000.00")

    buy_response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 1},
    )
    assert buy_response.status_code == 201
    purchase_id = int(buy_response.json()["id"])

    balance_after_buy = STORE.wallets_by_user[user_id].balance
    inventory_after_buy = STORE.inventory[(user_id, 1)]

    def _boom(*_: object, **__: object) -> None:
        raise RuntimeError("forced refund tx error")

    monkeypatch.setattr(type(STORE), "create_wallet_transaction", _boom)

    with pytest.raises(RuntimeError, match="forced refund tx error"):
        client.post(
            "/api/v1/refunds",
            headers=headers,
            json={"purchase_id": purchase_id, "reason": "rollback test"},
        )

    assert STORE.wallets_by_user[user_id].balance == balance_after_buy
    assert STORE.inventory[(user_id, 1)] == inventory_after_buy
    assert STORE.purchases[purchase_id].status == "completed"
    assert STORE.refunds == {}
    assert STORE.refunds_by_purchase == {}
