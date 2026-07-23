"""Add imported records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0006"
down_revision: str | None = "20260722_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imported_records",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("research_id", sa.Uuid(), nullable=False),
        sa.Column("datasource_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("raw_row_hash", sa.CHAR(64), nullable=False),
        sa.Column("content", sa.String(20000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("engagement_count", sa.BIGINT(), nullable=True),
        sa.Column("sentiment", sa.String(16), nullable=True),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name="fk_imported_records_import_job_id_import_jobs",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "source_row_number > 0", name="ck_imported_records_source_row_number_positive"
        ),
        sa.CheckConstraint(
            "char_length(trim(content)) > 0", name="ck_imported_records_content_not_blank"
        ),
        sa.CheckConstraint(
            "engagement_count IS NULL OR engagement_count >= 0",
            name="ck_imported_records_engagement_non_negative",
        ),
        sa.CheckConstraint(
            "sentiment IS NULL OR sentiment IN ('positive', 'negative', 'neutral')",
            name="ck_imported_records_sentiment_valid",
        ),
        sa.UniqueConstraint(
            "import_job_id", "source_row_number", name="uq_imported_records_job_row"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imported_records_import_job_id", "imported_records", ["import_job_id"])
    op.create_index(
        "ix_imported_records_organization_datasource",
        "imported_records",
        ["organization_id", "datasource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_imported_records_organization_datasource", table_name="imported_records")
    op.drop_index("ix_imported_records_import_job_id", table_name="imported_records")
    op.drop_table("imported_records")
