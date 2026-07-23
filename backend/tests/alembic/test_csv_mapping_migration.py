import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260722_0005_add_csv_mapping_import_jobs.py"
)


def load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("csv_mapping_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load CSV mapping migration module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_mapping_configuration_file_reference_and_index() -> None:
    module = load_migration_module()

    with (
        patch.object(module.op, "add_column") as add_column,
        patch.object(module.op, "create_foreign_key") as create_foreign_key,
        patch.object(module.op, "create_index") as create_index,
    ):
        module.upgrade()

    assert module.revision == "20260722_0005"
    assert module.down_revision == "20260722_0004"
    uploaded_file_column = add_column.call_args_list[0].args[1]
    configuration_column = add_column.call_args_list[1].args[1]
    assert uploaded_file_column.name == "uploaded_file_id"
    assert uploaded_file_column.nullable
    assert configuration_column.name == "configuration"
    assert not configuration_column.nullable
    assert isinstance(configuration_column.type, postgresql.JSONB)
    assert str(configuration_column.server_default.arg) == "'{}'::jsonb"
    assert create_foreign_key.call_args.args[:3] == (
        "fk_import_jobs_uploaded_file_id_uploaded_files",
        "import_jobs",
        "uploaded_files",
    )
    assert create_foreign_key.call_args.kwargs == {"ondelete": "SET NULL"}
    assert create_index.call_args.args == (
        "ix_import_jobs_uploaded_file_id",
        "import_jobs",
        ["uploaded_file_id"],
    )


def test_downgrade_removes_mapping_state_in_dependency_safe_order() -> None:
    module = load_migration_module()

    with (
        patch.object(module.op, "drop_index") as drop_index,
        patch.object(module.op, "drop_constraint") as drop_constraint,
        patch.object(module.op, "drop_column") as drop_column,
    ):
        module.downgrade()

    assert drop_index.call_args.args == ("ix_import_jobs_uploaded_file_id",)
    assert drop_index.call_args.kwargs == {"table_name": "import_jobs"}
    assert drop_constraint.call_args.args == (
        "fk_import_jobs_uploaded_file_id_uploaded_files",
        "import_jobs",
    )
    assert drop_constraint.call_args.kwargs == {"type_": "foreignkey"}
    assert [call.args for call in drop_column.call_args_list] == [
        ("import_jobs", "configuration"),
        ("import_jobs", "uploaded_file_id"),
    ]
