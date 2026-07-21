from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.database import get_database_resources, get_db_session
from app.db.session import DatabaseResources


def create_request(database: DatabaseResources | None) -> MagicMock:
    request = MagicMock()
    request.app.state = SimpleNamespace(database=database)
    return request


@pytest.mark.asyncio
async def test_get_db_session_yields_factory_session() -> None:
    session = MagicMock(spec=AsyncSession)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    session_factory = MagicMock(return_value=context_manager)
    database = DatabaseResources(
        engine=MagicMock(),
        session_factory=session_factory,
    )
    request = create_request(database)
    dependency = cast(AsyncGenerator[AsyncSession, None], get_db_session(request))
    yielded_session = await anext(dependency)

    assert yielded_session is session
    session_factory.assert_called_once_with()
    context_manager.__aenter__.assert_awaited_once_with()

    await dependency.aclose()

    context_manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_exits_context_after_iteration() -> None:
    session = MagicMock(spec=AsyncSession)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    database = DatabaseResources(
        engine=MagicMock(),
        session_factory=MagicMock(return_value=context_manager),
    )
    yielded_sessions = [yielded async for yielded in get_db_session(create_request(database))]

    assert yielded_sessions == [session]
    context_manager.__aenter__.assert_awaited_once_with()
    context_manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_rolls_back_when_request_handling_fails() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    database = DatabaseResources(
        engine=MagicMock(),
        session_factory=MagicMock(return_value=context_manager),
    )
    dependency = cast(AsyncGenerator[AsyncSession, None], get_db_session(create_request(database)))
    await anext(dependency)

    with pytest.raises(RuntimeError, match="request failed"):
        await dependency.athrow(RuntimeError("request failed"))

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()


def test_get_database_resources_returns_application_state_resource() -> None:
    database = DatabaseResources(
        engine=MagicMock(),
        session_factory=MagicMock(),
    )

    assert get_database_resources(create_request(database)) is database


def test_get_database_resources_returns_none_before_lifespan_startup() -> None:
    request = MagicMock()
    request.app.state = SimpleNamespace()

    assert get_database_resources(request) is None


@pytest.mark.asyncio
async def test_get_db_session_rejects_requests_before_database_startup() -> None:
    with pytest.raises(RuntimeError, match="Database resources are not initialized"):
        await anext(get_db_session(create_request(None)))
