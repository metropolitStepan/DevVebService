from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


engine = create_async_engine(settings.database_url, echo=settings.sql_echo, future=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def close_db() -> None:
    await engine.dispose()


async def check_db_health() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
