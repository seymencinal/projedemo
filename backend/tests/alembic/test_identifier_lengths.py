import ast
from pathlib import Path

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[2] / "alembic" / "versions"
NAMED_MIGRATION_OPERATIONS = {
    "create_check_constraint",
    "create_foreign_key",
    "create_index",
    "create_primary_key",
    "create_unique_constraint",
    "drop_constraint",
    "drop_index",
}


def _literal_string(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _migration_identifier_names(path: Path) -> list[str]:
    names: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in NAMED_MIGRATION_OPERATIONS
            and node.args
        ):
            name = _literal_string(node.args[0])
            if name is not None:
                names.append(name)
        for keyword in node.keywords:
            if keyword.arg == "name":
                name = _literal_string(keyword.value)
                if name is not None:
                    names.append(name)
    return names


def test_explicit_migration_identifier_names_fit_postgresql_limit() -> None:
    names = [
        name
        for path in MIGRATIONS_DIRECTORY.glob("*.py")
        for name in _migration_identifier_names(path)
    ]

    assert all(len(name) <= 63 for name in names)
