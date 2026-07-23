from collections.abc import Sequence

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.imported_record import ImportedRecord
from app.schemas.imported_record import ImportedRecordInsert


class ImportedRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_batch(self, records: Sequence[ImportedRecordInsert]) -> None:
        if not records:
            return
        await self._session.execute(
            insert(ImportedRecord),
            [
                {
                    "organization_id": record.organization_id,
                    "research_id": record.research_id,
                    "datasource_id": record.datasource_id,
                    "import_job_id": record.import_job_id,
                    "source_row_number": record.source_row_number,
                    "raw_row_hash": record.raw_row_hash,
                    "content": record.content,
                    "published_at": record.published_at,
                    "author": record.author,
                    "engagement_count": record.engagement_count,
                    "sentiment": record.sentiment,
                    "source_name": record.source_name,
                }
                for record in records
            ],
        )
