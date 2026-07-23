from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BIGINT,
    CHAR,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ImportedRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "imported_records"
    __table_args__ = (
        UniqueConstraint("import_job_id", "source_row_number", name="uq_imported_records_job_row"),
        CheckConstraint("source_row_number > 0", name="source_row_number_positive"),
        CheckConstraint("char_length(trim(content)) > 0", name="content_not_blank"),
        CheckConstraint(
            "engagement_count IS NULL OR engagement_count >= 0",
            name="engagement_non_negative",
        ),
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('positive', 'negative', 'neutral')",
            name="sentiment_valid",
        ),
        Index("ix_imported_records_import_job_id", "import_job_id"),
        Index("ix_imported_records_organization_datasource", "organization_id", "datasource_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(nullable=False)
    research_id: Mapped[UUID] = mapped_column(nullable=False)
    datasource_id: Mapped[UUID] = mapped_column(nullable=False)
    import_job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "import_jobs.id",
            name="fk_imported_records_import_job_id_import_jobs",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_row_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    content: Mapped[str] = mapped_column(String(20000), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    engagement_count: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
