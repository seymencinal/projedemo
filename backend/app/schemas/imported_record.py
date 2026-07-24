from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True, slots=True)
class ImportedRecordInsert:
    organization_id: UUID
    research_id: UUID
    datasource_id: UUID
    import_job_id: UUID
    source_row_number: int
    raw_row_hash: str
    content: str
    published_at: datetime | None
    author: str | None
    engagement_count: int | None
    sentiment: str | None
    source_name: str | None


class ImportedRecordRead(BaseModel):
    id: UUID
    source_row_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportedRecordPage(BaseModel):
    items: list[ImportedRecordRead]
    offset: int
    limit: int
    total: int
