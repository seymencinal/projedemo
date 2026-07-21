from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    ticker: str = Field(
        min_length=1,
        max_length=32,
    )
    exchange: str = Field(
        min_length=1,
        max_length=32,
    )
    isin: str | None = Field(
        default=None,
        min_length=12,
        max_length=12,
    )
    website: str | None = Field(
        default=None,
        max_length=2048,
    )
    description: str | None = None
    is_active: bool = True


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    ticker: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
    )
    exchange: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
    )
    isin: str | None = Field(
        default=None,
        min_length=12,
        max_length=12,
    )
    website: str | None = Field(
        default=None,
        max_length=2048,
    )
    description: str | None = None
    is_active: bool | None = None


class CompanyRead(CompanyBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
