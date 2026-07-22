from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import (
    DatasourceNotFoundError,
    IdempotencyConflictError,
    ImportJobNotFoundError,
    InvalidImportJobCountersError,
    InvalidImportJobTransitionError,
)
from app.models.import_job import ImportJob, ImportJobStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.import_job import ImportJobRepository
from app.schemas.import_job import ImportJobCreate, ImportJobTransition


class ImportJobService:
    def __init__(
        self,
        session: AsyncSession,
        repository: ImportJobRepository | None = None,
        datasource_repository: DatasourceRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or ImportJobRepository(session)
        self._datasource_repository = datasource_repository or DatasourceRepository(session)

    async def get(self, item_id: UUID, organization_id: UUID) -> ImportJob:
        item = await self._repository.get(item_id, organization_id)
        if item is None:
            raise ImportJobNotFoundError(item_id)
        return item

    async def list(self, datasource_id: UUID, organization_id: UUID) -> list[ImportJob]:
        if await self._datasource_repository.get(datasource_id, organization_id) is None:
            raise DatasourceNotFoundError(datasource_id)
        return await self._repository.list(datasource_id, organization_id)

    async def create(
        self, datasource_id: UUID, organization_id: UUID, payload: ImportJobCreate
    ) -> ImportJob:
        datasource = await self._datasource_repository.get(datasource_id, organization_id)
        if datasource is None:
            raise DatasourceNotFoundError(datasource_id)
        if await self._repository.get_by_key(
            organization_id,
            datasource_id,
            payload.idempotency_key,
        ):
            raise IdempotencyConflictError(payload.idempotency_key)
        item = await self._repository.add(
            ImportJob(
                organization_id=organization_id,
                research_id=datasource.research_id,
                datasource_id=datasource_id,
                status=ImportJobStatus.PENDING,
                idempotency_key=payload.idempotency_key,
                total_items=payload.total_items,
                processed_items=0,
                failed_items=0,
            )
        )
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def transition(
        self, item_id: UUID, organization_id: UUID, payload: ImportJobTransition
    ) -> ImportJob:
        item = await self.get(item_id, organization_id)
        allowed_transitions = {
            ImportJobStatus.PENDING: {ImportJobStatus.RUNNING, ImportJobStatus.CANCELLED},
            ImportJobStatus.RUNNING: {
                ImportJobStatus.COMPLETED,
                ImportJobStatus.FAILED,
                ImportJobStatus.CANCELLED,
            },
        }
        if payload.status not in allowed_transitions.get(item.status, set()):
            raise InvalidImportJobTransitionError()
        processed_items = (
            payload.processed_items if payload.processed_items is not None else item.processed_items
        )
        failed_items = (
            payload.failed_items if payload.failed_items is not None else item.failed_items
        )
        if processed_items < item.processed_items or failed_items < item.failed_items:
            raise InvalidImportJobCountersError()
        if processed_items + failed_items > item.total_items:
            raise InvalidImportJobCountersError()
        if (
            payload.status is ImportJobStatus.COMPLETED
            and processed_items + failed_items != item.total_items
        ):
            raise InvalidImportJobCountersError()
        item.status = payload.status
        item.processed_items = processed_items
        item.failed_items = failed_items
        if item.status is ImportJobStatus.RUNNING:
            item.started_at = datetime.now(UTC)
            item.completed_at = None
        elif item.status is ImportJobStatus.COMPLETED:
            item.completed_at = datetime.now(UTC)
            item.error_message = None
        elif item.status is ImportJobStatus.FAILED:
            item.completed_at = datetime.now(UTC)
            item.error_message = payload.error_message
        else:
            item.completed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(item)
        return item
