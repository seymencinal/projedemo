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


class UploadedFileStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class UploadedFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "datasource_id",
            "checksum_sha256",
            name="uq_uploaded_files_datasource_checksum",
        ),
        ForeignKeyConstraint(
            ["datasource_id", "organization_id"],
            ["datasources.id", "datasources.organization_id"],
            name="fk_uploaded_files_datasource_scope",
            ondelete="CASCADE",
        ),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        Index("ix_uploaded_files_organization_id", "organization_id"),
        Index("ix_uploaded_files_datasource_id", "datasource_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "organizations.id",
            name="fk_uploaded_files_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    datasource_id: Mapped[UUID] = mapped_column(nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[UploadedFileStatus] = mapped_column(
        Enum(
            UploadedFileStatus,
            name="uploaded_file_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=UploadedFileStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
