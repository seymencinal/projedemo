from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import Datasource, DatasourceType
from app.models.import_job import ImportJob
from app.models.import_validation_issue import ImportValidationIssue
from app.models.organization import Organization
from app.models.research import Research
from app.repositories.import_validation_issue import ImportValidationIssueRepository
from app.services.import_row_validation import RowValidationIssue

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


@pytest.mark.asyncio
async def test_insert_many_persists_order_nullable_source_and_rolls_back(
    integration_session: AsyncSession,
) -> None:
    job = await make_import_job(integration_session)
    repository = ImportValidationIssueRepository(integration_session)

    await repository.insert_many(
        job.id,
        (
            RowValidationIssue(7, "content", "body", "required", "safe"),
            RowValidationIssue(7, "sentiment", None, "invalid_sentiment", "safe"),
        ),
    )
    persisted = list(
        await integration_session.scalars(
            select(ImportValidationIssue).order_by(ImportValidationIssue.issue_order)
        )
    )

    assert [(item.issue_order, item.source_column) for item in persisted] == [
        (0, "body"),
        (1, None),
    ]
    await integration_session.rollback()
    assert await integration_session.scalar(select(ImportValidationIssue)) is None


@pytest.mark.asyncio
async def test_import_validation_issue_database_constraints_and_job_cascade(
    integration_session: AsyncSession,
) -> None:
    job = await make_import_job(integration_session)
    issue = ImportValidationIssue(
        import_job_id=job.id,
        source_row_number=1,
        issue_order=0,
        canonical_field="content",
        source_column="body",
        code="required",
        message="safe",
    )
    integration_session.add(issue)
    await integration_session.flush()

    async with integration_session.begin_nested():
        integration_session.add(
            ImportValidationIssue(
                import_job_id=job.id,
                source_row_number=1,
                issue_order=0,
                canonical_field="content",
                source_column="body",
                code="required",
                message="safe",
            )
        )
        with pytest.raises(IntegrityError):
            await integration_session.flush()

    for source_row_number, issue_order, import_job_id in (
        (0, 1, job.id),
        (1, -1, job.id),
        (1, 1, uuid4()),
    ):
        async with integration_session.begin_nested():
            integration_session.add(
                ImportValidationIssue(
                    import_job_id=import_job_id,
                    source_row_number=source_row_number,
                    issue_order=issue_order,
                    canonical_field="content",
                    source_column="body",
                    code="required",
                    message="safe",
                )
            )
            with pytest.raises(IntegrityError):
                await integration_session.flush()

    await integration_session.delete(job)
    await integration_session.flush()
    assert await integration_session.scalar(select(ImportValidationIssue)) is None


@pytest.mark.asyncio
async def test_list_and_count_for_import_job_are_scoped_ordered_and_paginated(
    integration_session: AsyncSession,
) -> None:
    target_job = await make_import_job(integration_session)
    other_job = await make_import_job(integration_session)
    repository = ImportValidationIssueRepository(integration_session)
    await repository.insert_many(
        target_job.id,
        (
            RowValidationIssue(10, "content", "body", "required", "safe"),
            RowValidationIssue(2, "content", "body", "required", "safe"),
            RowValidationIssue(2, "sentiment", None, "invalid_sentiment", "safe"),
        ),
    )
    await repository.insert_many(
        other_job.id,
        (RowValidationIssue(1, "content", "body", "required", "safe"),),
    )

    items = await repository.list_for_import_job(target_job.id, offset=0, limit=2)

    assert [(item.source_row_number, item.issue_order) for item in items] == [(2, 1), (2, 2)]
    assert await repository.count_for_import_job(target_job.id) == 3
    assert await repository.list_for_import_job(target_job.id, offset=3, limit=100) == []
