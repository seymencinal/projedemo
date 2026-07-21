from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, organization_id: UUID) -> Organization | None:
        result = await self._session.execute(
            select(Organization).where(Organization.id == organization_id),
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._session.execute(
            select(Organization).where(Organization.slug == slug),
        )
        return result.scalar_one_or_none()

    async def list(self) -> list[Organization]:
        result = await self._session.execute(select(Organization).order_by(Organization.name.asc()))
        return list(result.scalars().all())

    async def add(self, organization: Organization) -> Organization:
        self._session.add(organization)
        await self._session.flush()
        return organization
