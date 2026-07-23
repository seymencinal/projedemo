from typing import cast

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from app.models.import_validation_issue import ImportValidationIssue


def test_import_validation_issue_has_only_safe_persistence_fields() -> None:
    table = cast(Table, ImportValidationIssue.__table__)
    constraints = list(table.constraints)

    assert ImportValidationIssue.__tablename__ == "import_validation_issues"
    assert set(table.columns.keys()) == {
        "id",
        "import_job_id",
        "source_row_number",
        "issue_order",
        "canonical_field",
        "source_column",
        "code",
        "message",
        "created_at",
    }
    assert table.columns["source_column"].nullable
    assert not table.columns["import_job_id"].nullable
    assert cast(String, table.columns["canonical_field"].type).length == 64
    assert isinstance(table.columns["source_column"].type, Text)
    assert cast(String, table.columns["code"].type).length == 64
    assert cast(String, table.columns["message"].type).length == 255
    assert "updated_at" not in table.columns
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_import_validation_issues_import_job_id_import_jobs"
        and constraint.ondelete == "CASCADE"
        for constraint in constraints
    )
    assert any(isinstance(constraint, CheckConstraint) for constraint in constraints)
    assert any(
        isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns]
        == ["import_job_id", "source_row_number", "issue_order"]
        for constraint in constraints
    )
    assert any(
        isinstance(index, Index)
        and index.name == "ix_import_validation_issues_import_job_order"
        and [column.name for column in index.columns]
        == ["import_job_id", "source_row_number", "issue_order", "id"]
        for index in table.indexes
    )
    constraint_names = [
        str(constraint.name)
        for constraint in constraints
        if isinstance(constraint, (CheckConstraint, ForeignKeyConstraint, UniqueConstraint))
        and constraint.name is not None
    ]
    index_names = [str(index.name) for index in table.indexes if index.name is not None]
    assert all(len(name) <= 63 for name in [*constraint_names, *index_names])
