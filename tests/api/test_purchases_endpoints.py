from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.repositories.store import STORE


def test_buy_positive_success(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="buy_ok@example.com", username="buy_ok")
    topup_balance(headers=headers, amount="1000.00")

    response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 1},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "completed"


def test_buy_positive_idempotent_repeat_returns_same_purchase(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="buy_idem@example.com", username="buy_idem")
    topup_balance(headers=headers, amount="1000.00")

    idem_key = str(uuid4())
    first = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": idem_key},
        json={"item_id": 1, "quantity": 1},
    )
    second = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": idem_key},
        json={"item_id": 1, "quantity": 1},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_buy_negative_insufficient_funds_400(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="buy_no_money@example.com", username="buy_no_money")

    response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 1},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INSUFFICIENT_FUNDS"


def test_buy_negative_item_not_active_400(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="buy_inactive@example.com", username="buy_inactive")
    topup_balance(headers=headers, amount="1000.00")
    STORE.items[1].is_active = False

    response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 1},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ITEM_NOT_ACTIVE"


def test_history_positive_returns_user_purchases(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="history_ok@example.com", username="history_ok")
    topup_balance(headers=headers, amount="2000.00")

    for _ in range(2):
        response = client.post(
            "/api/v1/purchases",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"item_id": 1, "quantity": 1},
        )
        assert response.status_code == 201

    history = client.get("/api/v1/purchases", headers=headers)

    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert len(history.json()["purchases"]) == 2


def test_history_positive_pagination(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="history_page@example.com", username="history_page")
    topup_balance(headers=headers, amount="3000.00")

    for _ in range(3):
        response = client.post(
            "/api/v1/purchases",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"item_id": 1, "quantity": 1},
        )
        assert response.status_code == 201

    page = client.get("/api/v1/purchases", headers=headers, params={"limit": 2, "offset": 1})

    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["purchases"]) == 2
    assert page.json()["offset"] == 1


def test_history_negative_unauthorized_401(client: TestClient) -> None:
    response = client.get("/api/v1/purchases")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_history_negative_validation_422(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="history_422@example.com", username="history_422")

    response = client.get("/api/v1/purchases", headers=headers, params={"limit": 500})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_get_purchase_by_id_positive_for_owner(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
    create_purchase: Callable[..., tuple[dict[str, Any], str]],
) -> None:
    headers, _, _ = auth_headers(email="purchase_owner@example.com", username="purchase_owner")
    topup_balance(headers=headers, amount="1000.00")
    purchase, _ = create_purchase(headers=headers)

    response = client.get(f"/api/v1/purchases/{purchase['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == purchase["id"]


def test_get_purchase_by_id_positive_for_admin(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
    create_purchase: Callable[..., tuple[dict[str, Any], str]],
) -> None:
    player_headers, _, _ = auth_headers(email="purchase_player@example.com", username="purchase_player")
    topup_balance(headers=player_headers, amount="1000.00")
    purchase, _ = create_purchase(headers=player_headers)

    admin_auth_headers, _, _ = admin_headers(email="purchase_admin@example.com", username="purchase_admin")
    response = client.get(f"/api/v1/purchases/{purchase['id']}", headers=admin_auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == purchase["id"]


def test_get_purchase_by_id_negative_forbidden_403(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
    create_purchase: Callable[..., tuple[dict[str, Any], str]],
) -> None:
    owner_headers, _, _ = auth_headers(email="purchase_owner2@example.com", username="purchase_owner2")
    topup_balance(headers=owner_headers, amount="1000.00")
    purchase, _ = create_purchase(headers=owner_headers)

    stranger_headers, _, _ = auth_headers(email="purchase_stranger@example.com", username="purchase_stranger")
    response = client.get(f"/api/v1/purchases/{purchase['id']}", headers=stranger_headers)

    assert response.status_code == 403
    assert response.json()["code"] == "PURCHASE_FORBIDDEN"


def test_get_purchase_by_id_negative_not_found_404(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="purchase_nf@example.com", username="purchase_nf")

    response = client.get("/api/v1/purchases/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "PURCHASE_NOT_FOUND"
