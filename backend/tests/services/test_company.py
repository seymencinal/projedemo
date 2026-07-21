from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.company import CompanyService


def create_company() -> Company:
    return Company(
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
    )


def create_payload() -> CompanyCreate:
    return CompanyCreate(
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
        isin="US1234567890",
        website="https://example.com",
        description="Example description",
        is_active=True,
    )


def test_service_creates_repository_when_not_provided() -> None:
    session = MagicMock(spec=AsyncSession)
    service = CompanyService(session)

    assert service._session is session
    assert isinstance(service._repository, CompanyRepository)
    assert service._repository._session is session


def test_service_uses_provided_repository() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = MagicMock(spec=CompanyRepository)
    service = CompanyService(
        session=session,
        repository=repository,
    )

    assert service._session is session
    assert service._repository is repository


@pytest.mark.asyncio
async def test_get_by_id_returns_company() -> None:
    company = create_company()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    service = CompanyService(
        session=MagicMock(spec=AsyncSession),
        repository=repository,
    )
    company_id = uuid4()

    returned = await service.get_by_id(company_id)

    assert returned is company
    repository.get_by_id.assert_awaited_once_with(company_id)


@pytest.mark.asyncio
async def test_get_by_id_raises_when_company_is_missing() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=None)
    service = CompanyService(
        session=MagicMock(spec=AsyncSession),
        repository=repository,
    )
    company_id = uuid4()

    with pytest.raises(CompanyNotFoundError) as exc_info:
        await service.get_by_id(company_id)

    assert exc_info.value.company_id == company_id
    repository.get_by_id.assert_awaited_once_with(company_id)


@pytest.mark.asyncio
async def test_list_delegates_to_repository() -> None:
    first = Company(
        name="Alpha",
        ticker="ALP",
        exchange="NASDAQ",
    )
    second = Company(
        name="Beta",
        ticker="BET",
        exchange="NYSE",
    )
    repository = MagicMock(spec=CompanyRepository)
    repository.list = AsyncMock(return_value=[first, second])
    service = CompanyService(
        session=MagicMock(spec=AsyncSession),
        repository=repository,
    )

    returned = await service.list(
        offset=10,
        limit=25,
    )

    assert returned == [first, second]
    repository.list.assert_awaited_once_with(
        offset=10,
        limit=25,
    )


@pytest.mark.asyncio
async def test_list_uses_default_pagination() -> None:
    repository = MagicMock(spec=CompanyRepository)
    repository.list = AsyncMock(return_value=[])
    service = CompanyService(
        session=MagicMock(spec=AsyncSession),
        repository=repository,
    )

    await service.list()

    repository.list.assert_awaited_once_with(
        offset=0,
        limit=100,
    )


@pytest.mark.asyncio
async def test_create_adds_commits_refreshes_and_returns_company() -> None:
    payload = create_payload()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=None)
    repository.add = AsyncMock(side_effect=lambda company: company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(
        session=session,
        repository=repository,
    )

    returned = await service.create(payload)
    added_company = repository.add.await_args.args[0]

    repository.get_by_exchange_and_ticker.assert_awaited_once_with(
        "NASDAQ",
        "EXM",
    )
    repository.add.assert_awaited_once()
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(returned)
    assert isinstance(returned, Company)
    assert returned.name == payload.name
    assert returned.ticker == payload.ticker
    assert returned.exchange == payload.exchange
    assert returned.isin == payload.isin
    assert returned.website == payload.website
    assert returned.description == payload.description
    assert returned.is_active == payload.is_active
    assert returned is added_company


@pytest.mark.asyncio
async def test_create_returns_repository_result() -> None:
    payload = create_payload()
    persisted_company = Company(
        name="Persisted Company",
        ticker="PER",
        exchange="NYSE",
    )
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=None)
    repository.add = AsyncMock(return_value=persisted_company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(
        session=session,
        repository=repository,
    )

    returned = await service.create(payload)

    assert returned is persisted_company
    session.refresh.assert_awaited_once_with(persisted_company)


@pytest.mark.asyncio
async def test_create_raises_when_company_already_exists() -> None:
    payload = create_payload()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=create_company())
    repository.add = AsyncMock()
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(
        session=session,
        repository=repository,
    )

    with pytest.raises(CompanyAlreadyExistsError) as exc_info:
        await service.create(payload)

    assert exc_info.value.exchange == payload.exchange
    assert exc_info.value.ticker == payload.ticker
    repository.get_by_exchange_and_ticker.assert_awaited_once_with(
        payload.exchange,
        payload.ticker,
    )
    repository.add.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_preserves_exchange_and_ticker_for_duplicate_check() -> None:
    payload = CompanyCreate(
        name="Example Company",
        ticker="exm",
        exchange=" nasdaq ",
    )
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=create_company())
    service = CompanyService(
        session=MagicMock(spec=AsyncSession),
        repository=repository,
    )

    with pytest.raises(CompanyAlreadyExistsError) as exc_info:
        await service.create(payload)

    repository.get_by_exchange_and_ticker.assert_awaited_once_with(
        " nasdaq ",
        "exm",
    )
    assert exc_info.value.exchange == " nasdaq "
    assert exc_info.value.ticker == "exm"


@pytest.mark.asyncio
async def test_update_updates_company_and_commits() -> None:
    company = create_company()
    company.id = uuid4()
    payload = CompanyUpdate(
        name="Updated Company",
        website=None,
        is_active=False,
    )
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    result = await service.update(company.id, payload)
    updated_company, values = repository.update.await_args.args

    assert result is company
    repository.get_by_id.assert_awaited_once_with(company.id)
    repository.update.assert_awaited_once()
    assert updated_company is company
    assert values == {
        "name": "Updated Company",
        "website": None,
        "is_active": False,
    }
    repository.get_by_exchange_and_ticker.assert_not_awaited()
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(company)


@pytest.mark.asyncio
async def test_update_raises_when_company_not_found() -> None:
    company_id = uuid4()
    payload = CompanyUpdate(name="Updated Company")
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=None)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    with pytest.raises(CompanyNotFoundError) as exc_info:
        await service.update(company_id, payload)

    assert exc_info.value.company_id == company_id
    repository.update.assert_not_awaited()
    repository.get_by_exchange_and_ticker.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_raises_when_exchange_and_ticker_belong_to_another_company() -> None:
    company = create_company()
    company.id = uuid4()
    other_company = create_company()
    other_company.id = uuid4()
    payload = CompanyUpdate(exchange="NYSE", ticker="OTHER")
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=other_company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    with pytest.raises(CompanyAlreadyExistsError) as exc_info:
        await service.update(company.id, payload)

    assert exc_info.value.exchange == "NYSE"
    assert exc_info.value.ticker == "OTHER"
    repository.update.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_allows_exchange_and_ticker_of_same_company() -> None:
    company = create_company()
    company.id = uuid4()
    payload = CompanyUpdate(exchange="NASDAQ", ticker="EXM")
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=company)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    result = await service.update(company.id, payload)

    assert result is company
    repository.update.assert_awaited_once()
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(company)


@pytest.mark.asyncio
async def test_update_uses_existing_exchange_when_only_ticker_changes() -> None:
    company = create_company()
    company.id = uuid4()
    payload = CompanyUpdate(ticker="NEW")
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=None)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    await service.update(company.id, payload)

    repository.get_by_exchange_and_ticker.assert_awaited_once_with(
        exchange="NASDAQ",
        ticker="NEW",
    )


@pytest.mark.asyncio
async def test_update_uses_existing_ticker_when_only_exchange_changes() -> None:
    company = create_company()
    company.id = uuid4()
    payload = CompanyUpdate(exchange="NYSE")
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.get_by_exchange_and_ticker = AsyncMock(return_value=None)
    repository.update = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    await service.update(company.id, payload)

    repository.get_by_exchange_and_ticker.assert_awaited_once_with(
        exchange="NYSE",
        ticker="EXM",
    )


@pytest.mark.asyncio
async def test_update_with_empty_payload_returns_company_without_transaction() -> None:
    company = create_company()
    company.id = uuid4()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    result = await service.update(company.id, CompanyUpdate())

    assert result is company
    repository.update.assert_not_awaited()
    repository.get_by_exchange_and_ticker.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_deletes_company_and_commits() -> None:
    company = create_company()
    company.id = uuid4()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=company)
    repository.delete = AsyncMock()
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    await service.delete(company.id)

    repository.get_by_id.assert_awaited_once_with(company.id)
    repository.delete.assert_awaited_once_with(company)
    session.commit.assert_awaited_once_with()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_raises_when_company_not_found() -> None:
    company_id = uuid4()
    repository = MagicMock(spec=CompanyRepository)
    repository.get_by_id = AsyncMock(return_value=None)
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = CompanyService(session=session, repository=repository)

    with pytest.raises(CompanyNotFoundError) as exc_info:
        await service.delete(company_id)

    assert exc_info.value.company_id == company_id
    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()
