from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.repositories.store import STORE


def test_list_items_positive_active_only_default(client: TestClient) -> None:
    response = client.get("/api/v1/items")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 2
    assert all(item["is_active"] is True for item in payload["items"])


def test_list_items_positive_active_only_false_includes_inactive(client: TestClient) -> None:
    STORE.items[1].is_active = False

    response = client.get("/api/v1/items", params={"active_only": False})

    assert response.status_code == 200
    payload = response.json()
    item_ids = {item["id"] for item in payload["items"]}
    assert 1 in item_ids
    assert any(item["id"] == 1 and item["is_active"] is False for item in payload["items"])


def test_list_items_negative_limit_validation_422(client: TestClient) -> None:
    response = client.get("/api/v1/items", params={"limit": 0})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_list_items_negative_offset_validation_422(client: TestClient) -> None:
    response = client.get("/api/v1/items", params={"offset": -1})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_get_item_positive_first_item(client: TestClient) -> None:
    response = client.get("/api/v1/items/1")

    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_item_positive_second_item(client: TestClient) -> None:
    response = client.get("/api/v1/items/2")

    assert response.status_code == 200
    assert response.json()["id"] == 2


def test_get_item_negative_not_found_404(client: TestClient) -> None:
    response = client.get("/api/v1/items/999999")

    assert response.status_code == 404
    assert response.json()["code"] == "ITEM_NOT_FOUND"


def test_get_item_negative_path_validation_422(client: TestClient) -> None:
    response = client.get("/api/v1/items/not-an-int")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
