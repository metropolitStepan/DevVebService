from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_get_balance_positive_for_new_user(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, user_id, _ = auth_headers(email="wallet_new@example.com", username="wallet_new")

    response = client.get("/api/v1/wallet", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == user_id
    assert payload["balance"] == "0.00"


def test_get_balance_positive_after_topup(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="wallet_topup@example.com", username="wallet_topup")
    topup_balance(headers=headers, amount="350.50")

    response = client.get("/api/v1/wallet", headers=headers)

    assert response.status_code == 200
    assert response.json()["balance"] == "350.50"


def test_get_balance_negative_without_auth_401(client: TestClient) -> None:
    response = client.get("/api/v1/wallet")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_get_balance_negative_invalid_token_401(client: TestClient) -> None:
    response = client.get("/api/v1/wallet", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_topup_positive_simple(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="topup_simple@example.com", username="topup_simple")

    response = client.post(
        "/api/v1/wallet/topup",
        headers=headers,
        json={"amount": "99.99", "reason": "daily bonus"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["amount"] == "99.99"
    assert payload["status"] == "applied"


def test_topup_positive_external_ref_unique(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="topup_ext@example.com", username="topup_ext")

    response = client.post(
        "/api/v1/wallet/topup",
        headers=headers,
        json={"amount": "50.00", "reason": "promo", "external_ref": "ext-001"},
    )

    assert response.status_code == 201
    assert response.json()["external_ref"] == "ext-001"


def test_topup_negative_validation_422(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="topup_422@example.com", username="topup_422")

    response = client.post(
        "/api/v1/wallet/topup",
        headers=headers,
        json={"amount": "0.00", "reason": "ok reason"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_topup_negative_duplicate_external_ref_409(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="topup_dup@example.com", username="topup_dup")

    first = client.post(
        "/api/v1/wallet/topup",
        headers=headers,
        json={"amount": "25.00", "reason": "promo", "external_ref": "same-ext"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/wallet/topup",
        headers=headers,
        json={"amount": "30.00", "reason": "promo", "external_ref": "same-ext"},
    )

    assert second.status_code == 409
    assert second.json()["code"] == "TOPUP_EXTERNAL_REF_EXISTS"
