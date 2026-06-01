from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_admin_create_item_positive_with_stock(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_create1@example.com", username="admin_create1")

    response = client.post(
        "/api/v1/admin/items",
        headers=headers,
        json={
            "sku": "new_sku_001",
            "name": "Epic Sword",
            "description": "Legendary sword",
            "price": "499.00",
            "stock": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["sku"] == "new_sku_001"


def test_admin_create_item_positive_without_stock(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_create2@example.com", username="admin_create2")

    response = client.post(
        "/api/v1/admin/items",
        headers=headers,
        json={
            "sku": "new_sku_002",
            "name": "Battle Pass",
            "description": "Season access",
            "price": "999.00",
            "stock": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["stock"] is None


def test_admin_create_item_negative_player_forbidden_403(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    player_headers, _, _ = auth_headers(email="player_create@example.com", username="player_create")

    response = client.post(
        "/api/v1/admin/items",
        headers=player_headers,
        json={
            "sku": "forbidden_sku",
            "name": "Forbidden Item",
            "description": "not allowed",
            "price": "100.00",
            "stock": 1,
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


def test_admin_create_item_negative_duplicate_sku_409(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_dupe@example.com", username="admin_dupe")

    first = client.post(
        "/api/v1/admin/items",
        headers=headers,
        json={
            "sku": "dupe_sku",
            "name": "One",
            "description": "first",
            "price": "100.00",
            "stock": 1,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/admin/items",
        headers=headers,
        json={
            "sku": "dupe_sku",
            "name": "Two",
            "description": "second",
            "price": "100.00",
            "stock": 1,
        },
    )

    assert second.status_code == 409
    assert second.json()["code"] == "ITEM_SKU_EXISTS"


def test_admin_update_item_positive_name_description(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_update1@example.com", username="admin_update1")

    response = client.patch(
        "/api/v1/admin/items/1",
        headers=headers,
        json={"name": "Updated Name", "description": "Updated Description"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated Name"
    assert payload["description"] == "Updated Description"


def test_admin_update_item_positive_price_stock(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_update2@example.com", username="admin_update2")

    response = client.patch(
        "/api/v1/admin/items/2",
        headers=headers,
        json={"price": "1299.00", "stock": 5},
    )

    assert response.status_code == 200
    assert response.json()["price"] == "1299.00"
    assert response.json()["stock"] == 5


def test_admin_update_item_negative_player_forbidden_403(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="player_update@example.com", username="player_update")

    response = client.patch(
        "/api/v1/admin/items/1",
        headers=headers,
        json={"name": "Should Fail"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


def test_admin_update_item_negative_not_found_404(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_update_nf@example.com", username="admin_update_nf")

    response = client.patch(
        "/api/v1/admin/items/999999",
        headers=headers,
        json={"name": "No Item"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ITEM_NOT_FOUND"


def test_admin_delete_item_positive_existing(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_delete1@example.com", username="admin_delete1")

    response = client.delete("/api/v1/admin/items/1", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["is_active"] is False


def test_admin_delete_item_positive_created_item(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_delete2@example.com", username="admin_delete2")

    created = client.post(
        "/api/v1/admin/items",
        headers=headers,
        json={
            "sku": "delete_me_sku",
            "name": "Delete Me",
            "description": None,
            "price": "10.00",
            "stock": 1,
        },
    )
    assert created.status_code == 200
    item_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/admin/items/{item_id}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["id"] == item_id


def test_admin_delete_item_negative_player_forbidden_403(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="player_delete@example.com", username="player_delete")

    response = client.delete("/api/v1/admin/items/1", headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


def test_admin_delete_item_negative_not_found_404(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_delete_nf@example.com", username="admin_delete_nf")

    response = client.delete("/api/v1/admin/items/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "ITEM_NOT_FOUND"


def test_admin_toggle_item_positive_deactivate(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_toggle1@example.com", username="admin_toggle1")

    response = client.post(
        "/api/v1/admin/items/1/toggle-active",
        headers=headers,
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_toggle_item_positive_activate(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_toggle2@example.com", username="admin_toggle2")

    off = client.post(
        "/api/v1/admin/items/1/toggle-active",
        headers=headers,
        json={"is_active": False},
    )
    assert off.status_code == 200

    on = client.post(
        "/api/v1/admin/items/1/toggle-active",
        headers=headers,
        json={"is_active": True},
    )

    assert on.status_code == 200
    assert on.json()["is_active"] is True


def test_admin_toggle_item_negative_player_forbidden_403(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="player_toggle@example.com", username="player_toggle")

    response = client.post(
        "/api/v1/admin/items/1/toggle-active",
        headers=headers,
        json={"is_active": False},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


def test_admin_toggle_item_negative_not_found_404(
    client: TestClient,
    admin_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = admin_headers(email="admin_toggle_nf@example.com", username="admin_toggle_nf")

    response = client.post(
        "/api/v1/admin/items/999999/toggle-active",
        headers=headers,
        json={"is_active": True},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ITEM_NOT_FOUND"
