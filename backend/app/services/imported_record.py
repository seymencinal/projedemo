from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import ImportJobNotFoundError
from app.repositories.import_job import ImportJobRepository
from app.repositories.imported_record import ImportedRecordRepository
from app.schemas.imported_record import ImportedRecordPage, ImportedRecordRead


class ImportedRecordService:
    def __init__(
        self,
        session: AsyncSession,
        import_job_repository: ImportJobRepository | None = None,
        imported_record_repository: ImportedRecordRepository | None = None,
    ) -> None:
        self._import_jobs = import_job_repository or ImportJobRepository(session)
        self._records = imported_record_repository or ImportedRecordRepository(session)

    async def list_for_import_job(
        self,
        organization_id: UUID,
        datasource_id: UUID,
        import_job_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> ImportedRecordPage:
        import_job = await self._import_jobs.get(import_job_id, organization_id)
        if import_job is None or import_job.datasource_id != datasource_id:
            raise ImportJobNotFoundError(import_job_id)

        items = await self._records.list_for_import_job(
            import_job_id,
            offset=offset,
            limit=limit,
        )
        total = await self._records.count_for_import_job(import_job_id)
        return ImportedRecordPage(
            items=[ImportedRecordRead.model_validate(item) for item in items],
            offset=offset,
            limit=limit,
            total=total,
        )
