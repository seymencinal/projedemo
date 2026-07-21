"""Create companies table.

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_companies"),
        ),
        sa.UniqueConstraint(
            "exchange",
            "ticker",
            name=op.f("uq_companies_exchange"),
        ),
        sa.UniqueConstraint(
            "isin",
            name=op.f("uq_companies_isin"),
        ),
    )

    op.create_index(
        op.f("ix_companies_name"),
        "companies",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_companies_name"),
        table_name="companies",
    )
    op.drop_table("companies")
