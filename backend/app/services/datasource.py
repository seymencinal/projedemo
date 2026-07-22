from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import DatasourceNotFoundError, ResearchNotFoundError
from app.models.datasource import Datasource
from app.repositories.datasource import DatasourceRepository
from app.repositories.research import ResearchRepository
from app.schemas.datasource import DatasourceCreate, DatasourceUpdate


class DatasourceService:
    def __init__(
        self,
        session: AsyncSession,
        repository: DatasourceRepository | None = None,
        research_repository: ResearchRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or DatasourceRepository(session)
        self._research_repository = research_repository or ResearchRepository(session)

    async def get(self, item_id: UUID, organization_id: UUID) -> Datasource:
        item = await self._repository.get(item_id, organization_id)
        if item is None:
            raise DatasourceNotFoundError(item_id)
        return item

    async def list(self, research_id: UUID, organization_id: UUID) -> list[Datasource]:
        if await self._research_repository.get(research_id, organization_id) is None:
            raise ResearchNotFoundError(research_id)
        return await self._repository.list(research_id, organization_id)

    async def create(
        self, research_id: UUID, organization_id: UUID, payload: DatasourceCreate
    ) -> Datasource:
        if await self._research_repository.get(research_id, organization_id) is None:
            raise ResearchNotFoundError(research_id)
        item = await self._repository.add(
            Datasource(
                organization_id=organization_id, research_id=research_id, **payload.model_dump()
            )
        )
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def update(
        self, item_id: UUID, organization_id: UUID, payload: DatasourceUpdate
    ) -> Datasource:
        item = await self.get(item_id, organization_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def delete(self, item_id: UUID, organization_id: UUID) -> None:
        await self._repository.delete(await self.get(item_id, organization_id))
        await self._session.commit()
