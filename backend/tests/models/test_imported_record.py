from typing import cast

from sqlalchemy import CHAR, CheckConstraint, ForeignKeyConstraint, String, Table, UniqueConstraint

from app.models.imported_record import ImportedRecord


def test_imported_record_has_expected_scope_and_persistence_constraints() -> None:
    table = cast(Table, ImportedRecord.__table__)
    constraints = list(table.constraints)
    assert ImportedRecord.__tablename__ == "imported_records"
    assert any(
        isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["import_job_id", "source_row_number"]
        for constraint in constraints
    )
    assert any(isinstance(constraint, CheckConstraint) for constraint in constraints)
    assert any(isinstance(constraint, ForeignKeyConstraint) for constraint in constraints)
    assert cast(String, table.columns["content"].type).length == 20000
    assert cast(CHAR, table.columns["raw_row_hash"].type).length == 64
