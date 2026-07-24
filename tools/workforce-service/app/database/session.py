from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings


def _sqlite_async_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return database_url


def _engine_options(database_url: str) -> dict:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return {}

    database = url.database
    if database and database != ":memory:":
        Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)

    options: dict = {"connect_args": {"check_same_thread": False}}
    if database == ":memory:":
        options["poolclass"] = StaticPool
    return options


def _create_engine(database_url: str):
    return create_async_engine(_sqlite_async_url(database_url), echo=False, **_engine_options(database_url))


engine = _create_engine(get_settings().database_url)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def configure_database(database_url: str) -> None:
    global engine, async_session
    await engine.dispose()
    engine = _create_engine(database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
