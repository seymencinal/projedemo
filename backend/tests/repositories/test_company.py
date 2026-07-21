from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.repositories.company import CompanyRepository

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")


def create_company() -> Company:
    return Company(
        organization_id=ORGANIZATION_ID,
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
    )


def test_get_by_id_statement_contains_company_and_organization_ids() -> None:
    repository = CompanyRepository(MagicMock(spec=AsyncSession))
    company_id = uuid4()

    compiled = repository._get_by_id_statement(company_id, ORGANIZATION_ID).compile()

    assert company_id in compiled.params.values()
    assert ORGANIZATION_ID in compiled.params.values()


def test_exchange_ticker_statement_contains_organization_and_values() -> None:
    repository = CompanyRepository(MagicMock(spec=AsyncSession))

    compiled = repository._get_by_exchange_and_ticker_statement(
        ORGANIZATION_ID, "NASDAQ", "EXM"
    ).compile()

    assert {ORGANIZATION_ID, "NASDAQ", "EXM"} <= set(compiled.params.values())


@pytest.mark.asyncio
async def test_get_by_id_uses_organization_scope() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = create_company()
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await CompanyRepository(session).get_by_id(uuid4(), ORGANIZATION_ID)

    assert returned is not None
    assert returned.organization_id == ORGANIZATION_ID
    assert ORGANIZATION_ID in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_get_by_exchange_and_ticker_returns_none_when_no_scoped_match() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await CompanyRepository(session).get_by_exchange_and_ticker(
        ORGANIZATION_ID, "NYSE", "MISSING"
    )

    assert returned is None
    assert {ORGANIZATION_ID, "NYSE", "MISSING"} <= set(
        session.execute.await_args.args[0].compile().params.values()
    )


@pytest.mark.asyncio
async def test_list_uses_organization_scope_and_pagination() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = [create_company()]
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await CompanyRepository(session).list(ORGANIZATION_ID, offset=10, limit=25)

    assert returned[0].organization_id == ORGANIZATION_ID
    values = session.execute.await_args.args[0].compile().params.values()
    assert {ORGANIZATION_ID, 10, 25} <= set(values)


@pytest.mark.asyncio
async def test_add_update_and_delete_keep_repository_transaction_neutral() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    repository = CompanyRepository(session)
    company = create_company()

    assert await repository.add(company) is company
    assert await repository.update(company, {"name": "Updated"}) is company
    await repository.delete(company)

    assert company.name == "Updated"
    assert session.flush.await_count == 3
    session.delete.assert_awaited_once_with(company)
