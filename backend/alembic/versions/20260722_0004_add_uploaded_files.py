"""Add uploaded file foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0004"
down_revision: str | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "pending", "ready", "failed", "deleted", name="uploaded_file_status", create_type=False
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_unique_constraint(
        "uq_datasources_id_organization_id", "datasources", ["id", "organization_id"]
    )
    op.create_table(
        "uploaded_files",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("datasource_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            name="fk_uploaded_files_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["datasource_id", "organization_id"],
            ["datasources.id", "datasources.organization_id"],
            name="fk_uploaded_files_datasource_scope",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_uploaded_files_size_bytes_positive"),
        sa.UniqueConstraint(
            "organization_id",
            "datasource_id",
            "checksum_sha256",
            name="uq_uploaded_files_datasource_checksum",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_files_organization_id", "uploaded_files", ["organization_id"])
    op.create_index("ix_uploaded_files_datasource_id", "uploaded_files", ["datasource_id"])


def downgrade() -> None:
    op.drop_index("ix_uploaded_files_datasource_id", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_organization_id", table_name="uploaded_files")
    op.drop_table("uploaded_files")
    op.drop_constraint("uq_datasources_id_organization_id", "datasources", type_="unique")
    postgresql.ENUM(name="uploaded_file_status").drop(op.get_bind(), checkfirst=True)
