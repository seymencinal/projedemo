from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research import Research


class ResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, research_id: UUID, organization_id: UUID) -> Research | None:
        result = await self._session.execute(
            select(Research).where(
                Research.id == research_id, Research.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list(self, organization_id: UUID) -> list[Research]:
        result = await self._session.execute(
            select(Research)
            .where(Research.organization_id == organization_id)
            .order_by(Research.name)
        )
        return list(result.scalars().all())

    async def add(self, item: Research) -> Research:
        self._session.add(item)
        await self._session.flush()
        return item

    async def delete(self, item: Research) -> None:
        await self._session.delete(item)
        await self._session.flush()
