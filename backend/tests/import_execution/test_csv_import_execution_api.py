from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_csv_import_execution_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router
from app.exceptions.csv_import_execution import (
    ImportJobNotExecutableError,
    InvalidImportedRecordError,
)
from app.models.import_job import ImportJobStatus
from app.services.csv_import_execution import CsvImportExecutionService

ORGANIZATION_ID = uuid4()
DATASOURCE_ID = uuid4()
IMPORT_JOB_ID = uuid4()


def completed_job() -> SimpleNamespace:
    now = datetime(2026, 7, 23, tzinfo=UTC)
    return SimpleNamespace(
        id=IMPORT_JOB_ID,
        organization_id=ORGANIZATION_ID,
        research_id=uuid4(),
        datasource_id=DATASOURCE_ID,
        status=ImportJobStatus.COMPLETED,
        total_items=2,
        processed_items=2,
        failed_items=0,
        error_message=None,
        idempotency_key="key",
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


def client_with_service() -> tuple[TestClient, MagicMock]:
    service = MagicMock(spec=CsvImportExecutionService)
    service.execute = AsyncMock(return_value=completed_job())
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_csv_import_execution_service] = lambda: service
    return TestClient(app), service


def headers(organization_id: UUID = ORGANIZATION_ID) -> dict[str, str]:
    return {"X-Organization-ID": str(organization_id)}


def test_execute_csv_import_returns_completed_import_job() -> None:
    client, service = client_with_service()

    response = client.post(
        f"/datasources/{DATASOURCE_ID}/import-jobs/{IMPORT_JOB_ID}/execute",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["processed_items"] == 2
    assert service.execute.await_args.args == (IMPORT_JOB_ID, ORGANIZATION_ID, DATASOURCE_ID)


@pytest.mark.parametrize("error", [ImportJobNotExecutableError(), InvalidImportedRecordError()])
def test_execute_csv_import_maps_safe_execution_errors(error: Exception) -> None:
    client, service = client_with_service()
    service.execute.side_effect = error

    response = client.post(
        f"/datasources/{DATASOURCE_ID}/import-jobs/{IMPORT_JOB_ID}/execute",
        headers=headers(),
    )

    assert response.status_code in {409, 422}
    assert response.json() == {"detail": "CSV import execution failed."}


def test_execute_csv_import_rejects_missing_tenant_and_invalid_ids() -> None:
    client, service = client_with_service()

    assert (
        client.post(f"/datasources/{DATASOURCE_ID}/import-jobs/{IMPORT_JOB_ID}/execute").status_code
        == 422
    )
    assert (
        client.post(
            f"/datasources/not-a-uuid/import-jobs/{IMPORT_JOB_ID}/execute", headers=headers()
        ).status_code
        == 422
    )
    assert service.execute.await_count == 0
