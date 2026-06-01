from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.mark.db
@pytest.mark.asyncio
async def test_test_database_url_isolated(
    db_engine: AsyncEngine,
    test_database_url: str,
) -> None:
    assert "_test" in test_database_url

    async with db_engine.connect() as connection:
        value = await connection.scalar(text("SELECT 1"))

    assert value == 1


@pytest.mark.db
@pytest.mark.asyncio
async def test_db_session_executes_queries(db_session: AsyncSession) -> None:
    value = await db_session.scalar(text("SELECT 1"))
    assert value == 1
