import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260723_0006_add_imported_records.py"
)


def load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("imported_records_migration", MIGRATION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load imported records migration module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_imported_records_table_and_indexes() -> None:
    module = load_migration_module()
    with (
        patch.object(module.op, "create_table") as create_table,
        patch.object(module.op, "create_index") as create_index,
    ):
        module.upgrade()
    assert module.revision == "20260723_0006"
    assert module.down_revision == "20260722_0005"
    assert create_table.call_args.args[0] == "imported_records"
    assert [call.args[0] for call in create_index.call_args_list] == [
        "ix_imported_records_import_job_id",
        "ix_imported_records_organization_datasource",
    ]


def test_downgrade_drops_indexes_before_table() -> None:
    module = load_migration_module()
    with (
        patch.object(module.op, "drop_index") as drop_index,
        patch.object(module.op, "drop_table") as drop_table,
    ):
        module.downgrade()
    assert [call.args[0] for call in drop_index.call_args_list] == [
        "ix_imported_records_organization_datasource",
        "ix_imported_records_import_job_id",
    ]
    drop_table.assert_called_once_with("imported_records")
