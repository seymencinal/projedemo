"""Add identity and tenancy foundation.

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21 00:00:01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260721_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOOTSTRAP_ORGANIZATION_ID = "00000000-0000-0000-0000-000000000001"
BOOTSTRAP_ORGANIZATION_SLUG = "legacy-bootstrap"


def upgrade() -> None:
    membership_role = postgresql.ENUM(
        "owner",
        "admin",
        "member",
        "viewer",
        name="membership_role",
        create_type=False,
    )
    membership_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", membership_role, nullable=False),
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
            ondelete="CASCADE",
            name=op.f("fk_memberships_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name=op.f("fk_memberships_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint(
            "organization_id", "user_id", name=op.f("uq_memberships_organization_id")
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id=BOOTSTRAP_ORGANIZATION_ID,
            name="Legacy Bootstrap Organization",
            slug=BOOTSTRAP_ORGANIZATION_SLUG,
        )
    )
    op.add_column("companies", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE companies SET organization_id = :id WHERE organization_id IS NULL"
        ).bindparams(
            id=BOOTSTRAP_ORGANIZATION_ID,
        )
    )
    op.alter_column("companies", "organization_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_companies_organization_id_organizations"),
        "companies",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_companies_exchange", "companies", type_="unique")
    op.create_unique_constraint(
        op.f("uq_companies_organization_id"),
        "companies",
        ["organization_id", "exchange", "ticker"],
    )
    op.create_index(
        op.f("ix_companies_organization_id"), "companies", ["organization_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_companies_organization_id"), table_name="companies")
    op.drop_constraint(op.f("uq_companies_organization_id"), "companies", type_="unique")
    op.create_unique_constraint("uq_companies_exchange", "companies", ["exchange", "ticker"])
    op.drop_constraint(
        op.f("fk_companies_organization_id_organizations"), "companies", type_="foreignkey"
    )
    op.drop_column("companies", "organization_id")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
    sa.Enum(name="membership_role").drop(op.get_bind(), checkfirst=True)
