from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, company_id: UUID, organization_id: UUID) -> Company | None:
        statement = self._get_by_id_statement(company_id, organization_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_exchange_and_ticker(
        self,
        organization_id: UUID,
        exchange: str,
        ticker: str,
    ) -> Company | None:
        statement = self._get_by_exchange_and_ticker_statement(organization_id, exchange, ticker)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list(
        self,
        organization_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Company]:
        statement = (
            select(Company)
            .where(Company.organization_id == organization_id)
            .order_by(Company.name.asc(), Company.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def add(self, company: Company) -> Company:
        self._session.add(company)
        await self._session.flush()
        return company

    async def update(
        self,
        company: Company,
        values: dict[str, object],
    ) -> Company:
        for field, value in values.items():
            setattr(company, field, value)

        await self._session.flush()
        return company

    async def delete(
        self,
        company: Company,
    ) -> None:
        await self._session.delete(company)
        await self._session.flush()

    def _get_by_id_statement(
        self,
        company_id: UUID,
        organization_id: UUID,
    ) -> Select[tuple[Company]]:
        return select(Company).where(
            Company.id == company_id,
            Company.organization_id == organization_id,
        )

    def _get_by_exchange_and_ticker_statement(
        self,
        organization_id: UUID,
        exchange: str,
        ticker: str,
    ) -> Select[tuple[Company]]:
        return select(Company).where(
            Company.organization_id == organization_id,
            Company.exchange == exchange,
            Company.ticker == ticker,
        )
