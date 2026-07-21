from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.organization import OrganizationAlreadyExistsError, OrganizationNotFoundError
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import OrganizationCreate


class OrganizationService:
    def __init__(
        self,
        session: AsyncSession,
        repository: OrganizationRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or OrganizationRepository(session)

    async def create(self, payload: OrganizationCreate) -> Organization:
        existing = await self._repository.get_by_slug(payload.slug)
        if existing is not None:
            raise OrganizationAlreadyExistsError(payload.slug)

        organization = await self._repository.add(Organization(**payload.model_dump()))
        await self._session.commit()
        await self._session.refresh(organization)
        return organization

    async def get_by_id(self, organization_id: UUID) -> Organization:
        organization = await self._repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError(organization_id)
        return organization

    async def list(self) -> list[Organization]:
        return await self._repository.list()
