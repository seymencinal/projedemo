"""Add research, datasource, and import job foundations."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0003"
down_revision: str | None = "20260721_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    research_status = postgresql.ENUM(
        "draft", "active", "archived", name="research_status", create_type=False
    )
    datasource_type = postgresql.ENUM(
        "csv", "excel", "url", "manual", name="datasource_type", create_type=False
    )
    datasource_status = postgresql.ENUM(
        "pending", "ready", "failed", "disabled", name="datasource_status", create_type=False
    )
    import_job_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="import_job_status",
        create_type=False,
    )
    for enum in (research_status, datasource_type, datasource_status, import_job_status):
        enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "researches",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", research_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_researches_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_researches_organization_id", "researches", ["organization_id"])
    op.create_table(
        "datasources",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("research_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", datasource_type, nullable=False),
        sa.Column("status", datasource_status, nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_datasources_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["research_id"],
            ["researches.id"],
            name="fk_datasources_research_id_researches",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "research_id",
            name="uq_datasources_id_organization_id_research_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_datasources_organization_id", "datasources", ["organization_id"])
    op.create_index("ix_datasources_research_id", "datasources", ["research_id"])
    op.create_table(
        "import_jobs",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("research_id", sa.Uuid(), nullable=False),
        sa.Column("datasource_id", sa.Uuid(), nullable=False),
        sa.Column("status", import_job_status, nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("processed_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_import_jobs_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["research_id"],
            ["researches.id"],
            name="fk_import_jobs_research_id_researches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["datasource_id", "organization_id", "research_id"],
            ["datasources.id", "datasources.organization_id", "datasources.research_id"],
            ondelete="CASCADE",
            name="fk_import_jobs_datasource_id_organization_id_research_id_datasources",
        ),
        sa.CheckConstraint("total_items >= 0", name="ck_import_jobs_total_items_non_negative"),
        sa.CheckConstraint(
            "processed_items >= 0", name="ck_import_jobs_processed_items_non_negative"
        ),
        sa.CheckConstraint("failed_items >= 0", name="ck_import_jobs_failed_items_non_negative"),
        sa.CheckConstraint(
            "processed_items + failed_items <= total_items",
            name="ck_import_jobs_item_counts_within_total",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "datasource_id",
            "idempotency_key",
            name="uq_import_jobs_organization_id_datasource_id_idempotency_key",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_datasource_id", "import_jobs", ["datasource_id"])
    op.create_index("ix_import_jobs_organization_id", "import_jobs", ["organization_id"])
    op.create_index("ix_import_jobs_research_id", "import_jobs", ["research_id"])
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index(
        "ix_import_jobs_organization_id_datasource_id",
        "import_jobs",
        ["organization_id", "datasource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_import_jobs_organization_id_datasource_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_index("ix_import_jobs_research_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_organization_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_datasource_id", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("ix_datasources_research_id", table_name="datasources")
    op.drop_index("ix_datasources_organization_id", table_name="datasources")
    op.drop_table("datasources")
    op.drop_index("ix_researches_organization_id", table_name="researches")
    op.drop_table("researches")
    for name in ("import_job_status", "datasource_status", "datasource_type", "research_status"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
