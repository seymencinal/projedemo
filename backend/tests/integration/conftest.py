import asyncio
import os
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.core.config import get_settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip(
            "TEST_DATABASE_URL is not configured",
            allow_module_level=True,
        )

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("TEST_DATABASE_URL must use PostgreSQL")
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("TEST_DATABASE_URL must use the postgresql+psycopg async driver")
    return database_url


@contextmanager
def test_database_settings(url: URL) -> Iterator[None]:
    environment_values = {
        "DATABASE_HOST": url.host or "",
        "DATABASE_PORT": str(url.port or 5432),
        "DATABASE_NAME": url.database or "",
        "DATABASE_USER": url.username or "",
        "DATABASE_PASSWORD": url.password or "",
    }
    previous_values = {key: os.environ.get(key) for key in environment_values}

    os.environ.update(environment_values)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for key, value in previous_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated_test_database() -> str:
    database_url = get_test_database_url()
    url = make_url(database_url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    with test_database_settings(url):
        command.upgrade(config, "head")

    return database_url


@pytest_asyncio.fixture
async def integration_engine(
    migrated_test_database: str,
) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        migrated_test_database,
        pool_pre_ping=True,
    )

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def integration_connection(
    integration_engine: AsyncEngine,
) -> AsyncIterator[AsyncConnection]:
    async with integration_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest_asyncio.fixture
async def integration_session(
    integration_connection: AsyncConnection,
) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(
        bind=integration_connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session
