import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, call, patch

import sqlalchemy as sa
from alembic.config import Config

from app.core.config import get_settings
from app.db.session import build_database_url
from app.models.company import Company

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260721_0001_create_companies_table.py"
)


def load_migration_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "company_migration",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load company migration module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_config_uses_expected_script_location() -> None:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(config_path)
    database_url = config.get_main_option("sqlalchemy.url")

    assert config.get_main_option("script_location") == "alembic"
    assert config.get_main_option("prepend_sys_path") == "."
    assert database_url
    assert "postgresql" in database_url


def test_database_url_can_be_built_from_application_settings() -> None:
    database_url = build_database_url(get_settings())
    database_url_value = str(database_url)

    assert database_url_value
    assert "postgresql" in database_url_value
    assert database_url.drivername == "postgresql+psycopg"


def test_company_migration_revision_metadata() -> None:
    module = load_migration_module()
    namespace = vars(module)

    assert namespace["revision"] == "20260721_0001"
    assert namespace["down_revision"] is None
    assert namespace["branch_labels"] is None
    assert namespace["depends_on"] is None


def test_upgrade_creates_companies_table() -> None:
    module = load_migration_module()
    namespace = vars(module)
    migration_op = namespace["op"]
    upgrade = namespace["upgrade"]

    with (
        patch.object(migration_op, "f", side_effect=lambda name: name),
        patch.object(migration_op, "create_table") as create_table,
        patch.object(migration_op, "create_index"),
    ):
        upgrade()

    assert create_table.call_count == 1
    assert create_table.call_args.args[0] == "companies"

    columns = [item for item in create_table.call_args.args[1:] if isinstance(item, sa.Column)]
    columns_by_name = {column.name: column for column in columns}

    assert [column.name for column in columns] == [
        "name",
        "ticker",
        "exchange",
        "isin",
        "website",
        "description",
        "is_active",
        "id",
        "created_at",
        "updated_at",
    ]
    assert isinstance(columns_by_name["name"].type, sa.String)
    assert columns_by_name["name"].type.length == 255
    assert columns_by_name["name"].nullable is False
    assert isinstance(columns_by_name["ticker"].type, sa.String)
    assert columns_by_name["ticker"].type.length == 32
    assert columns_by_name["ticker"].nullable is False
    assert isinstance(columns_by_name["exchange"].type, sa.String)
    assert columns_by_name["exchange"].type.length == 32
    assert columns_by_name["exchange"].nullable is False
    assert isinstance(columns_by_name["isin"].type, sa.String)
    assert columns_by_name["isin"].type.length == 12
    assert columns_by_name["isin"].nullable is True
    assert isinstance(columns_by_name["website"].type, sa.String)
    assert columns_by_name["website"].type.length == 2048
    assert columns_by_name["website"].nullable is True
    assert isinstance(columns_by_name["description"].type, sa.Text)
    assert columns_by_name["description"].nullable is True
    assert isinstance(columns_by_name["is_active"].type, sa.Boolean)
    assert columns_by_name["is_active"].nullable is False
    assert columns_by_name["is_active"].server_default is not None
    assert isinstance(columns_by_name["id"].type, sa.Uuid)
    assert columns_by_name["id"].nullable is False
    assert isinstance(columns_by_name["created_at"].type, sa.DateTime)
    assert columns_by_name["created_at"].type.timezone is True
    assert columns_by_name["created_at"].nullable is False
    assert columns_by_name["created_at"].server_default is not None
    assert isinstance(columns_by_name["updated_at"].type, sa.DateTime)
    assert columns_by_name["updated_at"].type.timezone is True
    assert columns_by_name["updated_at"].nullable is False
    assert columns_by_name["updated_at"].server_default is not None


def test_upgrade_creates_expected_constraints() -> None:
    module = load_migration_module()
    namespace = vars(module)
    migration_op = namespace["op"]
    upgrade = namespace["upgrade"]

    with (
        patch.object(migration_op, "f", side_effect=lambda name: name),
        patch.object(migration_op, "create_table") as create_table,
        patch.object(migration_op, "create_index"),
    ):
        upgrade()

    table = sa.Table(
        "companies",
        sa.MetaData(),
        *create_table.call_args.args[1:],
    )
    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, (sa.PrimaryKeyConstraint, sa.UniqueConstraint))
    ]
    primary_key = next(
        constraint for constraint in constraints if isinstance(constraint, sa.PrimaryKeyConstraint)
    )
    unique_constraints = [
        constraint for constraint in constraints if isinstance(constraint, sa.UniqueConstraint)
    ]

    assert [column.name for column in primary_key.columns] == ["id"]
    assert primary_key.name == "pk_companies"
    assert {
        tuple(column.name for column in constraint.columns) for constraint in unique_constraints
    } == {("exchange", "ticker"), ("isin",)}
    assert {constraint.name for constraint in unique_constraints} == {
        "uq_companies_exchange",
        "uq_companies_isin",
    }


def test_upgrade_creates_name_index() -> None:
    module = load_migration_module()
    namespace = vars(module)
    migration_op = namespace["op"]
    upgrade = namespace["upgrade"]

    with (
        patch.object(migration_op, "f", side_effect=lambda name: name),
        patch.object(migration_op, "create_table"),
        patch.object(migration_op, "create_index") as create_index,
    ):
        upgrade()

    create_index.assert_called_once_with(
        "ix_companies_name",
        "companies",
        ["name"],
        unique=False,
    )


def test_downgrade_drops_index_before_table() -> None:
    module = load_migration_module()
    namespace = vars(module)
    migration_op = namespace["op"]
    downgrade = namespace["downgrade"]
    operations = MagicMock()

    with (
        patch.object(migration_op, "f", side_effect=lambda name: name),
        patch.object(migration_op, "drop_index", side_effect=operations.drop_index),
        patch.object(migration_op, "drop_table", side_effect=operations.drop_table),
    ):
        downgrade()

    assert operations.mock_calls == [
        call.drop_index(
            "ix_companies_name",
            table_name="companies",
        ),
        call.drop_table("companies"),
    ]


def test_migration_columns_match_company_metadata() -> None:
    module = load_migration_module()
    namespace = vars(module)
    migration_op = namespace["op"]
    upgrade = namespace["upgrade"]

    with (
        patch.object(migration_op, "f", side_effect=lambda name: name),
        patch.object(migration_op, "create_table") as create_table,
        patch.object(migration_op, "create_index"),
    ):
        upgrade()

    migration_columns = [
        item for item in create_table.call_args.args[1:] if isinstance(item, sa.Column)
    ]

    model_columns = [
        column for column in Company.__table__.columns if column.name != "organization_id"
    ]

    assert [column.name for column in migration_columns] == [
        column.name for column in model_columns
    ]
    for migration_column, model_column in zip(
        migration_columns,
        model_columns,
        strict=True,
    ):
        assert migration_column.nullable is model_column.nullable
        assert type(migration_column.type) is type(model_column.type)
        if isinstance(migration_column.type, sa.String) and isinstance(
            model_column.type,
            sa.String,
        ):
            assert migration_column.type.length == model_column.type.length
        if isinstance(migration_column.type, sa.DateTime) and isinstance(
            model_column.type,
            sa.DateTime,
        ):
            assert migration_column.type.timezone is model_column.type.timezone
