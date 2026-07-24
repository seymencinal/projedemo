from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import ImportJobNotFoundError
from app.repositories.import_job import ImportJobRepository
from app.repositories.imported_record import ImportedRecordRepository
from app.services.imported_record import ImportedRecordService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
IMPORT_JOB_ID = UUID("00000000-0000-0000-0000-000000000030")


def record(source_row_number: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        source_row_number=source_row_number,
        created_at=datetime(2026, 7, 24, tzinfo=UTC),
        import_job_id=IMPORT_JOB_ID,
        organization_id=ORGANIZATION_ID,
        datasource_id=DATASOURCE_ID,
        research_id=uuid4(),
        raw_row_hash="a" * 64,
        content="internal content",
    )


def create_service() -> tuple[ImportedRecordService, MagicMock, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    jobs = MagicMock(spec=ImportJobRepository)
    records = MagicMock(spec=ImportedRecordRepository)
    return ImportedRecordService(session, jobs, records), jobs, records


@pytest.mark.asyncio
async def test_list_for_import_job_returns_public_page_after_ownership_validation() -> None:
    service, jobs, records = create_service()
    jobs.get = AsyncMock(return_value=SimpleNamespace(datasource_id=DATASOURCE_ID))
    records.list_for_import_job = AsyncMock(return_value=[record(2), record(4)])
    records.count_for_import_job = AsyncMock(return_value=2)

    page = await service.list_for_import_job(
        ORGANIZATION_ID,
        DATASOURCE_ID,
        IMPORT_JOB_ID,
        offset=1,
        limit=2,
    )

    assert page.offset == 1 and page.limit == 2 and page.total == 2
    assert [item.source_row_number for item in page.items] == [2, 4]
    assert set(page.items[0].model_dump()) == {"id", "source_row_number", "created_at"}
    jobs.get.assert_awaited_once_with(IMPORT_JOB_ID, ORGANIZATION_ID)
    records.list_for_import_job.assert_awaited_once_with(IMPORT_JOB_ID, offset=1, limit=2)
    records.count_for_import_job.assert_awaited_once_with(IMPORT_JOB_ID)


@pytest.mark.asyncio
async def test_list_for_import_job_allows_empty_pages_without_status_filtering() -> None:
    service, jobs, records = create_service()
    jobs.get = AsyncMock(return_value=SimpleNamespace(datasource_id=DATASOURCE_ID, status="failed"))
    records.list_for_import_job = AsyncMock(return_value=[])
    records.count_for_import_job = AsyncMock(return_value=0)

    page = await service.list_for_import_job(
        ORGANIZATION_ID,
        DATASOURCE_ID,
        IMPORT_JOB_ID,
        offset=99,
        limit=100,
    )

    assert page.items == [] and page.total == 0
    records.list_for_import_job.assert_awaited_once_with(IMPORT_JOB_ID, offset=99, limit=100)


@pytest.mark.asyncio
@pytest.mark.parametrize("job", [None, SimpleNamespace(datasource_id=uuid4())])
async def test_list_for_import_job_hides_missing_cross_tenant_and_mismatched_jobs(
    job: SimpleNamespace | None,
) -> None:
    service, jobs, records = create_service()
    jobs.get = AsyncMock(return_value=job)

    with pytest.raises(ImportJobNotFoundError):
        await service.list_for_import_job(
            ORGANIZATION_ID,
            DATASOURCE_ID,
            IMPORT_JOB_ID,
            offset=0,
            limit=100,
        )

    records.list_for_import_job.assert_not_awaited()
    records.count_for_import_job.assert_not_awaited()
