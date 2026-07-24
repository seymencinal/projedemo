from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_import_validation_issue_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router
from app.exceptions.research import ImportJobNotFoundError
from app.schemas.import_validation_issue import (
    ImportValidationIssuePage,
    ImportValidationIssueRead,
)
from app.services.import_validation_issue import ImportValidationIssueService

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
IMPORT_JOB_ID = UUID("00000000-0000-0000-0000-000000000030")


def read_issue(source_row_number: int, issue_order: int) -> ImportValidationIssueRead:
    return ImportValidationIssueRead(
        id=uuid4(),
        source_row_number=source_row_number,
        issue_order=issue_order,
        canonical_field="content",
        source_column="body",
        code="required",
        message="CSV import contains an invalid record.",
        created_at=datetime(2026, 7, 23, tzinfo=UTC),
    )


def page(items: list[ImportValidationIssueRead] | None = None) -> ImportValidationIssuePage:
    return ImportValidationIssuePage(items=items or [], offset=0, limit=100, total=len(items or []))


def client_with_service() -> tuple[TestClient, MagicMock]:
    service = MagicMock(spec=ImportValidationIssueService)
    service.list_for_import_job = AsyncMock(return_value=page())
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_import_validation_issue_service] = lambda: service
    return TestClient(app), service


def headers(organization_id: UUID = ORGANIZATION_ID) -> dict[str, str]:
    return {"X-Organization-ID": str(organization_id)}


def url(datasource_id: UUID = DATASOURCE_ID, import_job_id: UUID = IMPORT_JOB_ID) -> str:
    return f"/datasources/{datasource_id}/import-jobs/{import_job_id}/validation-issues"


def test_list_validation_issues_returns_only_public_fields_in_deterministic_order() -> None:
    client, service = client_with_service()
    first = read_issue(2, 1)
    second = read_issue(4, 0)
    service.list_for_import_job.return_value = ImportValidationIssuePage(
        items=[first, second], offset=0, limit=100, total=2
    )

    response = client.get(url(), headers=headers())

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0 and body["limit"] == 100 and body["total"] == 2
    assert [item["source_row_number"] for item in body["items"]] == [2, 4]
    assert set(body["items"][0]) == {
        "id",
        "source_row_number",
        "issue_order",
        "canonical_field",
        "source_column",
        "code",
        "message",
        "created_at",
    }
    assert "import_job_id" not in body["items"][0]
    service.list_for_import_job.assert_awaited_once_with(
        ORGANIZATION_ID, DATASOURCE_ID, IMPORT_JOB_ID, offset=0, limit=100
    )


@pytest.mark.parametrize(
    ("params", "expected_offset", "expected_limit"),
    [({}, 0, 100), ({"offset": 1, "limit": 1}, 1, 1), ({"offset": 99}, 99, 100)],
)
def test_list_validation_issues_forwards_offset_limit_and_allows_empty_page(
    params: dict[str, int], expected_offset: int, expected_limit: int
) -> None:
    client, service = client_with_service()
    service.list_for_import_job.return_value = ImportValidationIssuePage(
        items=[],
        offset=expected_offset,
        limit=expected_limit,
        total=2,
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
def test_list_validation_issues_rejects_invalid_pagination(params: dict[str, int]) -> None:
    client, service = client_with_service()

    response = client.get(url(), params=params, headers=headers())

    assert response.status_code == 422
    service.list_for_import_job.assert_not_awaited()


@pytest.mark.parametrize("error", [ImportJobNotFoundError(IMPORT_JOB_ID)])
def test_list_validation_issues_hides_cross_tenant_and_datasource_mismatch(
    error: ImportJobNotFoundError,
) -> None:
    client, service = client_with_service()
    service.list_for_import_job.side_effect = error

    response = client.get(url(), headers=headers(uuid4()))

    assert response.status_code == 404
    assert response.json() == {"detail": str(error)}


def test_list_validation_issues_rejects_missing_tenant_and_invalid_uuids() -> None:
    client, service = client_with_service()

    assert client.get(url()).status_code == 422
    assert (
        client.get(
            url(datasource_id=DATASOURCE_ID, import_job_id=IMPORT_JOB_ID).replace(
                str(DATASOURCE_ID), "invalid"
            ),
            headers=headers(),
        ).status_code
        == 422
    )
    assert (
        client.get(
            url(import_job_id=UUID(int=0)).replace(str(UUID(int=0)), "invalid"), headers=headers()
        ).status_code
        == 422
    )
    assert service.list_for_import_job.await_count == 0
