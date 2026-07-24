from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.import_job import ImportJobStatus
from app.schemas.import_job import ImportJobCreate, ImportJobRead, ImportJobTransition


def test_create_normalizes_key_and_validates_total_items() -> None:
    payload = ImportJobCreate(idempotency_key=" key ", total_items=2)

    assert payload.idempotency_key == "key"
    assert payload.total_items == 2
    for key in ("", "   "):
        with pytest.raises(ValidationError):
            ImportJobCreate(idempotency_key=key)
    with pytest.raises(ValidationError):
        ImportJobCreate(idempotency_key="key", total_items=-1)


@pytest.mark.parametrize(
    "status",
    [
        ImportJobStatus.PENDING,
        ImportJobStatus.RUNNING,
        ImportJobStatus.COMPLETED,
        ImportJobStatus.CANCELLED,
    ],
)
def test_transition_accepts_valid_statuses_without_error_message(status: ImportJobStatus) -> None:
    payload = ImportJobTransition(status=status, processed_items=0, failed_items=0)

    assert payload.status is status


def test_transition_validates_failed_and_completed_error_message_policies() -> None:
    failed = ImportJobTransition(status=ImportJobStatus.FAILED, error_message=" failed ")
    completed = ImportJobTransition(status=ImportJobStatus.COMPLETED)

    assert failed.error_message == "failed"
    assert completed.error_message is None
    for error_message in (None, "", "   "):
        with pytest.raises(ValidationError):
            ImportJobTransition(status=ImportJobStatus.FAILED, error_message=error_message)
    with pytest.raises(ValidationError):
        ImportJobTransition(status=ImportJobStatus.COMPLETED, error_message="unexpected")


def test_transition_rejects_invalid_status_and_negative_counters() -> None:
    with pytest.raises(ValidationError):
        ImportJobTransition(status="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ImportJobTransition(status=ImportJobStatus.RUNNING, processed_items=-1)
    with pytest.raises(ValidationError):
        ImportJobTransition(status=ImportJobStatus.RUNNING, failed_items=-1)


def test_transition_supports_partial_counter_payloads_and_non_failed_error_message() -> None:
    payload = ImportJobTransition(
        status=ImportJobStatus.RUNNING,
        processed_items=2,
        error_message=" informational ",
    )

    assert payload.processed_items == 2
    assert payload.failed_items is None
    assert payload.error_message == "informational"


def test_read_supports_orm_attributes_and_nullable_lifecycle_fields() -> None:
    job_id = uuid4()
    organization_id = uuid4()
    research_id = uuid4()
    datasource_id = uuid4()
    now = datetime(2026, 7, 22, tzinfo=UTC)
    pending = ImportJobRead.model_validate(
        SimpleNamespace(
            id=job_id,
            organization_id=organization_id,
            research_id=research_id,
            datasource_id=datasource_id,
            status=ImportJobStatus.PENDING,
            total_items=0,
            processed_items=0,
            failed_items=0,
            error_message=None,
            idempotency_key="key",
            started_at=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    terminal = pending.model_copy(
        update={
            "status": ImportJobStatus.COMPLETED,
            "started_at": now,
            "completed_at": now,
        }
    )

    assert pending.started_at is None and pending.completed_at is None
    assert pending.validation_issue_count == 0
    assert terminal.status is ImportJobStatus.COMPLETED
    assert terminal.model_dump(mode="json")["id"] == str(job_id)
    assert terminal.model_dump(mode="json")["created_at"].endswith("Z")


def test_read_serializes_validation_issue_count_and_rejects_negative_values() -> None:
    now = datetime(2026, 7, 22, tzinfo=UTC)
    job = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        research_id=uuid4(),
        datasource_id=uuid4(),
        status=ImportJobStatus.FAILED,
        total_items=0,
        processed_items=0,
        failed_items=0,
        error_message="failed",
        idempotency_key="key",
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )

    assert (
        ImportJobRead.model_validate(
            {**vars(job), "validation_issue_count": 3}
        ).validation_issue_count
        == 3
    )
    with pytest.raises(ValidationError):
        ImportJobRead.model_validate({**vars(job), "validation_issue_count": -1})
