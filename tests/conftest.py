from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator, Callable, Generator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.repositories.store import STORE
from app.main import app
from app.models import Base


def _derive_test_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        if database_url.endswith(".db"):
            return database_url.replace(".db", "_test.db")
        return "sqlite+aiosqlite:///./.pytest/test.db"

    pattern = re.compile(r"(?P<prefix>.+/)(?P<name>[^/?]+)(?P<suffix>(\?.*)?)$")
    match = pattern.match(database_url)
    if match is None:
        return database_url

    db_name = match.group("name")
    if not db_name.endswith("_test"):
        db_name = f"{db_name}_test"

    return f"{match.group('prefix')}{db_name}{match.group('suffix')}"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", _derive_test_database_url(settings.database_url))


@pytest_asyncio.fixture(scope="session")
async def db_engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_database_url, future=True, echo=False)

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    except Exception as error:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Test DB is unavailable: {test_database_url}. Error: {error}")

    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture(autouse=True)
def reset_store() -> None:
    STORE.reset()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def register_user(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _register(
        *,
        email: str | None = None,
        username: str | None = None,
        password: str = "StrongPass123",
    ) -> dict[str, Any]:
        unique = uuid4().hex[:8]
        payload = {
            "email": email or f"user_{unique}@example.com",
            "username": username or f"user_{unique}",
            "password": password,
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _register


@pytest.fixture()
def auth_headers(
    register_user: Callable[..., dict[str, Any]],
) -> Callable[..., tuple[dict[str, str], int, dict[str, Any]]]:
    def _auth_headers(
        *,
        email: str | None = None,
        username: str | None = None,
        password: str = "StrongPass123",
    ) -> tuple[dict[str, str], int, dict[str, Any]]:
        response_payload = register_user(email=email, username=username, password=password)
        token = response_payload["tokens"]["access_token"]
        user_id = int(response_payload["user"]["id"])
        headers = {"Authorization": f"Bearer {token}"}
        return headers, user_id, response_payload

    return _auth_headers


@pytest.fixture()
def admin_headers(
    auth_headers: Callable[..., tuple[dict[str, str], int, dict[str, Any]]],
) -> Callable[..., tuple[dict[str, str], int, dict[str, Any]]]:
    def _admin_headers(
        *,
        email: str | None = None,
        username: str | None = None,
        password: str = "StrongPass123",
    ) -> tuple[dict[str, str], int, dict[str, Any]]:
        headers, user_id, payload = auth_headers(email=email, username=username, password=password)
        STORE.users[user_id].role = "admin"
        return headers, user_id, payload

    return _admin_headers


@pytest.fixture()
def topup_balance(client: TestClient) -> Callable[..., dict[str, Any]]:
    def _topup(
        *,
        headers: dict[str, str],
        amount: str = "1000.00",
        reason: str = "test topup",
        external_ref: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": amount,
            "reason": reason,
        }
        if external_ref is not None:
            payload["external_ref"] = external_ref

        response = client.post("/api/v1/wallet/topup", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _topup


@pytest.fixture()
def create_purchase(client: TestClient) -> Callable[..., tuple[dict[str, Any], str]]:
    def _create_purchase(
        *,
        headers: dict[str, str],
        item_id: int = 1,
        quantity: int = 1,
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        key = idempotency_key or str(uuid4())
        response = client.post(
            "/api/v1/purchases",
            headers={**headers, "Idempotency-Key": key},
            json={"item_id": item_id, "quantity": quantity},
        )
        assert response.status_code == 201, response.text
        return response.json(), key

    return _create_purchase
