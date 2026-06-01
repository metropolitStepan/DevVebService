from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def test_register_positive_returns_user_and_tokens(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "player@example.com",
            "username": "player_001",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == "player@example.com"
    assert payload["tokens"]["token_type"] == "bearer"


def test_register_positive_normalizes_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "PLAYER2@Example.COM",
            "username": "player_002",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "player2@example.com"


def test_register_negative_validation_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad",
            "username": "x",
            "password": "123",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_register_negative_duplicate_email_409(client: TestClient) -> None:
    payload = {
        "email": "dupe@example.com",
        "username": "dupe_user_1",
        "password": "StrongPass123",
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dupe@example.com",
            "username": "dupe_user_2",
            "password": "StrongPass123",
        },
    )
    assert second.status_code == 409
    assert second.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_login_positive_with_registered_user(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    register_user(email="login_ok@example.com", username="login_ok")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login_ok@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "login_ok"


def test_login_positive_email_case_insensitive(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    register_user(email="case_login@example.com", username="case_login")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "CASE_LOGIN@EXAMPLE.COM", "password": "StrongPass123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "case_login@example.com"


def test_login_negative_invalid_credentials_401(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    register_user(email="badpass@example.com", username="badpass")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "badpass@example.com", "password": "WrongPass123"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_negative_validation_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "bad", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_refresh_positive_rotates_tokens(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    auth_payload = register_user(email="refresh_ok@example.com", username="refresh_ok")
    refresh_token = auth_payload["tokens"]["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
    assert refreshed["refresh_token"] != refresh_token


def test_refresh_positive_token_can_be_used_for_me(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    auth_payload = register_user(email="refresh_me@example.com", username="refresh_me")

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_payload["tokens"]["refresh_token"]},
    )
    assert refresh_response.status_code == 200

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_response.json()['access_token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "refresh_me@example.com"


def test_refresh_negative_invalid_token_401(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_refresh_negative_reuse_old_refresh_token_401(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    auth_payload = register_user(email="refresh_reuse@example.com", username="refresh_reuse")
    token = auth_payload["tokens"]["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert first.status_code == 200

    second = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert second.status_code == 401
    assert second.json()["code"] == "INVALID_REFRESH_TOKEN"


def test_me_positive_returns_current_user(
    client: TestClient,
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> None:
    headers, _, _ = auth_headers(email="me_ok@example.com", username="me_ok")

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "me_ok@example.com"


def test_me_positive_after_login(
    client: TestClient,
    register_user: Callable[..., dict[str, Any]],
) -> None:
    register_user(email="me_login@example.com", username="me_login")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "me_login@example.com", "password": "StrongPass123"},
    )
    token = login.json()["tokens"]["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "me_login"


def test_me_negative_without_token_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_me_negative_invalid_auth_scheme_401(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Basic abcdef"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
