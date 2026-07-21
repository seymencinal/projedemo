from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.api.dependencies.database import get_database_resources
from app.api.routes.general import router as general_router
from app.db.session import DatabaseResources
from app.models.company import Company
from app.models.organization import Organization
from app.repositories.company import CompanyRepository

pytestmark = pytest.mark.integration

BOOTSTRAP_ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000001")


def create_company(
    *,
    name: str = "Example Company",
    ticker: str = "EXM",
    exchange: str = "NASDAQ",
    isin: str | None = "US1234567890",
) -> Company:
    return Company(
        organization_id=BOOTSTRAP_ORGANIZATION_ID,
        name=name,
        ticker=ticker,
        exchange=exchange,
        isin=isin,
        website="https://example.com",
        description="Example description",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_companies_table_exists(
    integration_session: AsyncSession,
) -> None:
    result = await integration_session.execute(
        text("SELECT to_regclass('public.companies')"),
    )

    assert result.scalar_one() == "companies"


@pytest.mark.asyncio
async def test_add_persists_company(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    company = create_company()

    result = await repository.add(company)
    row = await integration_session.scalar(select(Company).where(Company.id == company.id))

    assert result is company
    assert company.id is not None
    assert company.created_at is not None
    assert company.updated_at is not None
    assert row is company


@pytest.mark.asyncio
async def test_get_by_id_returns_persisted_company(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    company = create_company()
    await repository.add(company)
    company_id = company.id
    integration_session.expunge_all()

    result = await repository.get_by_id(company_id, BOOTSTRAP_ORGANIZATION_ID)

    assert result is not None
    assert result.id == company_id
    assert result.name == "Example Company"
    assert result.ticker == "EXM"
    assert result.exchange == "NASDAQ"


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)

    result = await repository.get_by_id(uuid4(), BOOTSTRAP_ORGANIZATION_ID)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_exchange_and_ticker_returns_persisted_company(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    company = create_company()
    await repository.add(company)

    result = await repository.get_by_exchange_and_ticker(BOOTSTRAP_ORGANIZATION_ID, "NASDAQ", "EXM")

    assert result is not None
    assert result.id == company.id
    assert result.exchange == "NASDAQ"
    assert result.ticker == "EXM"


@pytest.mark.asyncio
async def test_get_by_exchange_and_ticker_returns_none_when_missing(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)

    result = await repository.get_by_exchange_and_ticker(
        BOOTSTRAP_ORGANIZATION_ID, "NYSE", "MISSING"
    )

    assert result is None


@pytest.mark.asyncio
async def test_list_applies_pagination_and_name_ordering(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    for name, ticker, isin in (
        ("Alpha", "ALP", "US1234567891"),
        ("Beta", "BET", "US1234567892"),
        ("Gamma", "GAM", "US1234567893"),
    ):
        await repository.add(create_company(name=name, ticker=ticker, isin=isin))

    result = await repository.list(BOOTSTRAP_ORGANIZATION_ID, offset=1, limit=1)

    assert len(result) == 1
    assert result[0].name == "Beta"


@pytest.mark.asyncio
async def test_update_persists_values(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    company = create_company()
    await repository.add(company)

    result = await repository.update(
        company,
        {
            "name": "Updated Company",
            "website": None,
            "is_active": False,
        },
    )
    company_id = company.id
    integration_session.expunge_all()
    persisted_company = await integration_session.scalar(
        select(Company).where(Company.id == company_id),
    )

    assert result is company
    assert company.name == "Updated Company"
    assert company.website is None
    assert company.is_active is False
    assert persisted_company is not None
    assert persisted_company.name == "Updated Company"
    assert persisted_company.website is None
    assert persisted_company.is_active is False


@pytest.mark.asyncio
async def test_delete_removes_company(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    company = create_company()
    await repository.add(company)
    company_id = company.id

    await repository.delete(company)
    result = await integration_session.scalar(select(Company).where(Company.id == company_id))

    assert result is None


@pytest.mark.asyncio
async def test_unique_exchange_and_ticker_constraint(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    await repository.add(create_company(isin="US1234567891"))

    async with integration_session.begin_nested():
        integration_session.add(create_company(isin="US1234567892"))
        with pytest.raises(IntegrityError):
            await integration_session.flush()


@pytest.mark.asyncio
async def test_unique_isin_constraint(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    await repository.add(create_company(isin="US1234567891"))

    async with integration_session.begin_nested():
        integration_session.add(
            create_company(
                ticker="OTHER",
                exchange="NYSE",
                isin="US1234567891",
            )
        )
        with pytest.raises(IntegrityError):
            await integration_session.flush()


@pytest.mark.asyncio
async def test_nullable_isin_permits_multiple_nulls(
    integration_session: AsyncSession,
) -> None:
    repository = CompanyRepository(integration_session)
    first = create_company(isin=None)
    second = create_company(ticker="OTHER", exchange="NYSE", isin=None)

    await repository.add(first)
    await repository.add(second)

    assert first.id is not None
    assert second.id is not None
    assert first.id != second.id


@pytest.mark.asyncio
async def test_repository_does_not_return_companies_from_another_organization(
    integration_session: AsyncSession,
) -> None:
    other_organization = Organization(name="Other", slug=f"other-{uuid4().hex[:8]}")
    integration_session.add(other_organization)
    await integration_session.flush()
    company = create_company()
    company.organization_id = other_organization.id
    repository = CompanyRepository(integration_session)
    await repository.add(company)

    assert await repository.get_by_id(company.id, BOOTSTRAP_ORGANIZATION_ID) is None
    assert await repository.list(BOOTSTRAP_ORGANIZATION_ID) == []


@pytest.mark.asyncio
async def test_integration_test_runs_inside_transaction(
    integration_connection: AsyncConnection,
) -> None:
    assert integration_connection.in_transaction()


@pytest.mark.asyncio
async def test_readiness_checks_postgresql_connectivity(
    integration_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(bind=integration_engine)
    database = DatabaseResources(
        engine=integration_engine,
        session_factory=session_factory,
    )
    app = FastAPI()
    app.include_router(general_router)
    app.dependency_overrides[get_database_resources] = lambda: database

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
