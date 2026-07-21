from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)
from app.models.company import Company
from app.repositories.company import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyUpdate


class CompanyService:
    def __init__(
        self,
        session: AsyncSession,
        repository: CompanyRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or CompanyRepository(session)

    async def get_by_id(self, company_id: UUID) -> Company:
        company = await self._repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)
        return company

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Company]:
        return await self._repository.list(
            offset=offset,
            limit=limit,
        )

    async def create(self, payload: CompanyCreate) -> Company:
        existing_company = await self._repository.get_by_exchange_and_ticker(
            payload.exchange,
            payload.ticker,
        )
        if existing_company is not None:
            raise CompanyAlreadyExistsError(
                exchange=payload.exchange,
                ticker=payload.ticker,
            )

        company = Company(
            **payload.model_dump(),
        )
        company = await self._repository.add(company)
        await self._session.commit()
        await self._session.refresh(company)
        return company

    async def update(
        self,
        company_id: UUID,
        payload: CompanyUpdate,
    ) -> Company:
        company = await self._repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)

        values = payload.model_dump(exclude_unset=True)
        if not values:
            return company

        if "exchange" in values or "ticker" in values:
            exchange_value = values.get("exchange", company.exchange)
            ticker_value = values.get("ticker", company.ticker)
            exchange = exchange_value if isinstance(exchange_value, str) else company.exchange
            ticker = ticker_value if isinstance(ticker_value, str) else company.ticker
            existing_company = await self._repository.get_by_exchange_and_ticker(
                exchange=exchange,
                ticker=ticker,
            )
            if existing_company is not None and existing_company.id != company.id:
                raise CompanyAlreadyExistsError(
                    exchange=exchange,
                    ticker=ticker,
                )

        company = await self._repository.update(company, values)
        await self._session.commit()
        await self._session.refresh(company)
        return company

    async def delete(
        self,
        company_id: UUID,
    ) -> None:
        company = await self._repository.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError(company_id)

        await self._repository.delete(company)
        await self._session.commit()
