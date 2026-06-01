from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.repositories.store import STORE
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    STORE.reset()


def _auth_headers(email: str = "buyer@example.com", username: str = "buyer_1") -> tuple[dict[str, str], int]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    payload = register_response.json()
    user_id = payload["user"]["id"]
    access_token = payload["tokens"]["access_token"]
    return {"Authorization": f"Bearer {access_token}"}, user_id


def _topup(headers: dict[str, str], amount: str = "1000.00") -> None:
    response = client.post(
        "/api/v1/wallet/topup",
        json={"amount": amount, "reason": "test topup"},
        headers=headers,
    )
    assert response.status_code == 201


def test_purchase_and_refund_happy_path() -> None:
    headers, user_id = _auth_headers()
    _topup(headers)

    idempotency_key = str(uuid4())
    buy_response = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 1},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert buy_response.status_code == 201

    purchase_id = buy_response.json()["id"]

    wallet_after_purchase = client.get("/api/v1/wallet", headers=headers)
    assert wallet_after_purchase.status_code == 200
    assert wallet_after_purchase.json()["balance"] == "801.00"

    inventory_after_purchase = client.get("/api/v1/inventory", headers=headers)
    assert inventory_after_purchase.status_code == 200
    assert inventory_after_purchase.json()["items"][0]["quantity"] == 1

    refund_response = client.post(
        "/api/v1/refunds",
        json={"purchase_id": purchase_id, "reason": "mistaken purchase"},
        headers=headers,
    )
    assert refund_response.status_code == 201
    assert refund_response.json()["status"] == "applied"

    wallet_after_refund = client.get("/api/v1/wallet", headers=headers)
    assert wallet_after_refund.status_code == 200
    assert wallet_after_refund.json()["balance"] == "1000.00"

    assert any(tx.operation == "purchase_debit" for tx in STORE.wallet_transactions.values())
    assert any(tx.operation == "refund_credit" for tx in STORE.wallet_transactions.values())
    assert STORE.purchases[purchase_id].status == "refunded"
    assert STORE.inventory[(user_id, 1)] == 0


def test_purchase_idempotency_same_key_returns_same_result() -> None:
    headers, _ = _auth_headers(email="idempotent@example.com", username="idempotent")
    _topup(headers, amount="500.00")

    idempotency_key = str(uuid4())
    response_first = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 1},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert response_first.status_code == 201

    response_second = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 1},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert response_second.status_code == 201
    assert response_second.json()["id"] == response_first.json()["id"]

    wallet_response = client.get("/api/v1/wallet", headers=headers)
    assert wallet_response.status_code == 200
    assert wallet_response.json()["balance"] == "301.00"

    purchase_debits = [tx for tx in STORE.wallet_transactions.values() if tx.operation == "purchase_debit"]
    assert len(purchase_debits) == 1


def test_purchase_idempotency_conflict_on_payload_change() -> None:
    headers, _ = _auth_headers(email="conflict@example.com", username="conflict")
    _topup(headers, amount="1000.00")

    idempotency_key = str(uuid4())
    first_response = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 1},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 2},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert second_response.status_code == 409
    assert second_response.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_refund_window_rule_enforced_for_player() -> None:
    headers, _ = _auth_headers(email="refundwindow@example.com", username="refundwindow")
    _topup(headers, amount="1000.00")

    idempotency_key = str(uuid4())
    buy_response = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 1},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert buy_response.status_code == 201
    purchase_id = buy_response.json()["id"]

    STORE.purchases[purchase_id].created_at = datetime.now(UTC) - timedelta(
        minutes=settings.refund_window_minutes + 1
    )

    refund_response = client.post(
        "/api/v1/refunds",
        json={"purchase_id": purchase_id, "reason": "late refund"},
        headers=headers,
    )
    assert refund_response.status_code == 400
    assert refund_response.json()["code"] == "REFUND_WINDOW_EXPIRED"


def test_refund_inventory_condition_rule_enforced() -> None:
    headers, user_id = _auth_headers(email="invcheck@example.com", username="invcheck")
    _topup(headers, amount="1000.00")

    idempotency_key = str(uuid4())
    buy_response = client.post(
        "/api/v1/purchases",
        json={"item_id": 1, "quantity": 1},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    assert buy_response.status_code == 201
    purchase_id = buy_response.json()["id"]

    STORE.inventory[(user_id, 1)] = 0

    refund_response = client.post(
        "/api/v1/refunds",
        json={"purchase_id": purchase_id, "reason": "inventory mismatch"},
        headers=headers,
    )
    assert refund_response.status_code == 409
    assert refund_response.json()["code"] == "REFUND_INVENTORY_CONDITION_FAILED"
