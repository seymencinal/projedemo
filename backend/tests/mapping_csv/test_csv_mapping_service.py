from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.csv_mapping import (
    BlankSourceColumnError,
    DuplicateSourceColumnError,
    MissingRequiredCanonicalFieldError,
    UnknownCanonicalFieldError,
)
from app.exceptions.research import DatasourceNotFoundError, IdempotencyConflictError
from app.exceptions.uploaded_file import UploadedFileNotFoundError
from app.models.import_job import ImportJob, ImportJobStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.import_job import ImportJobRepository
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.csv_mapping import CsvImportMappingRequest
from app.services.mapping_preparation import MappingPreparationService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
UPLOADED_FILE_ID = UUID("00000000-0000-0000-0000-000000000040")
RESEARCH_ID = UUID("00000000-0000-0000-0000-000000000030")


def create_service() -> tuple[
    MappingPreparationService, MagicMock, MagicMock, MagicMock, MagicMock
]:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    import_jobs = MagicMock(spec=ImportJobRepository)
    datasources = MagicMock(spec=DatasourceRepository)
    uploaded_files = MagicMock(spec=UploadedFileRepository)
    return (
        MappingPreparationService(session, import_jobs, datasources, uploaded_files),
        session,
        import_jobs,
        datasources,
        uploaded_files,
    )


def payload(mapping: dict[str, str] | None = None) -> CsvImportMappingRequest:
    return CsvImportMappingRequest(
        idempotency_key=" mapping-key ",
        mapping=mapping or {"content": " body ", "author": "author"},
    )


@pytest.mark.asyncio
async def test_prepare_creates_pending_job_with_normalized_mapping_and_scoped_file() -> None:
    service, session, import_jobs, datasources, uploaded_files = create_service()
    datasources.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))
    uploaded_files.get = AsyncMock(return_value=SimpleNamespace(datasource_id=DATASOURCE_ID))
    import_jobs.get_by_key = AsyncMock(return_value=None)

    def add_job(job: ImportJob) -> ImportJob:
        job.id = uuid4()
        return job

    import_jobs.add = AsyncMock(side_effect=add_job)

    response = await service.prepare(DATASOURCE_ID, UPLOADED_FILE_ID, ORGANIZATION_ID, payload())

    created_job = import_jobs.add.await_args.args[0]
    assert isinstance(created_job, ImportJob)
    assert created_job.status is ImportJobStatus.PENDING
    assert created_job.organization_id == ORGANIZATION_ID
    assert created_job.research_id == RESEARCH_ID
    assert created_job.datasource_id == DATASOURCE_ID
    assert created_job.uploaded_file_id == UPLOADED_FILE_ID
    assert created_job.configuration == {"mapping": {"content": "body", "author": "author"}}
    assert created_job.idempotency_key == "mapping-key"
    assert created_job.total_items == created_job.processed_items == created_job.failed_items == 0
    assert response.status is ImportJobStatus.PENDING
    assert response.accepted_mapping == {"content": "body", "author": "author"}
    import_jobs.get_by_key.assert_awaited_once_with(ORGANIZATION_ID, DATASOURCE_ID, "mapping-key")
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(created_job)


@pytest.mark.asyncio
async def test_prepare_scopes_datasource_and_uploaded_file_without_cross_tenant_access() -> None:
    service, _, import_jobs, datasources, uploaded_files = create_service()
    datasources.get = AsyncMock(return_value=None)

    with pytest.raises(DatasourceNotFoundError):
        await service.prepare(DATASOURCE_ID, UPLOADED_FILE_ID, ORGANIZATION_ID, payload())

    datasources.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))
    uploaded_files.get = AsyncMock(return_value=None)
    with pytest.raises(UploadedFileNotFoundError):
        await service.prepare(DATASOURCE_ID, UPLOADED_FILE_ID, ORGANIZATION_ID, payload())

    uploaded_files.get = AsyncMock(return_value=SimpleNamespace(datasource_id=uuid4()))
    with pytest.raises(DatasourceNotFoundError):
        await service.prepare(DATASOURCE_ID, UPLOADED_FILE_ID, ORGANIZATION_ID, payload())

    import_jobs.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_reuses_datasource_scoped_idempotency_conflicts() -> None:
    service, _, import_jobs, datasources, uploaded_files = create_service()
    datasources.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))
    uploaded_files.get = AsyncMock(return_value=SimpleNamespace(datasource_id=DATASOURCE_ID))
    import_jobs.get_by_key = AsyncMock(return_value=MagicMock(spec=ImportJob))

    with pytest.raises(IdempotencyConflictError):
        await service.prepare(DATASOURCE_ID, UPLOADED_FILE_ID, ORGANIZATION_ID, payload())

    import_jobs.add.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mapping", "error_type"),
    [
        ({"content": "body", "unknown": "value"}, UnknownCanonicalFieldError),
        ({"author": "author"}, MissingRequiredCanonicalFieldError),
        ({"content": "   "}, BlankSourceColumnError),
        ({"content": "shared", "author": " shared "}, DuplicateSourceColumnError),
        ({"Content": "body"}, UnknownCanonicalFieldError),
    ],
)
async def test_prepare_enforces_exact_canonical_mapping_rules(
    mapping: dict[str, str], error_type: type[Exception]
) -> None:
    service, _, import_jobs, datasources, uploaded_files = create_service()
    datasources.get = AsyncMock(return_value=SimpleNamespace(research_id=RESEARCH_ID))
    uploaded_files.get = AsyncMock(return_value=SimpleNamespace(datasource_id=DATASOURCE_ID))

    with pytest.raises(error_type):
        await service.prepare(DATASOURCE_ID, UPLOADED_FILE_ID, ORGANIZATION_ID, payload(mapping))

    import_jobs.get_by_key.assert_not_awaited()
    import_jobs.add.assert_not_awaited()
