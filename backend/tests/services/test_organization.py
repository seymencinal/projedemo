from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.organization import OrganizationAlreadyExistsError, OrganizationNotFoundError
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import OrganizationCreate
from app.services.organization import OrganizationService


@pytest.mark.asyncio
async def test_create_organization_normalizes_slug_and_commits() -> None:
    repository = MagicMock(spec=OrganizationRepository)
    repository.get_by_slug = AsyncMock(return_value=None)
    repository.add = AsyncMock(side_effect=lambda organization: organization)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = OrganizationService(session, repository)

    organization = await service.create(OrganizationCreate(name="Example", slug="example"))

    assert organization.slug == "example"
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(organization)


@pytest.mark.asyncio
async def test_create_rejects_duplicate_slug() -> None:
    repository = MagicMock(spec=OrganizationRepository)
    repository.get_by_slug = AsyncMock(return_value=Organization(name="Example", slug="example"))

    with pytest.raises(OrganizationAlreadyExistsError):
        await OrganizationService(MagicMock(spec=AsyncSession), repository).create(
            OrganizationCreate(name="Example", slug="example")
        )


@pytest.mark.asyncio
async def test_get_by_id_and_list_delegate_to_repository() -> None:
    organization = Organization(name="Example", slug="example")
    repository = MagicMock(spec=OrganizationRepository)
    repository.get_by_id = AsyncMock(return_value=organization)
    repository.list = AsyncMock(return_value=[organization])
    service = OrganizationService(MagicMock(spec=AsyncSession), repository)
    organization_id = uuid4()

    assert await service.get_by_id(organization_id) is organization
    assert await service.list() == [organization]
    repository.get_by_id.assert_awaited_once_with(organization_id)


@pytest.mark.asyncio
async def test_get_by_id_rejects_unknown_organization() -> None:
    repository = MagicMock(spec=OrganizationRepository)
    repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(OrganizationNotFoundError):
        await OrganizationService(MagicMock(spec=AsyncSession), repository).get_by_id(uuid4())
