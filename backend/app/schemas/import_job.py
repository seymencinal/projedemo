from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.import_job import ImportJobStatus


class ImportJobCreate(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    total_items: int = Field(default=0, ge=0)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Idempotency key cannot be blank.")
        return normalized_value


class ImportJobRead(BaseModel):
    id: UUID
    organization_id: UUID
    research_id: UUID
    datasource_id: UUID
    status: ImportJobStatus
    total_items: int
    processed_items: int
    failed_items: int
    error_message: str | None
    idempotency_key: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ImportJobTransition(BaseModel):
    status: ImportJobStatus
    processed_items: int | None = Field(default=None, ge=0)
    failed_items: int | None = Field(default=None, ge=0)
    error_message: str | None = None

    @field_validator("error_message")
    @classmethod
    def normalize_error_message(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_completed(self) -> "ImportJobTransition":
        if self.status is ImportJobStatus.COMPLETED and self.error_message is not None:
            raise ValueError("Completed import jobs cannot have an error message.")
        if self.status is ImportJobStatus.FAILED and not self.error_message:
            raise ValueError("Failed import jobs require an error message.")
        return self
