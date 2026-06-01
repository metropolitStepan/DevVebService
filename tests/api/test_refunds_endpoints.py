from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.repositories.store import STORE


def _buy_for_user(
    *,
    client: TestClient,
    headers: dict[str, str],
) -> int:
    response = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"item_id": 1, "quantity": 1},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_refund_positive_for_owner(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="refund_owner@example.com", username="refund_owner")
    topup_balance(headers=headers, amount="1000.00")
    purchase_id = _buy_for_user(client=client, headers=headers)

    response = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"purchase_id": purchase_id, "reason": "mistaken purchase"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "applied"


def test_refund_positive_admin_for_other_user(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    player_headers, _, _ = auth_headers(email="refund_player@example.com", username="refund_player")
    topup_balance(headers=player_headers, amount="1000.00")
    purchase_id = _buy_for_user(client=client, headers=player_headers)

    admin_auth_headers, _, _ = admin_headers(email="refund_admin@example.com", username="refund_admin")
    response = client.post(
        "/api/v1/refunds",
        headers=admin_auth_headers,
        json={"purchase_id": purchase_id, "reason": "admin support action"},
    )

    assert response.status_code == 201
    assert response.json()["purchase_id"] == purchase_id


def test_refund_negative_already_refunded_409(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="refund_dupe@example.com", username="refund_dupe")
    topup_balance(headers=headers, amount="1000.00")
    purchase_id = _buy_for_user(client=client, headers=headers)

    first = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"purchase_id": purchase_id, "reason": "first request"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"purchase_id": purchase_id, "reason": "duplicate request"},
    )

    assert second.status_code == 400
    assert second.json()["code"] == "REFUND_NOT_ALLOWED"


def test_refund_negative_window_expired_400(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    headers, _, _ = auth_headers(email="refund_late@example.com", username="refund_late")
    topup_balance(headers=headers, amount="1000.00")
    purchase_id = _buy_for_user(client=client, headers=headers)

    STORE.purchases[purchase_id].created_at = datetime.now(UTC) - timedelta(
        minutes=settings.refund_window_minutes + 1,
    )

    response = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"purchase_id": purchase_id, "reason": "late refund request"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "REFUND_WINDOW_EXPIRED"


def test_refund_negative_forbidden_for_other_player_403(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
    topup_balance: Callable[..., dict[str, Any]],
) -> None:
    owner_headers, _, _ = auth_headers(email="refund_owner2@example.com", username="refund_owner2")
    topup_balance(headers=owner_headers, amount="1000.00")
    purchase_id = _buy_for_user(client=client, headers=owner_headers)

    stranger_headers, _, _ = auth_headers(email="refund_stranger@example.com", username="refund_stranger")
    response = client.post(
        "/api/v1/refunds",
        headers=stranger_headers,
        json={"purchase_id": purchase_id, "reason": "not my purchase"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "REFUND_FORBIDDEN"


def test_refund_negative_validation_422(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="refund_422@example.com", username="refund_422")

    response = client.post(
        "/api/v1/refunds",
        headers=headers,
        json={"purchase_id": 1, "reason": "bad"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
