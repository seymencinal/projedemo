from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DatasourceType(StrEnum):
    CSV = "csv"
    EXCEL = "excel"
    URL = "url"
    MANUAL = "manual"


class DatasourceStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DISABLED = "disabled"


class Datasource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasources"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            "research_id",
            name="uq_datasources_id_organization_id_research_id",
        ),
        Index("ix_datasources_organization_id", "organization_id"),
        Index("ix_datasources_research_id", "research_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    research_id: Mapped[UUID] = mapped_column(
        ForeignKey("researches.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[DatasourceType] = mapped_column(
        Enum(
            DatasourceType,
            name="datasource_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    status: Mapped[DatasourceStatus] = mapped_column(
        Enum(
            DatasourceStatus,
            name="datasource_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=DatasourceStatus.PENDING,
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
