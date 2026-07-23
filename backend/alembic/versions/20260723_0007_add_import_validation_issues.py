"""Add import validation issues."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0007"
down_revision: str | None = "20260723_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_validation_issues",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("issue_order", sa.Integer(), nullable=False),
        sa.Column("canonical_field", sa.String(64), nullable=False),
        sa.Column("source_column", sa.Text(), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("message", sa.String(255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name="fk_import_validation_issues_import_job_id_import_jobs",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "source_row_number > 0",
            name="ck_import_validation_issues_source_row_number_positive",
        ),
        sa.CheckConstraint(
            "issue_order >= 0",
            name="ck_import_validation_issues_issue_order_non_negative",
        ),
        sa.CheckConstraint(
            "char_length(trim(canonical_field)) > 0",
            name="ck_import_validation_issues_canonical_field_not_blank",
        ),
        sa.CheckConstraint(
            "char_length(trim(code)) > 0", name="ck_import_validation_issues_code_not_blank"
        ),
        sa.CheckConstraint(
            "char_length(trim(message)) > 0",
            name="ck_import_validation_issues_message_not_blank",
        ),
        sa.UniqueConstraint(
            "import_job_id",
            "source_row_number",
            "issue_order",
            name="uq_import_validation_issues_job_row_order",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_validation_issues_import_job_order",
        "import_validation_issues",
        ["import_job_id", "source_row_number", "issue_order", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_validation_issues_import_job_order", table_name="import_validation_issues"
    )
    op.drop_table("import_validation_issues")
