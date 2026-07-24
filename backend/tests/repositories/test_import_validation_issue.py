from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.import_validation_issue import ImportValidationIssueRepository
from app.services.import_row_validation import RowValidationIssue


@pytest.mark.asyncio
async def test_insert_many_uses_ordered_core_payload_without_commit() -> None:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    repository = ImportValidationIssueRepository(session)
    job_id = uuid4()
    issues = (
        RowValidationIssue(7, "content", "body", "required", "safe"),
        RowValidationIssue(7, "sentiment", None, "invalid_sentiment", "safe"),
    )

    await repository.insert_many(job_id, issues)
    await repository.insert_many(job_id, ())

    session.execute.assert_awaited_once()
    payload = session.execute.await_args.args[1]
    assert payload == [
        {
            "import_job_id": job_id,
            "source_row_number": 7,
            "issue_order": 0,
            "canonical_field": "content",
            "source_column": "body",
            "code": "required",
            "message": "safe",
        },
        {
            "import_job_id": job_id,
            "source_row_number": 7,
            "issue_order": 1,
            "canonical_field": "sentiment",
            "source_column": None,
            "code": "invalid_sentiment",
            "message": "safe",
        },
    ]
    assert session.commit.call_count == 0


@pytest.mark.asyncio
async def test_list_and_count_for_import_job_use_scoped_ordered_queries_without_commit() -> None:
    session = MagicMock(spec=AsyncSession)
    issues = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
    result = MagicMock()
    result.scalars.return_value.all.return_value = issues
    session.execute = AsyncMock(return_value=result)
    session.scalar = AsyncMock(return_value=3)
    repository = ImportValidationIssueRepository(session)
    job_id = uuid4()

    listed = await repository.list_for_import_job(job_id, offset=2, limit=1)
    total = await repository.count_for_import_job(job_id)

    assert listed == issues
    assert total == 3
    list_statement = session.execute.await_args.args[0]
    count_statement = session.scalar.await_args.args[0]
    assert job_id in list_statement.compile().params.values()
    assert job_id in count_statement.compile().params.values()
    assert "ORDER BY import_validation_issues.source_row_number ASC" in str(list_statement)
    assert "import_validation_issues.issue_order ASC" in str(list_statement)
    assert "import_validation_issues.id ASC" in str(list_statement)
    assert "LIMIT" in str(list_statement) and "OFFSET" in str(list_statement)
    assert session.commit.call_count == 0


@pytest.mark.asyncio
async def test_list_for_import_job_returns_empty_page_for_unmatched_job() -> None:
    session = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.scalar = AsyncMock(return_value=0)
    repository = ImportValidationIssueRepository(session)
    job_id = uuid4()

    assert await repository.list_for_import_job(job_id, offset=99, limit=100) == []
    assert await repository.count_for_import_job(job_id) == 0
