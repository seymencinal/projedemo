import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260723_0007_add_import_validation_issues.py"
)


def load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "import_validation_issues_migration", MIGRATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load import validation issues migration module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_import_validation_issues_contract() -> None:
    module = load_migration_module()
    with (
        patch.object(module.op, "create_table") as create_table,
        patch.object(module.op, "create_index") as create_index,
    ):
        module.upgrade()

    assert module.revision == "20260723_0007"
    assert module.down_revision == "20260723_0006"
    assert create_table.call_args.args[0] == "import_validation_issues"
    assert create_index.call_args.args[0] == "ix_import_validation_issues_import_job_order"


def test_downgrade_drops_index_before_import_validation_issues_table() -> None:
    module = load_migration_module()
    with (
        patch.object(module.op, "drop_index") as drop_index,
        patch.object(module.op, "drop_table") as drop_table,
    ):
        module.downgrade()

    drop_index.assert_called_once_with(
        "ix_import_validation_issues_import_job_order",
        table_name="import_validation_issues",
    )
    drop_table.assert_called_once_with("import_validation_issues")
