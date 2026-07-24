from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import Datasource, DatasourceType
from app.models.import_job import ImportJob
from app.models.imported_record import ImportedRecord
from app.models.organization import Organization
from app.models.research import Research
from app.repositories.imported_record import ImportedRecordRepository

pytestmark = pytest.mark.integration


async def make_import_job(session: AsyncSession) -> ImportJob:
    organization = Organization(name="Organization", slug=f"organization-{uuid4().hex}")
    session.add(organization)
    await session.flush()
    research = Research(organization_id=organization.id, name="Research")
    session.add(research)
    await session.flush()
    datasource = Datasource(
        organization_id=organization.id,
        research_id=research.id,
        name="Datasource",
        source_type=DatasourceType.CSV,
    )
    session.add(datasource)
    await session.flush()
    job = ImportJob(
        organization_id=organization.id,
        research_id=research.id,
        datasource_id=datasource.id,
        idempotency_key=f"key-{uuid4().hex}",
    )
    session.add(job)
    await session.flush()
    return job


def record(job: ImportJob, source_row_number: int) -> ImportedRecord:
    return ImportedRecord(
        organization_id=job.organization_id,
        research_id=job.research_id,
        datasource_id=job.datasource_id,
        import_job_id=job.id,
        source_row_number=source_row_number,
        raw_row_hash=f"{source_row_number:064x}",
        content=f"content {source_row_number}",
        published_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_list_and_count_for_import_job_are_scoped_ordered_and_paginated(
    integration_session: AsyncSession,
) -> None:
    target_job = await make_import_job(integration_session)
    other_job = await make_import_job(integration_session)
    integration_session.add_all(
        [
            record(target_job, 4),
            record(target_job, 2),
            record(target_job, 8),
            record(other_job, 1),
        ]
    )
    await integration_session.flush()
    repository = ImportedRecordRepository(integration_session)

    items = await repository.list_for_import_job(target_job.id, offset=1, limit=1)

    assert [item.source_row_number for item in items] == [4]
    assert await repository.count_for_import_job(target_job.id) == 3
    assert await repository.list_for_import_job(target_job.id, offset=3, limit=100) == []
    assert await repository.count_for_import_job(other_job.id) == 1
