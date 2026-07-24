from __future__ import annotations

from builtins import list as builtin_list
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import Label

from app.models.import_job import ImportJob
from app.models.import_validation_issue import ImportValidationIssue


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

    async def get_with_validation_issue_count(
        self,
        job_id: UUID,
        organization_id: UUID,
    ) -> tuple[ImportJob, int] | None:
        result = await self._session.execute(
            select(ImportJob, self._validation_issue_count()).where(
                ImportJob.id == job_id, ImportJob.organization_id == organization_id
            )
        )
        item = result.one_or_none()
        return None if item is None else (item[0], int(item[1]))

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

    async def list_with_validation_issue_count(
        self,
        datasource_id: UUID,
        organization_id: UUID,
    ) -> builtin_list[tuple[ImportJob, int]]:
        result = await self._session.execute(
            select(ImportJob, self._validation_issue_count())
            .where(
                ImportJob.datasource_id == datasource_id,
                ImportJob.organization_id == organization_id,
            )
            .order_by(ImportJob.created_at.desc())
        )
        return [(item[0], int(item[1])) for item in result.all()]

    async def add(self, item: ImportJob) -> ImportJob:
        self._session.add(item)
        await self._session.flush()
        return item

    @staticmethod
    def _validation_issue_count() -> Label[int]:
        return (
            select(func.count(ImportValidationIssue.id))
            .where(ImportValidationIssue.import_job_id == ImportJob.id)
            .correlate(ImportJob)
            .scalar_subquery()
            .label("validation_issue_count")
        )
