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
