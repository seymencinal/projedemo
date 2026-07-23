from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.import_job import ImportJobStatus


class CsvImportMappingRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    mapping: dict[str, str] = Field(min_length=1, max_length=6)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Idempotency key cannot be blank.")
        return normalized_value


class CsvImportMappingAcceptedRead(BaseModel):
    import_job_id: UUID
    status: ImportJobStatus
    uploaded_file_id: UUID
    datasource_id: UUID
    accepted_mapping: dict[str, str]
