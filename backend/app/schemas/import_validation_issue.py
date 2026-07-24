from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImportValidationIssueRead(BaseModel):
    id: UUID
    source_row_number: int
    issue_order: int
    canonical_field: str
    source_column: str | None
    code: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportValidationIssuePage(BaseModel):
    items: list[ImportValidationIssueRead]
    offset: int
    limit: int
    total: int
