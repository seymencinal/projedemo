from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.imported_record import ImportedRecordRepository
from app.schemas.imported_record import ImportedRecordInsert


@pytest.mark.asyncio
async def test_insert_batch_uses_core_execution_and_does_not_commit() -> None:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    repository = ImportedRecordRepository(session)
    record = ImportedRecordInsert(
        organization_id=uuid4(),
        research_id=uuid4(),
        datasource_id=uuid4(),
        import_job_id=uuid4(),
        source_row_number=1,
        raw_row_hash="a" * 64,
        content="content",
        published_at=None,
        author=None,
        engagement_count=None,
        sentiment=None,
        source_name=None,
    )

    await repository.insert_batch([record])
    await repository.insert_batch([])

    session.execute.assert_awaited_once()
    assert session.commit.call_count == 0


@pytest.mark.asyncio
async def test_list_and_count_for_import_job_use_ordered_paginated_queries_without_commit() -> None:
    session = MagicMock(spec=AsyncSession)
    items = [
        SimpleNamespace(id=uuid4(), source_row_number=2, created_at=datetime.now(UTC)),
        SimpleNamespace(id=uuid4(), source_row_number=4, created_at=datetime.now(UTC)),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    session.execute = AsyncMock(return_value=result)
    session.scalar = AsyncMock(return_value=3)
    repository = ImportedRecordRepository(session)
    import_job_id = uuid4()

    assert await repository.list_for_import_job(import_job_id, offset=1, limit=2) == items
    assert await repository.count_for_import_job(import_job_id) == 3

    list_statement = session.execute.await_args.args[0]
    count_statement = session.scalar.await_args.args[0]
    assert import_job_id in list_statement.compile().params.values()
    assert import_job_id in count_statement.compile().params.values()
    assert "ORDER BY imported_records.source_row_number ASC" in str(list_statement)
    assert "imported_records.id ASC" in str(list_statement)
    assert "LIMIT" in str(list_statement) and "OFFSET" in str(list_statement)
    assert session.commit.call_count == 0


@pytest.mark.asyncio
async def test_list_and_count_for_import_job_return_empty_results() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.scalar = AsyncMock(return_value=0)
    repository = ImportedRecordRepository(session)

    assert await repository.list_for_import_job(uuid4(), offset=99, limit=100) == []
    assert await repository.count_for_import_job(uuid4()) == 0
