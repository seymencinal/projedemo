from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_mapping_preparation_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router
from app.exceptions.csv_mapping import (
    BlankSourceColumnError,
    DuplicateSourceColumnError,
    MissingRequiredCanonicalFieldError,
    UnknownCanonicalFieldError,
)
from app.exceptions.research import DatasourceNotFoundError, IdempotencyConflictError
from app.exceptions.uploaded_file import UploadedFileNotFoundError
from app.models.import_job import ImportJobStatus
from app.schemas.csv_mapping import CsvImportMappingAcceptedRead
from app.services.mapping_preparation import MappingPreparationService

ORGANIZATION_ID = uuid4()
OTHER_ORGANIZATION_ID = uuid4()
DATASOURCE_ID = uuid4()
UPLOADED_FILE_ID = uuid4()
IMPORT_JOB_ID = uuid4()


def accepted_response() -> CsvImportMappingAcceptedRead:
    return CsvImportMappingAcceptedRead(
        import_job_id=IMPORT_JOB_ID,
        status=ImportJobStatus.PENDING,
        uploaded_file_id=UPLOADED_FILE_ID,
        datasource_id=DATASOURCE_ID,
        accepted_mapping={"content": "body"},
    )


def client_with_service() -> tuple[TestClient, MagicMock]:
    service = MagicMock(spec=MappingPreparationService)
    service.prepare = AsyncMock(return_value=accepted_response())
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_mapping_preparation_service] = lambda: service
    return TestClient(app), service


def headers(organization_id: UUID = ORGANIZATION_ID) -> dict[str, str]:
    return {"X-Organization-ID": str(organization_id)}


def request_payload(mapping: dict[str, str] | None = None) -> dict[str, object]:
    return {
        "idempotency_key": " mapping-key ",
        "mapping": {"content": "body"} if mapping is None else mapping,
    }


def test_prepare_csv_import_returns_pending_job_and_forwards_tenant_scope() -> None:
    client, service = client_with_service()

    response = client.post(
        f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
        headers=headers(),
        json=request_payload(),
    )

    assert response.status_code == 201
    assert response.json() == {
        "import_job_id": str(IMPORT_JOB_ID),
        "status": "pending",
        "uploaded_file_id": str(UPLOADED_FILE_ID),
        "datasource_id": str(DATASOURCE_ID),
        "accepted_mapping": {"content": "body"},
    }
    assert service.prepare.await_args.args[:3] == (
        DATASOURCE_ID,
        UPLOADED_FILE_ID,
        ORGANIZATION_ID,
    )
    assert service.prepare.await_args.args[3].idempotency_key == "mapping-key"


@pytest.mark.parametrize(
    ("mapping", "error"),
    [
        ({"content": "body", "unknown": "value"}, UnknownCanonicalFieldError()),
        ({"author": "author"}, MissingRequiredCanonicalFieldError()),
        ({"content": "body", "author": "body"}, DuplicateSourceColumnError()),
        ({"content": "   "}, BlankSourceColumnError()),
    ],
)
def test_prepare_csv_import_maps_invalid_mapping_errors_to_safe_validation_response(
    mapping: dict[str, str], error: Exception
) -> None:
    client, service = client_with_service()
    service.prepare.side_effect = error

    response = client.post(
        f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
        headers=headers(),
        json=request_payload(mapping),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "CSV mapping is invalid."}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (IdempotencyConflictError("mapping-key"), 409),
        (DatasourceNotFoundError(DATASOURCE_ID), 404),
        (UploadedFileNotFoundError(UPLOADED_FILE_ID), 404),
    ],
)
def test_prepare_csv_import_maps_idempotency_and_scoped_resource_errors(
    error: Exception, expected_status: int
) -> None:
    client, service = client_with_service()
    service.prepare.side_effect = error

    response = client.post(
        f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
        headers=headers(),
        json=request_payload(),
    )

    assert response.status_code == expected_status
    assert "detail" in response.json()


def test_prepare_csv_import_rejects_invalid_request_and_tenant_values() -> None:
    client, service = client_with_service()

    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
            json=request_payload(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/datasources/not-a-uuid/files/{UPLOADED_FILE_ID}/imports",
            headers=headers(),
            json=request_payload(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/files/not-a-uuid/imports",
            headers=headers(),
            json=request_payload(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
            headers={"X-Organization-ID": "invalid"},
            json=request_payload(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
            headers=headers(),
            json=request_payload({}),
        ).status_code
        == 422
    )
    assert service.prepare.await_count == 0


def test_prepare_csv_import_forwards_cross_tenant_context_and_hides_mismatch() -> None:
    client, service = client_with_service()
    service.prepare.side_effect = DatasourceNotFoundError(DATASOURCE_ID)

    response = client.post(
        f"/datasources/{DATASOURCE_ID}/files/{UPLOADED_FILE_ID}/imports",
        headers=headers(OTHER_ORGANIZATION_ID),
        json=request_payload(),
    )

    assert response.status_code == 404
    assert service.prepare.await_args.args[:3] == (
        DATASOURCE_ID,
        UPLOADED_FILE_ID,
        OTHER_ORGANIZATION_ID,
    )
