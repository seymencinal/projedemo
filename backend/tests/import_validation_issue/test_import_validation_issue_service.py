from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import ImportJobNotFoundError
from app.models.import_job import ImportJobStatus
from app.repositories.import_job import ImportJobRepository
from app.repositories.import_validation_issue import ImportValidationIssueRepository
from app.services.import_validation_issue import ImportValidationIssueService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
IMPORT_JOB_ID = UUID("00000000-0000-0000-0000-000000000030")


def issue(source_row_number: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        source_row_number=source_row_number,
        issue_order=0,
        canonical_field="content",
        source_column="body",
        code="required",
        message="CSV import contains an invalid record.",
        created_at=datetime(2026, 7, 23, tzinfo=UTC),
    )


def create_service() -> tuple[ImportValidationIssueService, MagicMock, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    jobs = MagicMock(spec=ImportJobRepository)
    issues = MagicMock(spec=ImportValidationIssueRepository)
    jobs.get = AsyncMock()
    issues.list_for_import_job = AsyncMock()
    issues.count_for_import_job = AsyncMock()
    return ImportValidationIssueService(session, jobs, issues), jobs, issues


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(ImportJobStatus))
async def test_list_returns_page_for_any_import_job_status(status: ImportJobStatus) -> None:
    service, jobs, issues = create_service()
    jobs.get.return_value = SimpleNamespace(datasource_id=DATASOURCE_ID, status=status)
    issues.list_for_import_job.return_value = [issue()]
    issues.count_for_import_job.return_value = 1

    page = await service.list_for_import_job(
        ORGANIZATION_ID,
        DATASOURCE_ID,
        IMPORT_JOB_ID,
        offset=3,
        limit=10,
    )

    assert page.offset == 3 and page.limit == 10 and page.total == 1
    assert page.items[0].source_row_number == 2
    jobs.get.assert_awaited_once_with(IMPORT_JOB_ID, ORGANIZATION_ID)
    issues.list_for_import_job.assert_awaited_once_with(IMPORT_JOB_ID, offset=3, limit=10)
    issues.count_for_import_job.assert_awaited_once_with(IMPORT_JOB_ID)


@pytest.mark.asyncio
async def test_list_returns_empty_page() -> None:
    service, jobs, issues = create_service()
    jobs.get.return_value = SimpleNamespace(datasource_id=DATASOURCE_ID)
    issues.list_for_import_job.return_value = []
    issues.count_for_import_job.return_value = 0

    page = await service.list_for_import_job(
        ORGANIZATION_ID,
        DATASOURCE_ID,
        IMPORT_JOB_ID,
        offset=0,
        limit=100,
    )

    assert page.items == [] and page.total == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("job", [None, SimpleNamespace(datasource_id=uuid4())])
async def test_list_hides_missing_cross_tenant_and_datasource_mismatch_jobs(
    job: SimpleNamespace | None,
) -> None:
    service, jobs, issues = create_service()
    jobs.get.return_value = job

    with pytest.raises(ImportJobNotFoundError):
        await service.list_for_import_job(
            ORGANIZATION_ID,
            DATASOURCE_ID,
            IMPORT_JOB_ID,
            offset=0,
            limit=100,
        )

    issues.list_for_import_job.assert_not_awaited()
    issues.count_for_import_job.assert_not_awaited()
