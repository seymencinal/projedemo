from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_job import ImportJob, ImportJobStatus
from app.repositories.import_job import ImportJobRepository

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
RESEARCH_ID = UUID("00000000-0000-0000-0000-000000000030")


def create_job() -> ImportJob:
    return ImportJob(
        organization_id=ORGANIZATION_ID,
        datasource_id=DATASOURCE_ID,
        research_id=RESEARCH_ID,
        status=ImportJobStatus.PENDING,
        total_items=0,
        processed_items=0,
        failed_items=0,
        idempotency_key="key",
    )


def test_repository_stores_session() -> None:
    session = MagicMock(spec=AsyncSession)

    assert ImportJobRepository(session)._session is session


@pytest.mark.asyncio
async def test_get_scopes_query_by_job_and_organization_and_returns_job() -> None:
    job = create_job()
    result = MagicMock()
    result.scalar_one_or_none.return_value = job
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await ImportJobRepository(session).get(uuid4(), ORGANIZATION_ID)

    assert returned is job
    assert ORGANIZATION_ID in session.execute.await_args.args[0].compile().params.values()
    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_returns_none_for_cross_tenant_or_missing_job() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    assert await ImportJobRepository(session).get(uuid4(), uuid4()) is None


@pytest.mark.asyncio
async def test_get_by_key_scopes_duplicate_detection_to_organization_and_datasource() -> None:
    job = create_job()
    result = MagicMock()
    result.scalar_one_or_none.return_value = job
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    returned = await ImportJobRepository(session).get_by_key(ORGANIZATION_ID, DATASOURCE_ID, "key")

    assert returned is job
    values = session.execute.await_args.args[0].compile().params.values()
    assert {ORGANIZATION_ID, DATASOURCE_ID, "key"} <= set(values)


@pytest.mark.asyncio
async def test_get_by_key_returns_none_when_key_is_reused_on_another_datasource() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    assert await ImportJobRepository(session).get_by_key(ORGANIZATION_ID, uuid4(), "key") is None


@pytest.mark.asyncio
async def test_list_filters_by_datasource_and_organization_and_handles_empty_result() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    assert await ImportJobRepository(session).list(DATASOURCE_ID, ORGANIZATION_ID) == []
    values = session.execute.await_args.args[0].compile().params.values()
    assert {ORGANIZATION_ID, DATASOURCE_ID} <= set(values)
    result.scalars.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_returns_persisted_jobs_in_repository_order() -> None:
    jobs = [create_job(), create_job()]
    result = MagicMock()
    result.scalars.return_value.all.return_value = jobs
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)

    assert await ImportJobRepository(session).list(DATASOURCE_ID, ORGANIZATION_ID) == jobs


@pytest.mark.asyncio
async def test_add_persists_flushes_and_returns_job() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    repository = ImportJobRepository(session)
    job = create_job()

    assert await repository.add(job) is job
    session.add.assert_called_once_with(job)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_called()
