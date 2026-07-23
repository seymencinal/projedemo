from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase

from app.db.base import NAMING_CONVENTION, Base, metadata
from app.models.company import Company
from app.models.datasource import Datasource
from app.models.import_job import ImportJob
from app.models.imported_record import ImportedRecord
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.research import Research
from app.models.uploaded_file import UploadedFile
from app.models.user import User


def test_base_is_declarative_base() -> None:
    assert issubclass(Base, DeclarativeBase)
    assert Base.metadata is metadata
    assert isinstance(metadata, MetaData)


def test_metadata_uses_expected_naming_convention() -> None:
    assert metadata.naming_convention == NAMING_CONVENTION
    assert NAMING_CONVENTION == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def test_naming_convention_generates_constraint_names() -> None:
    test_metadata = MetaData(naming_convention=NAMING_CONVENTION)
    Table(
        "parent",
        test_metadata,
        Column("id", Integer, primary_key=True),
    )
    child_table = Table(
        "child",
        test_metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("parent.id")),
        Column("code", String(50), nullable=False, unique=True, index=True),
        Column("quantity", Integer, nullable=False),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        UniqueConstraint("parent_id", "code"),
    )

    assert child_table.primary_key.name == "pk_child"

    foreign_key_constraint = next(iter(child_table.foreign_key_constraints))
    assert foreign_key_constraint.name == "fk_child_parent_id_parent"

    check_constraint = next(
        constraint
        for constraint in child_table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert check_constraint.name == "ck_child_quantity_non_negative"

    unique_constraint = next(
        constraint
        for constraint in child_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["parent_id", "code"]
    )
    assert unique_constraint.name == "uq_child_parent_id"

    index = next(
        index
        for index in child_table.indexes
        if [column.name for column in index.columns] == ["code"]
    )
    assert index.name == "ix_child_code"


def test_base_metadata_contains_expected_application_tables() -> None:
    assert set(Base.metadata.tables) == {
        "companies",
        "datasources",
        "import_jobs",
        "imported_records",
        "memberships",
        "organizations",
        "researches",
        "uploaded_files",
        "users",
    }
    assert Base.metadata.tables["companies"] is Company.__table__
    assert Base.metadata.tables["organizations"] is Organization.__table__
    assert Base.metadata.tables["users"] is User.__table__
    assert Base.metadata.tables["memberships"] is Membership.__table__
    assert Base.metadata.tables["researches"] is Research.__table__
    assert Base.metadata.tables["datasources"] is Datasource.__table__
    assert Base.metadata.tables["import_jobs"] is ImportJob.__table__
    assert Base.metadata.tables["imported_records"] is ImportedRecord.__table__
    assert Base.metadata.tables["uploaded_files"] is UploadedFile.__table__
