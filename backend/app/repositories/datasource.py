from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import Datasource


class DatasourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, datasource_id: UUID, organization_id: UUID) -> Datasource | None:
        result = await self._session.execute(
            select(Datasource).where(
                Datasource.id == datasource_id, Datasource.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list(self, research_id: UUID, organization_id: UUID) -> list[Datasource]:
        result = await self._session.execute(
            select(Datasource)
            .where(
                Datasource.research_id == research_id, Datasource.organization_id == organization_id
            )
            .order_by(Datasource.name)
        )
        return list(result.scalars().all())

    async def add(self, item: Datasource) -> Datasource:
        self._session.add(item)
        await self._session.flush()
        return item

    async def delete(self, item: Datasource) -> None:
        await self._session.delete(item)
        await self._session.flush()
