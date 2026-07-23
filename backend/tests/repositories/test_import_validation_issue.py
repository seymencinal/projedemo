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
