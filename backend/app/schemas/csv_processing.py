from uuid import UUID

from pydantic import BaseModel, Field


class CsvSummaryRead(BaseModel):
    uploaded_file_id: UUID
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=1)
    column_names: list[str]
