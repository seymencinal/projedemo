from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_csv_processing_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router
from app.exceptions.csv_processing import (
    CsvColumnLimitExceededError,
    CsvFileNotProcessableError,
    CsvRowLimitExceededError,
    EmptyCsvFileError,
    MalformedCsvError,
    UnsupportedCsvFileError,
)
from app.exceptions.research import DatasourceNotFoundError
from app.exceptions.storage import StoredFileNotFoundError
from app.exceptions.uploaded_file import UploadedFileNotFoundError
from app.services.csv_processing import CsvProcessingService

ORG = uuid4()
SOURCE = uuid4()
FILE = uuid4()


def client() -> tuple[TestClient, MagicMock]:
    service = MagicMock(spec=CsvProcessingService)
    service.summarize = AsyncMock(
        return_value=SimpleNamespace(
            uploaded_file_id=FILE,
            row_count=1,
            column_count=2,
            column_names=["a", "b"],
        )
    )
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_csv_processing_service] = lambda: service
    return TestClient(app), service


def test_csv_summary_success_is_public_and_tenant_scoped() -> None:
    test_client, service = client()
    response = test_client.post(
        f"/datasources/{SOURCE}/files/{FILE}/csv-summary",
        headers={"X-Organization-ID": str(ORG)},
    )
    assert response.status_code == 200
    assert response.json() == {
        "uploaded_file_id": str(FILE),
        "row_count": 1,
        "column_count": 2,
        "column_names": ["a", "b"],
    }
    service.summarize.assert_awaited_once_with(ORG, SOURCE, FILE)


def test_csv_summary_validates_path_and_tenant_header() -> None:
    test_client, _ = client()
    assert (
        test_client.post(
            "/datasources/not-a-uuid/files/not-a-uuid/csv-summary",
            headers={"X-Organization-ID": str(ORG)},
        ).status_code
        == 422
    )
    assert test_client.post(f"/datasources/{SOURCE}/files/{FILE}/csv-summary").status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (UploadedFileNotFoundError(FILE), 404),
        (DatasourceNotFoundError(SOURCE), 404),
        (UnsupportedCsvFileError(), 415),
        (EmptyCsvFileError(), 422),
        (MalformedCsvError(), 422),
        (CsvRowLimitExceededError(), 422),
        (CsvColumnLimitExceededError(), 422),
        (CsvFileNotProcessableError(), 409),
        (StoredFileNotFoundError("private.csv"), 404),
    ],
)
def test_csv_summary_maps_domain_errors(error: Exception, status_code: int) -> None:
    test_client, service = client()
    service.summarize.side_effect = error
    response = test_client.post(
        f"/datasources/{SOURCE}/files/{FILE}/csv-summary",
        headers={"X-Organization-ID": str(ORG)},
    )
    assert response.status_code == status_code
    assert "private.csv" not in response.json()["detail"]
