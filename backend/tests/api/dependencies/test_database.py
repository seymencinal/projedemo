from collections.abc import AsyncGenerator
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.database import get_db_session


@pytest.mark.asyncio
async def test_get_db_session_yields_factory_session() -> None:
    session = MagicMock(spec=AsyncSession)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.api.dependencies.database.async_session_factory",
        return_value=context_manager,
    ) as factory:
        dependency = cast(AsyncGenerator[AsyncSession, None], get_db_session())
        yielded_session = await anext(dependency)

        assert yielded_session is session
        factory.assert_called_once_with()
        context_manager.__aenter__.assert_awaited_once_with()

        await dependency.aclose()

    context_manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_exits_context_after_iteration() -> None:
    session = MagicMock(spec=AsyncSession)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.api.dependencies.database.async_session_factory",
        return_value=context_manager,
    ):
        yielded_sessions = [yielded async for yielded in get_db_session()]

    assert yielded_sessions == [session]
    context_manager.__aenter__.assert_awaited_once_with()
    context_manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_does_not_manage_transaction() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=session)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.api.dependencies.database.async_session_factory",
        return_value=context_manager,
    ):
        _ = [yielded async for yielded in get_db_session()]

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
