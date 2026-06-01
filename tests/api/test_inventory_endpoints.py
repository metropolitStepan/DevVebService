from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_inventory_positive_empty_for_new_user(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="inv_empty@example.com", username="inv_empty")

    response = client.get("/api/v1/inventory", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_inventory_positive_after_purchase(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
    create_purchase: Callable[..., tuple[dict[str, Any], str]],
) -> None:
    headers, _, _ = auth_headers(email="inv_purchase@example.com", username="inv_purchase")
    topup_balance(headers=headers, amount="1000.00")
    create_purchase(headers=headers, item_id=1, quantity=2)

    response = client.get("/api/v1/inventory", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["item_id"] == 1
    assert payload["items"][0]["quantity"] == 2


def test_inventory_negative_without_auth_401(client: TestClient) -> None:
    response = client.get("/api/v1/inventory")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_inventory_negative_invalid_token_401(client: TestClient) -> None:
    response = client.get(
        "/api/v1/inventory",
        headers={"Authorization": "Bearer malformed.token.value"},
    )

    assert response.status_code == 401
    assert response.json()["code"] in {"INVALID_TOKEN", "INVALID_TOKEN_SIGNATURE"}
