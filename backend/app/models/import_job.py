from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ImportJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "datasource_id",
            "idempotency_key",
            name="uq_import_jobs_organization_id_datasource_id_idempotency_key",
        ),
        ForeignKeyConstraint(
            ["datasource_id", "organization_id", "research_id"],
            ["datasources.id", "datasources.organization_id", "datasources.research_id"],
            ondelete="CASCADE",
            name="fk_import_jobs_datasource_id_organization_id_research_id_datasources",
        ),
        CheckConstraint("total_items >= 0", name="total_items_non_negative"),
        CheckConstraint("processed_items >= 0", name="processed_items_non_negative"),
        CheckConstraint("failed_items >= 0", name="failed_items_non_negative"),
        CheckConstraint(
            "processed_items + failed_items <= total_items", name="item_counts_within_total"
        ),
        Index("ix_import_jobs_datasource_id", "datasource_id"),
        Index("ix_import_jobs_organization_id", "organization_id"),
        Index("ix_import_jobs_research_id", "research_id"),
        Index("ix_import_jobs_status", "status"),
        Index("ix_import_jobs_organization_id_datasource_id", "organization_id", "datasource_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "organizations.id",
            name="fk_import_jobs_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    research_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "researches.id",
            name="fk_import_jobs_research_id_researches",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    datasource_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(
            ImportJobStatus,
            name="import_job_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=ImportJobStatus.PENDING,
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
