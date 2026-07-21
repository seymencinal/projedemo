from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository


def create_organization() -> Organization:
    return Organization(name="Example", slug="example")


def test_repository_stores_session() -> None:
    session = MagicMock(spec=AsyncSession)

    assert OrganizationRepository(session)._session is session


@pytest.mark.asyncio
async def test_get_by_id_returns_matching_organization() -> None:
    organization = create_organization()
    result = MagicMock()
    result.scalar_one_or_none.return_value = organization
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    organization_id = uuid4()

    returned = await OrganizationRepository(session).get_by_id(organization_id)

    assert returned is organization
    assert organization_id in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_get_by_slug_returns_none_when_missing() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await OrganizationRepository(session).get_by_slug("missing")

    assert returned is None
    assert "missing" in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_list_orders_by_name() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = [create_organization()]
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await OrganizationRepository(session).list()

    assert [organization.slug for organization in returned] == ["example"]
    assert "ORDER BY organizations.name ASC" in str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_add_flushes_without_committing() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = OrganizationRepository(session)
    organization = create_organization()

    assert await repository.add(organization) is organization
    session.add.assert_called_once_with(organization)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_called()
