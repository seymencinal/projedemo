from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_imported_record_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router
from app.exceptions.research import ImportJobNotFoundError
from app.schemas.imported_record import ImportedRecordPage, ImportedRecordRead
from app.services.imported_record import ImportedRecordService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
IMPORT_JOB_ID = UUID("00000000-0000-0000-0000-000000000030")


def item(source_row_number: int) -> ImportedRecordRead:
    return ImportedRecordRead(
        id=uuid4(),
        source_row_number=source_row_number,
        created_at=datetime(2026, 7, 24, tzinfo=UTC),
    )


def page(
    items: list[ImportedRecordRead] | None = None,
    *,
    offset: int = 0,
    limit: int = 100,
    total: int | None = None,
) -> ImportedRecordPage:
    records = items or []
    return ImportedRecordPage(
        items=records, offset=offset, limit=limit, total=len(records) if total is None else total
    )


def client_with_service() -> tuple[TestClient, MagicMock]:
    service = MagicMock(spec=ImportedRecordService)
    service.list_for_import_job = AsyncMock(return_value=page())
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_imported_record_service] = lambda: service
    return TestClient(app), service


def headers(organization_id: UUID = ORGANIZATION_ID) -> dict[str, str]:
    return {"X-Organization-ID": str(organization_id)}


def url(datasource_id: UUID = DATASOURCE_ID, import_job_id: UUID = IMPORT_JOB_ID) -> str:
    return f"/datasources/{datasource_id}/import-jobs/{import_job_id}/records"


def test_list_imported_records_returns_only_public_ordered_fields() -> None:
    client, service = client_with_service()
    first, second = item(2), item(4)
    service.list_for_import_job.return_value = page([first, second], total=3)

    response = client.get(url(), headers=headers())

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0 and body["limit"] == 100 and body["total"] == 3
    assert [record["source_row_number"] for record in body["items"]] == [2, 4]
    assert set(body["items"][0]) == {"id", "source_row_number", "created_at"}
    assert "import_job_id" not in body["items"][0]
    assert "raw_row_hash" not in body["items"][0]
    assert "content" not in body["items"][0]
    service.list_for_import_job.assert_awaited_once_with(
        ORGANIZATION_ID, DATASOURCE_ID, IMPORT_JOB_ID, offset=0, limit=100
    )


@pytest.mark.parametrize(
    ("params", "expected_offset", "expected_limit"),
    [({}, 0, 100), ({"offset": 1, "limit": 1}, 1, 1), ({"offset": 99}, 99, 100)],
)
def test_list_imported_records_forwards_pagination_and_allows_empty_pages(
    params: dict[str, int], expected_offset: int, expected_limit: int
) -> None:
    client, service = client_with_service()
    service.list_for_import_job.return_value = page(
        [], offset=expected_offset, limit=expected_limit, total=2
    )

    response = client.get(url(), params=params, headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "offset": expected_offset,
        "limit": expected_limit,
        "total": 2,
    }
    service.list_for_import_job.assert_awaited_once_with(
        ORGANIZATION_ID,
        DATASOURCE_ID,
        IMPORT_JOB_ID,
        offset=expected_offset,
        limit=expected_limit,
    )


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 101}])
def test_list_imported_records_rejects_invalid_pagination(params: dict[str, int]) -> None:
    client, service = client_with_service()

    response = client.get(url(), params=params, headers=headers())

    assert response.status_code == 422
    service.list_for_import_job.assert_not_awaited()


@pytest.mark.parametrize("error", [ImportJobNotFoundError(IMPORT_JOB_ID)])
def test_list_imported_records_hides_cross_tenant_and_datasource_mismatch(
    error: ImportJobNotFoundError,
) -> None:
    client, service = client_with_service()
    service.list_for_import_job.side_effect = error

    response = client.get(url(), headers=headers(uuid4()))

    assert response.status_code == 404
    assert response.json() == {"detail": str(error)}


def test_list_imported_records_rejects_missing_tenant_and_invalid_uuids() -> None:
    client, service = client_with_service()

    assert client.get(url()).status_code == 422
    assert (
        client.get(url().replace(str(DATASOURCE_ID), "invalid"), headers=headers()).status_code
        == 422
    )
    assert (
        client.get(url().replace(str(IMPORT_JOB_ID), "invalid"), headers=headers()).status_code
        == 422
    )
    assert service.list_for_import_job.await_count == 0
