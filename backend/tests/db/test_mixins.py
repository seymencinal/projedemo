from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped

from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TestBase(DeclarativeBase):
    __test__ = False


def create_test_model() -> type[TestBase]:
    class TestModel(UUIDPrimaryKeyMixin, TimestampMixin, TestBase):
        __tablename__ = "test_mixin_model"

    return TestModel


TestModel = create_test_model()


def test_mixins_define_expected_columns() -> None:
    assert set(TestModel.__table__.columns.keys()) == {
        "id",
        "created_at",
        "updated_at",
    }


def test_uuid_primary_key_column_configuration() -> None:
    column = TestModel.__table__.columns["id"]

    assert isinstance(column.type, Uuid)
    assert column.primary_key is True
    assert column.nullable is False
    assert column.default is not None
    assert column.default.is_callable


def test_uuid_primary_key_python_annotation() -> None:
    assert TestModel.__annotations__.get("id") is None
    assert UUIDPrimaryKeyMixin.__annotations__["id"] == Mapped[UUID]


def test_timestamp_column_types() -> None:
    created_at = TestModel.__table__.columns["created_at"]
    updated_at = TestModel.__table__.columns["updated_at"]

    assert isinstance(created_at.type, DateTime)
    assert isinstance(updated_at.type, DateTime)
    assert created_at.type.timezone is True
    assert updated_at.type.timezone is True
    assert created_at.nullable is False
    assert updated_at.nullable is False


def test_timestamp_defaults() -> None:
    created_at = TestModel.__table__.columns["created_at"]
    updated_at = TestModel.__table__.columns["updated_at"]

    assert created_at.server_default is not None
    assert updated_at.server_default is not None
    assert updated_at.onupdate is not None
    assert created_at.onupdate is None


def test_timestamp_python_annotations() -> None:
    assert TimestampMixin.__annotations__["created_at"] == Mapped[datetime]
    assert TimestampMixin.__annotations__["updated_at"] == Mapped[datetime]
