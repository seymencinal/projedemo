from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import DatabaseResources


def get_database_resources(request: Request) -> DatabaseResources | None:
    return getattr(request.app.state, "database", None)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = get_database_resources(request)
    if database is None:
        raise RuntimeError("Database resources are not initialized.")

    async with database.session_factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
