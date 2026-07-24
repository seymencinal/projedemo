from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_import_job_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router
from app.exceptions.research import (
    DatasourceNotFoundError,
    IdempotencyConflictError,
    ImportJobNotFoundError,
    InvalidImportJobCountersError,
    InvalidImportJobTransitionError,
)
from app.models.import_job import ImportJobStatus
from app.services.import_job import ImportJobService

ORGANIZATION_ID = uuid4()
OTHER_ORGANIZATION_ID = uuid4()
DATASOURCE_ID = uuid4()
IMPORT_JOB_ID = uuid4()


def import_job(
    status: ImportJobStatus = ImportJobStatus.PENDING,
    *,
    total_items: int = 2,
    processed_items: int = 0,
    failed_items: int = 0,
    error_message: str | None = None,
) -> SimpleNamespace:
    now = datetime(2026, 7, 22, tzinfo=UTC)
    return SimpleNamespace(
        id=IMPORT_JOB_ID,
        organization_id=ORGANIZATION_ID,
        research_id=uuid4(),
        datasource_id=DATASOURCE_ID,
        status=status,
        total_items=total_items,
        processed_items=processed_items,
        failed_items=failed_items,
        error_message=error_message,
        idempotency_key="key",
        started_at=now if status is not ImportJobStatus.PENDING else None,
        completed_at=(
            now
            if status
            in {ImportJobStatus.COMPLETED, ImportJobStatus.FAILED, ImportJobStatus.CANCELLED}
            else None
        ),
        created_at=now,
        updated_at=now,
    )


def client_with_service() -> tuple[TestClient, MagicMock]:
    service = MagicMock(spec=ImportJobService)
    service.create = AsyncMock(return_value=import_job())
    service.list_with_validation_issue_count = AsyncMock(return_value=[(import_job(), 0)])
    service.get_with_validation_issue_count = AsyncMock(return_value=(import_job(), 0))
    service.transition = AsyncMock(return_value=import_job(ImportJobStatus.RUNNING))
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_import_job_service] = lambda: service
    return TestClient(app), service


def headers(organization_id: UUID = ORGANIZATION_ID) -> dict[str, str]:
    return {"X-Organization-ID": str(organization_id)}


def test_import_job_create_list_get_and_response_serialization() -> None:
    client, service = client_with_service()
    validation_failed = import_job(ImportJobStatus.FAILED, error_message="failed")
    service.get_with_validation_issue_count.return_value = (validation_failed, 3)

    created = client.post(
        f"/datasources/{DATASOURCE_ID}/import-jobs",
        headers=headers(),
        json={"idempotency_key": " key ", "total_items": 2},
    )
    listed = client.get(f"/datasources/{DATASOURCE_ID}/import-jobs", headers=headers())
    fetched = client.get(f"/import-jobs/{IMPORT_JOB_ID}", headers=headers())

    assert created.status_code == 201
    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert created.json()["id"] == str(IMPORT_JOB_ID)
    assert created.json()["status"] == "pending"
    assert created.json()["validation_issue_count"] == 0
    assert created.json()["created_at"].endswith("Z")
    assert listed.json()[0]["datasource_id"] == str(DATASOURCE_ID)
    assert listed.json()[0]["validation_issue_count"] == 0
    assert fetched.json()["validation_issue_count"] == 3
    assert service.create.await_args.args[0] == DATASOURCE_ID
    assert service.create.await_args.args[1] == ORGANIZATION_ID
    assert service.create.await_args.args[2].idempotency_key == "key"
    assert service.list_with_validation_issue_count.await_args.args == (
        DATASOURCE_ID,
        ORGANIZATION_ID,
    )
    assert service.get_with_validation_issue_count.await_args.args == (
        IMPORT_JOB_ID,
        ORGANIZATION_ID,
    )


@pytest.mark.parametrize(
    ("target_status", "payload", "processed_items", "failed_items", "error_message"),
    [
        (ImportJobStatus.RUNNING, {}, 0, 0, None),
        (ImportJobStatus.CANCELLED, {}, 0, 0, None),
        (ImportJobStatus.COMPLETED, {"processed_items": 2}, 2, 0, None),
        (ImportJobStatus.FAILED, {"error_message": "upstream failed"}, 0, 0, "upstream failed"),
        (ImportJobStatus.CANCELLED, {"processed_items": 1}, 1, 0, None),
    ],
)
def test_import_job_transition_accepts_every_service_allowed_target(
    target_status: ImportJobStatus,
    payload: dict[str, int | str],
    processed_items: int,
    failed_items: int,
    error_message: str | None,
) -> None:
    client, service = client_with_service()
    service.transition = AsyncMock(
        return_value=import_job(
            target_status,
            processed_items=processed_items,
            failed_items=failed_items,
            error_message=error_message,
        )
    )

    response = client.patch(
        f"/import-jobs/{IMPORT_JOB_ID}/status",
        headers=headers(),
        json={"status": target_status.value, **payload},
    )

    assert response.status_code == 200
    assert response.json()["status"] == target_status.value
    assert service.transition.await_args.args[0:2] == (IMPORT_JOB_ID, ORGANIZATION_ID)
    assert service.transition.await_args.args[2].status is target_status


def test_import_job_api_rejects_invalid_tenant_path_and_payload_values() -> None:
    client, service = client_with_service()

    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/import-jobs", json={"idempotency_key": "key"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/datasources/{DATASOURCE_ID}/import-jobs",
            headers={"X-Organization-ID": "invalid"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/datasources/not-a-uuid/import-jobs",
            headers=headers(),
            json={"idempotency_key": "key"},
        ).status_code
        == 422
    )
    assert client.get("/import-jobs/not-a-uuid", headers=headers()).status_code == 422
    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/import-jobs",
            headers=headers(),
            json={"idempotency_key": "   "},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/import-jobs",
            headers=headers(),
            json={"idempotency_key": "key", "total_items": -1},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "invalid"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "running", "processed_items": -1},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "running", "failed_items": -1},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "failed"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "failed", "error_message": "   "},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "completed", "error_message": "unexpected"},
        ).status_code
        == 422
    )
    assert service.create.await_count == 0
    assert service.transition.await_count == 0


@pytest.mark.parametrize(
    ("method", "path", "side_effect", "expected_status"),
    [
        ("post", "datasource", DatasourceNotFoundError(DATASOURCE_ID), 404),
        ("get", "import-job", ImportJobNotFoundError(IMPORT_JOB_ID), 404),
        ("patch", "import-job", InvalidImportJobTransitionError(), 409),
        ("post", "datasource", IdempotencyConflictError("key"), 409),
        ("patch", "import-job", InvalidImportJobCountersError(), 422),
    ],
)
def test_import_job_api_maps_domain_exceptions_safely(
    method: str,
    path: str,
    side_effect: Exception,
    expected_status: int,
) -> None:
    client, service = client_with_service()
    if method == "post":
        service.create.side_effect = side_effect
        response = client.post(
            f"/datasources/{DATASOURCE_ID}/import-jobs",
            headers=headers(),
            json={"idempotency_key": "key"},
        )
    elif method == "get":
        service.get_with_validation_issue_count.side_effect = side_effect
        response = client.get(f"/import-jobs/{IMPORT_JOB_ID}", headers=headers())
    else:
        service.transition.side_effect = side_effect
        response = client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(),
            json={"status": "running"},
        )

    assert response.status_code == expected_status
    assert "detail" in response.json()


def test_import_job_api_forwards_other_tenant_and_maps_isolation_to_not_found() -> None:
    client, service = client_with_service()
    service.create.side_effect = DatasourceNotFoundError(DATASOURCE_ID)
    service.list_with_validation_issue_count.side_effect = DatasourceNotFoundError(DATASOURCE_ID)
    service.get_with_validation_issue_count.side_effect = ImportJobNotFoundError(IMPORT_JOB_ID)
    service.transition.side_effect = ImportJobNotFoundError(IMPORT_JOB_ID)

    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/import-jobs",
            headers=headers(OTHER_ORGANIZATION_ID),
            json={"idempotency_key": "key"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/datasources/{DATASOURCE_ID}/import-jobs", headers=headers(OTHER_ORGANIZATION_ID)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/import-jobs/{IMPORT_JOB_ID}", headers=headers(OTHER_ORGANIZATION_ID)
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/import-jobs/{IMPORT_JOB_ID}/status",
            headers=headers(OTHER_ORGANIZATION_ID),
            json={"status": "running"},
        ).status_code
        == 404
    )
    assert service.create.await_args.args[1] == OTHER_ORGANIZATION_ID
    assert service.list_with_validation_issue_count.await_args.args[1] == OTHER_ORGANIZATION_ID
    assert service.get_with_validation_issue_count.await_args.args[1] == OTHER_ORGANIZATION_ID
    assert service.transition.await_args.args[1] == OTHER_ORGANIZATION_ID
