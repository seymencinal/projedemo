from dataclasses import dataclass

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


@dataclass(frozen=True)
class DatabaseResources:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def build_database_url(settings: Settings) -> URL:
    if settings.database_user is None or settings.database_password is None:
        raise RuntimeError("Database credentials are not configured.")

    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.database_user,
        password=settings.database_password.get_secret_value(),
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
    )


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        build_database_url(settings),
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def create_database_resources(settings: Settings) -> DatabaseResources:
    engine = create_database_engine(settings)
    return DatabaseResources(
        engine=engine,
        session_factory=create_session_factory(engine),
    )


async def dispose_database_resources(resources: DatabaseResources) -> None:
    await resources.engine.dispose()
