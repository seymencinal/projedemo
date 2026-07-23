"""Add CSV mapping state to import jobs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260722_0005"
down_revision: str | None = "20260722_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("import_jobs", sa.Column("uploaded_file_id", sa.Uuid(), nullable=True))
    op.add_column(
        "import_jobs",
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_import_jobs_uploaded_file_id_uploaded_files",
        "import_jobs",
        "uploaded_files",
        ["uploaded_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_import_jobs_uploaded_file_id", "import_jobs", ["uploaded_file_id"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_uploaded_file_id", table_name="import_jobs")
    op.drop_constraint(
        "fk_import_jobs_uploaded_file_id_uploaded_files",
        "import_jobs",
        type_="foreignkey",
    )
    op.drop_column("import_jobs", "configuration")
    op.drop_column("import_jobs", "uploaded_file_id")
