from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob


class ImportJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_id: UUID, organization_id: UUID) -> ImportJob | None:
        result = await self._session.execute(
            select(ImportJob).where(
                ImportJob.id == job_id, ImportJob.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_execution(
        self, job_id: UUID, organization_id: UUID, datasource_id: UUID
    ) -> ImportJob | None:
        result = await self._session.execute(
            select(ImportJob)
            .where(
                ImportJob.id == job_id,
                ImportJob.organization_id == organization_id,
                ImportJob.datasource_id == datasource_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_key(
        self,
        organization_id: UUID,
        datasource_id: UUID,
        key: str,
    ) -> ImportJob | None:
        result = await self._session.execute(
            select(ImportJob).where(
                ImportJob.organization_id == organization_id,
                ImportJob.datasource_id == datasource_id,
                ImportJob.idempotency_key == key,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, datasource_id: UUID, organization_id: UUID) -> list[ImportJob]:
        result = await self._session.execute(
            select(ImportJob)
            .where(
                ImportJob.datasource_id == datasource_id,
                ImportJob.organization_id == organization_id,
            )
            .order_by(ImportJob.created_at.desc())
        )
        return list(result.scalars().all())

    async def add(self, item: ImportJob) -> ImportJob:
        self._session.add(item)
        await self._session.flush()
        return item
