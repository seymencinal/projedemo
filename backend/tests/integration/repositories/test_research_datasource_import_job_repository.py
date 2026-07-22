from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import Datasource, DatasourceStatus, DatasourceType
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.organization import Organization
from app.models.research import Research, ResearchStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.import_job import ImportJobRepository
from app.repositories.research import ResearchRepository

pytestmark = pytest.mark.integration


async def make_organization(session: AsyncSession) -> Organization:
    organization = Organization(name="Organization", slug=f"organization-{uuid4().hex}")
    session.add(organization)
    await session.flush()
    return organization


async def make_research(session: AsyncSession, organization: Organization) -> Research:
    research = Research(
        organization_id=organization.id,
        name="Research",
        status=ResearchStatus.ACTIVE,
    )
    session.add(research)
    await session.flush()
    return research


async def make_datasource(
    session: AsyncSession, organization: Organization, research: Research
) -> Datasource:
    datasource = Datasource(
        organization_id=organization.id,
        research_id=research.id,
        name="Datasource",
        source_type=DatasourceType.CSV,
        status=DatasourceStatus.READY,
        configuration={"delimiter": ","},
    )
    session.add(datasource)
    await session.flush()
    return datasource


@pytest.mark.asyncio
async def test_research_persists_scopes_and_deletes(integration_session: AsyncSession) -> None:
    organization = await make_organization(integration_session)
    other = await make_organization(integration_session)
    repository = ResearchRepository(integration_session)
    research = await repository.add(
        Research(organization_id=organization.id, name="Alpha", status=ResearchStatus.ACTIVE)
    )
    await repository.add(Research(organization_id=other.id, name="Other"))
    research.description = "Updated"
    await integration_session.flush()

    persisted_research = await repository.get(research.id, organization.id)
    assert persisted_research is not None
    assert persisted_research.status is ResearchStatus.ACTIVE
    assert await repository.get(research.id, other.id) is None
    assert [item.name for item in await repository.list(organization.id)] == ["Alpha"]
    await repository.delete(research)
    assert await repository.get(research.id, organization.id) is None


@pytest.mark.asyncio
async def test_datasource_persists_json_enums_and_tenant_research_scope(
    integration_session: AsyncSession,
) -> None:
    organization = await make_organization(integration_session)
    other = await make_organization(integration_session)
    research = await make_research(integration_session, organization)
    datasource = await make_datasource(integration_session, organization, research)
    repository = DatasourceRepository(integration_session)

    persisted_datasource = await repository.get(datasource.id, organization.id)
    assert persisted_datasource is not None
    assert persisted_datasource.configuration == {"delimiter": ","}
    assert await repository.get(datasource.id, other.id) is None
    assert [item.id for item in await repository.list(research.id, organization.id)] == [
        datasource.id
    ]
    assert await repository.list(research.id, other.id) == []
    await repository.delete(datasource)
    assert await repository.get(datasource.id, organization.id) is None


@pytest.mark.asyncio
async def test_import_job_constraints_relationships_and_idempotency_scope(
    integration_session: AsyncSession,
) -> None:
    organization = await make_organization(integration_session)
    other = await make_organization(integration_session)
    research = await make_research(integration_session, organization)
    datasource = await make_datasource(integration_session, organization, research)
    second = await make_datasource(integration_session, organization, research)
    repository = ImportJobRepository(integration_session)
    job = await repository.add(
        ImportJob(
            organization_id=organization.id,
            research_id=research.id,
            datasource_id=datasource.id,
            status=ImportJobStatus.RUNNING,
            total_items=2,
            processed_items=1,
            failed_items=0,
            idempotency_key="same-key",
            started_at=datetime.now(UTC),
        )
    )
    await repository.add(
        ImportJob(
            organization_id=organization.id,
            research_id=research.id,
            datasource_id=second.id,
            status=ImportJobStatus.PENDING,
            total_items=0,
            processed_items=0,
            failed_items=0,
            idempotency_key="same-key",
        )
    )
    persisted_job = await repository.get(job.id, organization.id)
    assert persisted_job is not None
    assert persisted_job.status is ImportJobStatus.RUNNING
    assert await repository.get(job.id, other.id) is None
    assert [item.id for item in await repository.list(datasource.id, organization.id)] == [job.id]
    assert await repository.list(datasource.id, other.id) == []
    assert await repository.get_by_key(organization.id, datasource.id, "same-key") is not None

    async with integration_session.begin_nested():
        integration_session.add(
            ImportJob(
                organization_id=organization.id,
                research_id=research.id,
                datasource_id=datasource.id,
                status=ImportJobStatus.PENDING,
                total_items=0,
                processed_items=0,
                failed_items=0,
                idempotency_key="same-key",
            )
        )
        with pytest.raises(IntegrityError):
            await integration_session.flush()
    async with integration_session.begin_nested():
        integration_session.add(
            ImportJob(
                organization_id=other.id,
                research_id=research.id,
                datasource_id=datasource.id,
                status=ImportJobStatus.PENDING,
                total_items=-1,
                processed_items=0,
                failed_items=0,
                idempotency_key="invalid",
            )
        )
        with pytest.raises(IntegrityError):
            await integration_session.flush()


@pytest.mark.asyncio
async def test_migration_catalog_contains_research_datasource_import_job_contract(
    integration_session: AsyncSession,
) -> None:
    tables = await integration_session.scalars(
        text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('researches', 'datasources', 'import_jobs')"
        )
    )
    enums = await integration_session.scalars(
        text(
            "SELECT typname FROM pg_type WHERE typname IN ('research_status', 'datasource_type', 'datasource_status', 'import_job_status')"
        )
    )
    constraints = await integration_session.scalars(
        text(
            "SELECT conname FROM pg_constraint WHERE conname IN ('fk_import_jobs_datasource_id_organization_id_research_id_datasources', 'uq_import_jobs_organization_id_datasource_id_idempotency_key', 'uq_datasources_id_organization_id_research_id')"
        )
    )

    assert set(tables) == {"researches", "datasources", "import_jobs"}
    assert set(enums) == {
        "research_status",
        "datasource_type",
        "datasource_status",
        "import_job_status",
    }
    assert set(constraints) == {
        "fk_import_jobs_datasource_id_organization_id_research_id_datasources",
        "uq_import_jobs_organization_id_datasource_id_idempotency_key",
        "uq_datasources_id_organization_id_research_id",
    }
    assert (
        await integration_session.scalar(select(ImportJob).where(ImportJob.id == uuid4())) is None
    )
