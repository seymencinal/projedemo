import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260721_0002_add_identity_and_tenancy.py"
)


def load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("identity_tenancy_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load identity and tenancy migration module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_tenancy_migration_metadata_and_bootstrap_constants() -> None:
    module = load_migration_module()

    assert module.revision == "20260721_0002"
    assert module.down_revision == "20260721_0001"
    bootstrap_organization_id = UUID("00000000-0000-0000-0000-000000000001")
    assert bootstrap_organization_id == module.BOOTSTRAP_ORGANIZATION_ID
    assert module.BOOTSTRAP_ORGANIZATION_SLUG == "legacy-bootstrap"


def test_upgrade_creates_identity_tables_and_backfills_existing_companies() -> None:
    module = load_migration_module()
    bind = MagicMock()

    with (
        patch.object(module.op, "get_bind", return_value=bind),
        patch.object(module.op, "f", side_effect=lambda name: name),
        patch.object(module.op, "create_table") as create_table,
        patch.object(module.op, "execute") as execute,
        patch.object(module.op, "add_column") as add_column,
        patch.object(module.op, "alter_column") as alter_column,
        patch.object(module.op, "create_foreign_key") as create_foreign_key,
        patch.object(module.op, "drop_constraint"),
        patch.object(module.op, "create_unique_constraint") as create_unique_constraint,
        patch.object(module.op, "create_index") as create_index,
        patch.object(postgresql.ENUM, "create"),
    ):
        module.upgrade()

    assert [call.args[0] for call in create_table.call_args_list] == [
        "organizations",
        "users",
        "memberships",
    ]
    assert add_column.call_args.args[0] == "companies"
    assert add_column.call_args.args[1].name == "organization_id"
    assert alter_column.call_args.args == ("companies", "organization_id")
    assert alter_column.call_args.kwargs == {"nullable": False}
    assert create_foreign_key.call_args.args[:3] == (
        "fk_companies_organization_id_organizations",
        "companies",
        "organizations",
    )
    assert create_unique_constraint.call_args.args[1] == "companies"
    assert create_index.call_args.args[:3] == (
        "ix_companies_organization_id",
        "companies",
        ["organization_id"],
    )
    statements = [str(call.args[0]) for call in execute.call_args_list]
    assert any("INSERT INTO organizations" in statement for statement in statements)
    assert any("UPDATE companies SET organization_id" in statement for statement in statements)
    id_parameters = [call.args[0]._bindparams["id"] for call in execute.call_args_list]
    assert all(parameter.value == module.BOOTSTRAP_ORGANIZATION_ID for parameter in id_parameters)
    assert all(
        isinstance(parameter.type, postgresql.UUID) and parameter.type.as_uuid
        for parameter in id_parameters
    )
    membership_role_column = next(
        column
        for column in create_table.call_args_list[2].args
        if isinstance(column, sa.Column) and column.name == "role"
    )
    assert isinstance(membership_role_column.type, postgresql.ENUM)
    assert membership_role_column.type.create_type is False
