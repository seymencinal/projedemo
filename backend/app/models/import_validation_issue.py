from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin


class ImportValidationIssue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_validation_issues"
    __table_args__ = (
        UniqueConstraint(
            "import_job_id",
            "source_row_number",
            "issue_order",
            name="uq_import_validation_issues_job_row_order",
        ),
        CheckConstraint(
            "source_row_number > 0",
            name="source_row_number_positive",
        ),
        CheckConstraint("issue_order >= 0", name="issue_order_non_negative"),
        CheckConstraint(
            "char_length(trim(canonical_field)) > 0",
            name="canonical_field_not_blank",
        ),
        CheckConstraint("char_length(trim(code)) > 0", name="code_not_blank"),
        CheckConstraint("char_length(trim(message)) > 0", name="message_not_blank"),
        Index(
            "ix_import_validation_issues_import_job_order",
            "import_job_id",
            "source_row_number",
            "issue_order",
            "id",
        ),
    )

    import_job_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "import_jobs.id",
            name="fk_import_validation_issues_import_job_id_import_jobs",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_order: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_field: Mapped[str] = mapped_column(String(64), nullable=False)
    source_column: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
