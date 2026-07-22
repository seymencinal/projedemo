from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.uploaded_file import UploadedFileStatus


class UploadedFileCreate(BaseModel):
    original_filename: str = Field(min_length=1, max_length=255)
    stored_filename: str = Field(min_length=1, max_length=255)
    storage_path: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("original_filename", "stored_filename", "storage_path", "content_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value


class UploadedFileStatusUpdate(BaseModel):
    status: UploadedFileStatus
    error_message: str | None = None

    @field_validator("error_message")
    @classmethod
    def normalize_error_message(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_error_message(self) -> "UploadedFileStatusUpdate":
        if self.status is UploadedFileStatus.FAILED and not self.error_message:
            raise ValueError("Failed uploaded files require an error message.")
        if self.status is not UploadedFileStatus.FAILED and self.error_message is not None:
            raise ValueError("Only failed uploaded files can have an error message.")
        return self


class UploadedFileRead(BaseModel):
    id: UUID
    organization_id: UUID
    datasource_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    status: UploadedFileStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
