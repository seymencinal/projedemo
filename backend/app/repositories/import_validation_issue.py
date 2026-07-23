from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_validation_issue import ImportValidationIssue
from app.services.import_row_validation import RowValidationIssue


class ImportValidationIssueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_many(
        self,
        import_job_id: UUID,
        issues: Sequence[RowValidationIssue],
    ) -> None:
        if not issues:
            return
        await self._session.execute(
            insert(ImportValidationIssue),
            [
                {
                    "import_job_id": import_job_id,
                    "source_row_number": issue.source_row_number,
                    "issue_order": issue_order,
                    "canonical_field": issue.canonical_field,
                    "source_column": issue.source_column,
                    "code": issue.code,
                    "message": issue.message,
                }
                for issue_order, issue in enumerate(issues)
            ],
        )
