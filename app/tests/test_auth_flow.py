from fastapi.testclient import TestClient

from app.db.repositories.store import STORE
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    STORE.reset()


def test_register_login_me() -> None:
    register_payload = {
        "email": "player@example.com",
        "username": "player_1",
        "password": "strong-pass-123",
    }
    register_response = client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "player@example.com", "password": "strong-pass-123"},
    )
    assert login_response.status_code == 200

    access_token = login_response.json()["tokens"]["access_token"]
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "player@example.com"
