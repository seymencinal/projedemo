from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, insert, select
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

    async def list_for_import_job(
        self,
        import_job_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> list[ImportValidationIssue]:
        result = await self._session.execute(
            select(ImportValidationIssue)
            .where(ImportValidationIssue.import_job_id == import_job_id)
            .order_by(
                ImportValidationIssue.source_row_number.asc(),
                ImportValidationIssue.issue_order.asc(),
                ImportValidationIssue.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_import_job(self, import_job_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(ImportValidationIssue)
            .where(ImportValidationIssue.import_job_id == import_job_id)
        )
        return int(count or 0)
