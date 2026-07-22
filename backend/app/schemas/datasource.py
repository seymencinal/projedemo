from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.datasource import DatasourceStatus, DatasourceType


class DatasourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: DatasourceType
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Name cannot be blank.")
        return normalized_value


class DatasourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: DatasourceStatus | None = None
    configuration: dict[str, Any] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Name cannot be blank.")
        return normalized_value


class DatasourceRead(BaseModel):
    id: UUID
    organization_id: UUID
    research_id: UUID
    name: str
    source_type: DatasourceType
    status: DatasourceStatus
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
