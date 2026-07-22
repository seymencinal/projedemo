from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import ResearchNotFoundError
from app.models.research import Research
from app.repositories.research import ResearchRepository
from app.schemas.research import ResearchCreate, ResearchUpdate


class ResearchService:
    def __init__(self, session: AsyncSession, repository: ResearchRepository | None = None) -> None:
        self._session = session
        self._repository = repository or ResearchRepository(session)

    async def get(self, item_id: UUID, organization_id: UUID) -> Research:
        item = await self._repository.get(item_id, organization_id)
        if item is None:
            raise ResearchNotFoundError(item_id)
        return item

    async def list(self, organization_id: UUID) -> list[Research]:
        return await self._repository.list(organization_id)

    async def create(self, organization_id: UUID, payload: ResearchCreate) -> Research:
        item = await self._repository.add(
            Research(organization_id=organization_id, **payload.model_dump())
        )
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def update(
        self, item_id: UUID, organization_id: UUID, payload: ResearchUpdate
    ) -> Research:
        item = await self.get(item_id, organization_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def delete(self, item_id: UUID, organization_id: UUID) -> None:
        await self._repository.delete(await self.get(item_id, organization_id))
        await self._session.commit()
