from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.repositories.company import CompanyRepository


def create_company() -> Company:
    return Company(
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
    )


def test_repository_stores_session() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = CompanyRepository(session)

    assert repository._session is session


def test_get_by_id_statement_targets_company_and_id() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = CompanyRepository(session)
    company_id = uuid4()

    statement = repository._get_by_id_statement(company_id)
    compiled = statement.compile()

    assert statement.column_descriptions[0]["entity"] is Company
    assert statement.whereclause is not None
    assert company_id in compiled.params.values()


def test_exchange_ticker_statement_contains_values() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = CompanyRepository(session)

    statement = repository._get_by_exchange_and_ticker_statement(
        "NASDAQ",
        "EXM",
    )
    compiled = statement.compile()

    assert statement.column_descriptions[0]["entity"] is Company
    assert "NASDAQ" in compiled.params.values()
    assert "EXM" in compiled.params.values()


@pytest.mark.asyncio
async def test_get_by_id_returns_company() -> None:
    company = create_company()
    result = MagicMock()
    result.scalar_one_or_none.return_value = company
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repository = CompanyRepository(session)

    returned = await repository.get_by_id(uuid4())

    assert returned is company
    session.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repository = CompanyRepository(session)

    returned = await repository.get_by_id(uuid4())

    assert returned is None


@pytest.mark.asyncio
async def test_get_by_exchange_and_ticker_returns_company() -> None:
    company = create_company()
    result = MagicMock()
    result.scalar_one_or_none.return_value = company
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repository = CompanyRepository(session)

    returned = await repository.get_by_exchange_and_ticker("NASDAQ", "EXM")

    assert returned is company
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_returns_companies() -> None:
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
    scalar_result = MagicMock()
    scalar_result.all.return_value = [first, second]
    result = MagicMock()
    result.scalars.return_value = scalar_result
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repository = CompanyRepository(session)

    returned = await repository.list(offset=10, limit=25)
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert returned == [first, second]
    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()
    assert 10 in compiled.params.values()
    assert 25 in compiled.params.values()


@pytest.mark.asyncio
async def test_list_uses_default_pagination() -> None:
    scalar_result = MagicMock()
    scalar_result.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalar_result
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    repository = CompanyRepository(session)

    await repository.list()
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert 0 in compiled.params.values()
    assert 100 in compiled.params.values()


@pytest.mark.asyncio
async def test_add_adds_flushes_and_returns_company() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = CompanyRepository(session)
    company = create_company()

    returned = await repository.add(company)

    session.add.assert_called_once_with(company)
    session.flush.assert_awaited_once_with()
    assert returned is company


@pytest.mark.asyncio
async def test_update_applies_values_and_flushes() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = CompanyRepository(session)
    company = create_company()
    values: dict[str, object] = {
        "name": "Updated Company",
        "website": None,
        "is_active": False,
    }

    result = await repository.update(company, values)

    assert result is company
    assert company.name == "Updated Company"
    assert company.website is None
    assert company.is_active is False
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_update_with_empty_values_only_flushes() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = CompanyRepository(session)
    company = create_company()

    result = await repository.update(company, {})

    assert result is company
    session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_deletes_company_and_flushes() -> None:
    session = MagicMock(spec=AsyncSession)
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    repository = CompanyRepository(session)
    company = create_company()

    await repository.delete(company)

    session.delete.assert_awaited_once_with(company)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
