from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
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
from app.services.import_job import ImportJobService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
RESEARCH_ID = UUID("00000000-0000-0000-0000-000000000030")


def create_job(status: ImportJobStatus = ImportJobStatus.PENDING) -> ImportJob:
    job = ImportJob(
        organization_id=ORGANIZATION_ID,
        datasource_id=DATASOURCE_ID,
        research_id=RESEARCH_ID,
        status=status,
        total_items=10,
        processed_items=0,
        failed_items=0,
        idempotency_key="key",
    )
    job.id = uuid4()
    return job


def create_service(
    repository: MagicMock | None = None,
    datasource_repository: MagicMock | None = None,
) -> tuple[ImportJobService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    job_repository = repository or MagicMock(spec=ImportJobRepository)
    source_repository = datasource_repository or MagicMock(spec=DatasourceRepository)
    return (
        ImportJobService(session, job_repository, source_repository),
        session,
        job_repository,
        source_repository,
    )


@pytest.mark.asyncio
async def test_get_and_list_are_tenant_scoped_and_raise_not_found() -> None:
    service, _, repository, source_repository = create_service()
    job = create_job()
    repository.get = AsyncMock(return_value=job)
    repository.list = AsyncMock(return_value=[job])
    source_repository.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))

    assert await service.get(job.id, ORGANIZATION_ID) is job
    assert await service.list(DATASOURCE_ID, ORGANIZATION_ID) == [job]
    repository.get.assert_awaited_once_with(job.id, ORGANIZATION_ID)
    repository.list.assert_awaited_once_with(DATASOURCE_ID, ORGANIZATION_ID)

    repository.get = AsyncMock(return_value=None)
    source_repository.get = AsyncMock(return_value=None)
    with pytest.raises(ImportJobNotFoundError):
        await service.get(uuid4(), ORGANIZATION_ID)
    with pytest.raises(DatasourceNotFoundError):
        await service.list(DATASOURCE_ID, ORGANIZATION_ID)


@pytest.mark.asyncio
async def test_summary_reads_return_validation_issue_counts_and_preserve_scope() -> None:
    service, _, repository, source_repository = create_service()
    successful = create_job(ImportJobStatus.COMPLETED)
    validation_failed = create_job(ImportJobStatus.FAILED)
    repository.get_with_validation_issue_count = AsyncMock(return_value=(validation_failed, 3))
    repository.list_with_validation_issue_count = AsyncMock(
        return_value=[(successful, 0), (validation_failed, 3)]
    )
    source_repository.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))

    assert await service.get_with_validation_issue_count(validation_failed.id, ORGANIZATION_ID) == (
        validation_failed,
        3,
    )
    assert await service.list_with_validation_issue_count(DATASOURCE_ID, ORGANIZATION_ID) == [
        (successful, 0),
        (validation_failed, 3),
    ]
    repository.get_with_validation_issue_count.assert_awaited_once_with(
        validation_failed.id, ORGANIZATION_ID
    )
    repository.list_with_validation_issue_count.assert_awaited_once_with(
        DATASOURCE_ID, ORGANIZATION_ID
    )


@pytest.mark.asyncio
async def test_summary_reads_preserve_existing_not_found_behavior() -> None:
    service, _, repository, source_repository = create_service()
    repository.get_with_validation_issue_count = AsyncMock(return_value=None)
    source_repository.get = AsyncMock(return_value=None)

    with pytest.raises(ImportJobNotFoundError):
        await service.get_with_validation_issue_count(uuid4(), ORGANIZATION_ID)
    with pytest.raises(DatasourceNotFoundError):
        await service.list_with_validation_issue_count(DATASOURCE_ID, ORGANIZATION_ID)


@pytest.mark.asyncio
async def test_create_derives_relationships_and_enforces_datasource_scoped_idempotency() -> None:
    service, session, repository, source_repository = create_service()
    source_repository.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))
    repository.get_by_key = AsyncMock(return_value=None)
    repository.add = AsyncMock(side_effect=lambda job: job)

    job = await service.create(
        DATASOURCE_ID, ORGANIZATION_ID, ImportJobCreate(idempotency_key=" key ", total_items=4)
    )

    assert job.status is ImportJobStatus.PENDING
    assert (job.organization_id, job.datasource_id, job.research_id) == (
        ORGANIZATION_ID,
        DATASOURCE_ID,
        RESEARCH_ID,
    )
    assert job.processed_items == job.failed_items == 0
    repository.get_by_key.assert_awaited_once_with(ORGANIZATION_ID, DATASOURCE_ID, "key")
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(job)

    source_repository.get = AsyncMock(return_value=None)
    with pytest.raises(DatasourceNotFoundError):
        await service.create(
            DATASOURCE_ID, ORGANIZATION_ID, ImportJobCreate(idempotency_key="other")
        )
    source_repository.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))
    repository.get_by_key = AsyncMock(return_value=create_job())
    with pytest.raises(IdempotencyConflictError):
        await service.create(DATASOURCE_ID, ORGANIZATION_ID, ImportJobCreate(idempotency_key="key"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ImportJobStatus.PENDING, ImportJobStatus.RUNNING),
        (ImportJobStatus.PENDING, ImportJobStatus.CANCELLED),
        (ImportJobStatus.RUNNING, ImportJobStatus.COMPLETED),
        (ImportJobStatus.RUNNING, ImportJobStatus.FAILED),
        (ImportJobStatus.RUNNING, ImportJobStatus.CANCELLED),
    ],
)
async def test_transition_allows_only_supported_lifecycle_paths(
    from_status: ImportJobStatus,
    to_status: ImportJobStatus,
) -> None:
    service, _, repository, _ = create_service()
    job = create_job(from_status)
    if from_status is ImportJobStatus.RUNNING:
        job.started_at = datetime(2026, 1, 1, tzinfo=UTC)
    repository.get = AsyncMock(return_value=job)
    payload = ImportJobTransition(
        status=to_status,
        processed_items=10 if to_status is ImportJobStatus.COMPLETED else None,
        error_message="failed" if to_status is ImportJobStatus.FAILED else None,
    )

    result = await service.transition(job.id, ORGANIZATION_ID, payload)

    assert result.status is to_status
    if to_status is ImportJobStatus.RUNNING:
        assert result.started_at is not None and result.completed_at is None
    elif to_status is ImportJobStatus.COMPLETED:
        assert result.completed_at is not None and result.error_message is None
    else:
        assert result.completed_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (ImportJobStatus.PENDING, ImportJobStatus.PENDING),
        (ImportJobStatus.PENDING, ImportJobStatus.COMPLETED),
        (ImportJobStatus.PENDING, ImportJobStatus.FAILED),
        (ImportJobStatus.RUNNING, ImportJobStatus.PENDING),
        (ImportJobStatus.COMPLETED, ImportJobStatus.RUNNING),
        (ImportJobStatus.FAILED, ImportJobStatus.RUNNING),
        (ImportJobStatus.CANCELLED, ImportJobStatus.RUNNING),
    ],
)
async def test_transition_rejects_forbidden_lifecycle_paths(
    from_status: ImportJobStatus,
    to_status: ImportJobStatus,
) -> None:
    service, _, repository, _ = create_service()
    job = create_job(from_status)
    repository.get = AsyncMock(return_value=job)

    with pytest.raises(InvalidImportJobTransitionError):
        await service.transition(
            job.id,
            ORGANIZATION_ID,
            ImportJobTransition(
                status=to_status,
                error_message="failed" if to_status is ImportJobStatus.FAILED else None,
            ),
        )


@pytest.mark.asyncio
async def test_transition_rejects_counter_regression_overflow_and_incomplete_completion() -> None:
    service, _, repository, _ = create_service()
    job = create_job(ImportJobStatus.RUNNING)
    job.processed_items = 3
    job.failed_items = 1
    repository.get = AsyncMock(return_value=job)

    for payload in (
        ImportJobTransition(status=ImportJobStatus.CANCELLED, processed_items=2),
        ImportJobTransition(status=ImportJobStatus.CANCELLED, failed_items=0),
        ImportJobTransition(status=ImportJobStatus.CANCELLED, processed_items=10, failed_items=1),
        ImportJobTransition(status=ImportJobStatus.COMPLETED, processed_items=5, failed_items=1),
    ):
        with pytest.raises(InvalidImportJobCountersError):
            await service.transition(job.id, ORGANIZATION_ID, payload)
