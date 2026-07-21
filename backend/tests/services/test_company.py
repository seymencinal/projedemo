from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.company import CompanyAlreadyExistsError, CompanyNotFoundError
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.company import CompanyService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")


def create_company() -> Company:
    return Company(
        organization_id=ORGANIZATION_ID,
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
    )


def create_payload() -> CompanyCreate:
    return CompanyCreate(name="Example Company", ticker="EXM", exchange="NASDAQ")


def create_service(repository: MagicMock, session: MagicMock | None = None) -> CompanyService:
    return CompanyService(session or MagicMock(spec=AsyncSession), repository=repository)


def test_service_creates_repository_when_not_provided() -> None:
    session = MagicMock(spec=AsyncSession)
    service = CompanyService(session)

    assert isinstance(service._repository, CompanyRepository)
    assert service._repository._session is session


@pytest.mark.asyncio
async def test_get_by_id_scopes_lookup_to_organization() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)

    returned = await create_service(repository).get_by_id(company.id, ORGANIZATION_ID)

    assert returned is company
    repository.get_by_id.assert_awaited_once_with(company.id, ORGANIZATION_ID)


@pytest.mark.asyncio
async def test_get_by_id_does_not_return_company_from_another_organization() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=None)
    company_id = uuid4()

    with pytest.raises(CompanyNotFoundError):
        await create_service(repository).get_by_id(company_id, ORGANIZATION_ID)

    repository.get_by_id.assert_awaited_once_with(company_id, ORGANIZATION_ID)


@pytest.mark.asyncio
async def test_list_scopes_results_to_organization() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.list = AsyncMock(return_value=[create_company()])

    returned = await create_service(repository).list(ORGANIZATION_ID, offset=10, limit=25)

    assert len(returned) == 1
    repository.list.assert_awaited_once_with(ORGANIZATION_ID, offset=10, limit=25)


@pytest.mark.asyncio
async def test_create_sets_organization_and_checks_duplicate_in_same_organization() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=None)
    repository.add = AsyncMock(side_effect=lambda company: company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    company = await create_service(repository, session).create(ORGANIZATION_ID, create_payload())

    assert company.organization_id == ORGANIZATION_ID
    repository.get_by_exchange_and_ticker.assert_awaited_once_with(ORGANIZATION_ID, "NASDAQ", "EXM")
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(company)


@pytest.mark.asyncio
async def test_create_rejects_duplicate_in_same_organization() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=create_company())

    with pytest.raises(CompanyAlreadyExistsError):
        await create_service(repository).create(ORGANIZATION_ID, create_payload())


@pytest.mark.asyncio
async def test_update_scopes_company_lookup_and_duplicate_check() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=None)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    returned = await create_service(repository, session).update(
        company.id,
        ORGANIZATION_ID,
        CompanyUpdate(ticker="NEW"),
    )

    assert returned is company
    repository.get_by_id.assert_awaited_once_with(company.id, ORGANIZATION_ID)
    repository.get_by_exchange_and_ticker.assert_awaited_once_with(
        ORGANIZATION_ID, exchange="NASDAQ", ticker="NEW"
    )
    repository.update.assert_awaited_once_with(company, {"ticker": "NEW"})


@pytest.mark.asyncio
async def test_update_rejects_company_outside_organization() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=None)
    company_id = uuid4()

    with pytest.raises(CompanyNotFoundError):
        await create_service(repository).update(
            company_id, ORGANIZATION_ID, CompanyUpdate(name="Updated")
        )


@pytest.mark.asyncio
async def test_update_with_empty_payload_returns_scoped_company_without_transaction() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    returned = await create_service(repository, session).update(
        company.id, ORGANIZATION_ID, CompanyUpdate()
    )

    assert returned is company
    repository.update.assert_not_awaited()
    repository.get_by_exchange_and_ticker.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_non_identity_fields_skips_duplicate_lookup() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    returned = await create_service(repository, session).update(
        company.id, ORGANIZATION_ID, CompanyUpdate(name="Updated")
    )

    assert returned is company
    repository.get_by_exchange_and_ticker.assert_not_awaited()
    repository.update.assert_awaited_once_with(company, {"name": "Updated"})


@pytest.mark.asyncio
async def test_update_allows_existing_exchange_and_ticker_on_same_company() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=company)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    returned = await create_service(repository, session).update(
        company.id,
        ORGANIZATION_ID,
        CompanyUpdate(exchange=company.exchange, ticker=company.ticker),
    )

    assert returned is company
    repository.update.assert_awaited_once_with(
        company,
        {"exchange": company.exchange, "ticker": company.ticker},
    )


@pytest.mark.asyncio
async def test_update_rejects_duplicate_in_same_organization() -> None:
    company = create_company()
    duplicate = create_company()
    duplicate.id = uuid4()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=duplicate)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    with pytest.raises(CompanyAlreadyExistsError):
        await create_service(repository, session).update(
            company.id,
            ORGANIZATION_ID,
            CompanyUpdate(ticker="OTHER"),
        )

    repository.update.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_scopes_company_lookup() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.delete = AsyncMock()
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()

    await create_service(repository, session).delete(company.id, ORGANIZATION_ID)

    repository.get_by_id.assert_awaited_once_with(company.id, ORGANIZATION_ID)
    repository.delete.assert_awaited_once_with(company)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_rejects_company_outside_organization() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(CompanyNotFoundError):
        await create_service(repository).delete(uuid4(), ORGANIZATION_ID)
