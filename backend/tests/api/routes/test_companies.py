from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.company import get_company_service
from app.api.dependencies.tenant import get_temporary_organization_id
from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.api.routes.companies import router as companies_router
from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.company import CompanyService

ORGANIZATION_ID = uuid4()


def create_test_client(service: CompanyService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(companies_router)
    app.dependency_overrides[get_company_service] = lambda: service
    app.dependency_overrides[get_temporary_organization_id] = lambda: ORGANIZATION_ID
    return TestClient(app)


def create_company() -> Company:
    company = Company(
        organization_id=ORGANIZATION_ID,
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
        isin="US1234567890",
        website="https://example.com",
        description="Example description",
        is_active=True,
    )
    company.id = uuid4()
    company.created_at = datetime(
        2026,
        7,
        21,
        10,
        0,
        tzinfo=UTC,
    )
    company.updated_at = datetime(
        2026,
        7,
        21,
        10,
        30,
        tzinfo=UTC,
    )
    return company


def create_service_mock() -> MagicMock:
    service = MagicMock(spec=CompanyService)
    service.create = AsyncMock()
    service.list = AsyncMock()
    service.get_by_id = AsyncMock()
    service.update = AsyncMock()
    service.delete = AsyncMock()
    return service


def test_companies_router_metadata() -> None:
    assert companies_router.prefix == "/companies"
    assert "companies" in companies_router.tags


def test_create_company_returns_created_company() -> None:
    company = create_company()
    service = create_service_mock()
    service.create.return_value = company
    client = create_test_client(service)

    response = client.post(
        "/companies",
        json={
            "name": "Example Company",
            "ticker": "EXM",
            "exchange": "NASDAQ",
            "isin": "US1234567890",
            "website": "https://example.com",
            "description": "Example description",
            "is_active": True,
        },
    )
    body = response.json()
    organization_id, payload = service.create.await_args.args

    assert response.status_code == 201
    assert body["id"] == str(company.id)
    assert body["name"] == company.name
    assert body["ticker"] == company.ticker
    assert body["exchange"] == company.exchange
    assert body["isin"] == company.isin
    assert body["website"] == company.website
    assert body["description"] == company.description
    assert body["is_active"] is company.is_active
    assert datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")) == company.created_at
    assert datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00")) == company.updated_at
    service.create.assert_awaited_once()
    assert organization_id == ORGANIZATION_ID
    assert isinstance(payload, CompanyCreate)
    assert payload.name == "Example Company"
    assert payload.ticker == "EXM"
    assert payload.exchange == "NASDAQ"


def test_create_company_returns_conflict_when_duplicate() -> None:
    service = create_service_mock()
    service.create.side_effect = CompanyAlreadyExistsError(
        exchange="NASDAQ",
        ticker="EXM",
    )
    client = create_test_client(service)

    response = client.post(
        "/companies",
        json={
            "name": "Example Company",
            "ticker": "EXM",
            "exchange": "NASDAQ",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Company with exchange 'NASDAQ' and ticker 'EXM' already exists."
    }


def test_create_company_rejects_invalid_payload() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.post(
        "/companies",
        json={
            "ticker": "EXM",
            "exchange": "NASDAQ",
        },
    )

    assert response.status_code == 422
    service.create.assert_not_awaited()


def test_list_companies_returns_companies() -> None:
    first = create_company()
    second = create_company()
    service = create_service_mock()
    service.list.return_value = [first, second]
    client = create_test_client(service)

    response = client.get(
        "/companies",
        params={
            "offset": 10,
            "limit": 25,
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["id"] == str(first.id)
    assert response.json()[1]["id"] == str(second.id)
    service.list.assert_awaited_once_with(
        ORGANIZATION_ID,
        offset=10,
        limit=25,
    )


def test_list_companies_uses_default_pagination() -> None:
    service = create_service_mock()
    service.list.return_value = []
    client = create_test_client(service)

    response = client.get("/companies")

    assert response.status_code == 200
    assert response.json() == []
    service.list.assert_awaited_once_with(
        ORGANIZATION_ID,
        offset=0,
        limit=100,
    )


def test_list_companies_rejects_negative_offset() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.get(
        "/companies",
        params={"offset": -1},
    )

    assert response.status_code == 422
    service.list.assert_not_awaited()


def test_list_companies_rejects_zero_limit() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.get(
        "/companies",
        params={"limit": 0},
    )

    assert response.status_code == 422
    service.list.assert_not_awaited()


def test_list_companies_rejects_limit_above_maximum() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.get(
        "/companies",
        params={"limit": 101},
    )

    assert response.status_code == 422
    service.list.assert_not_awaited()


def test_get_company_returns_company() -> None:
    company = create_company()
    service = create_service_mock()
    service.get_by_id.return_value = company
    client = create_test_client(service)

    response = client.get(f"/companies/{company.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(company.id)
    service.get_by_id.assert_awaited_once_with(company.id, ORGANIZATION_ID)


def test_get_company_returns_not_found_when_missing() -> None:
    company_id = uuid4()
    service = create_service_mock()
    service.get_by_id.side_effect = CompanyNotFoundError(company_id)
    client = create_test_client(service)

    response = client.get(f"/companies/{company_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Company with id '{company_id}' was not found."}
    service.get_by_id.assert_awaited_once_with(company_id, ORGANIZATION_ID)


def test_get_company_rejects_invalid_uuid() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.get("/companies/not-a-uuid")

    assert response.status_code == 422
    service.get_by_id.assert_not_awaited()


def test_update_company_returns_updated_company() -> None:
    company = create_company()
    company.name = "Updated Company"
    company.website = None
    company.is_active = False
    service = create_service_mock()
    service.update.return_value = company
    client = create_test_client(service)

    response = client.patch(
        f"/companies/{company.id}",
        json={
            "name": "Updated Company",
            "website": None,
            "is_active": False,
        },
    )
    company_id, organization_id, payload = service.update.await_args.args

    assert response.status_code == 200
    assert response.json()["id"] == str(company.id)
    assert response.json()["name"] == "Updated Company"
    assert response.json()["website"] is None
    assert response.json()["is_active"] is False
    service.update.assert_awaited_once()
    assert company_id == company.id
    assert organization_id == ORGANIZATION_ID
    assert isinstance(payload, CompanyUpdate)
    assert payload.name == "Updated Company"
    assert payload.website is None
    assert payload.is_active is False


def test_update_company_accepts_empty_payload() -> None:
    company = create_company()
    service = create_service_mock()
    service.update.return_value = company
    client = create_test_client(service)

    response = client.patch(f"/companies/{company.id}", json={})
    _, organization_id, payload = service.update.await_args.args

    assert response.status_code == 200
    service.update.assert_awaited_once()
    assert organization_id == ORGANIZATION_ID
    assert isinstance(payload, CompanyUpdate)
    assert payload.model_dump(exclude_unset=True) == {}


def test_update_company_returns_not_found_when_missing() -> None:
    company_id = uuid4()
    service = create_service_mock()
    service.update.side_effect = CompanyNotFoundError(company_id)
    client = create_test_client(service)

    response = client.patch(
        f"/companies/{company_id}",
        json={"name": "Updated Company"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": f"Company with id '{company_id}' was not found."}


def test_update_company_returns_conflict_when_duplicate() -> None:
    company_id = uuid4()
    service = create_service_mock()
    service.update.side_effect = CompanyAlreadyExistsError(
        exchange="NYSE",
        ticker="OTHER",
    )
    client = create_test_client(service)

    response = client.patch(
        f"/companies/{company_id}",
        json={"exchange": "NYSE", "ticker": "OTHER"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Company with exchange 'NYSE' and ticker 'OTHER' already exists."
    }


def test_update_company_rejects_invalid_uuid() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.patch(
        "/companies/not-a-uuid",
        json={"name": "Updated"},
    )

    assert response.status_code == 422
    service.update.assert_not_awaited()


def test_update_company_rejects_invalid_payload() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.patch(
        f"/companies/{uuid4()}",
        json={"ticker": ""},
    )

    assert response.status_code == 422
    service.update.assert_not_awaited()


def test_delete_company_returns_no_content() -> None:
    company_id = uuid4()
    service = create_service_mock()
    client = create_test_client(service)

    response = client.delete(f"/companies/{company_id}")

    assert response.status_code == 204
    assert response.content == b""
    service.delete.assert_awaited_once_with(company_id, ORGANIZATION_ID)


def test_delete_company_returns_not_found_when_missing() -> None:
    company_id = uuid4()
    service = create_service_mock()
    service.delete.side_effect = CompanyNotFoundError(company_id)
    client = create_test_client(service)

    response = client.delete(f"/companies/{company_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Company with id '{company_id}' was not found."}


def test_delete_company_rejects_invalid_uuid() -> None:
    service = create_service_mock()
    client = create_test_client(service)

    response = client.delete("/companies/not-a-uuid")

    assert response.status_code == 422
    service.delete.assert_not_awaited()


def test_api_router_includes_company_routes() -> None:
    company = create_company()
    service = create_service_mock()
    service.create.return_value = company
    service.list.return_value = [company]
    service.get_by_id.return_value = company
    service.update.return_value = company
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_company_service] = lambda: service
    app.dependency_overrides[get_temporary_organization_id] = lambda: ORGANIZATION_ID
    client = TestClient(app)

    assert client.get("/companies").status_code == 200
    assert client.get(f"/companies/{company.id}").status_code == 200
    assert (
        client.patch(
            f"/companies/{company.id}",
            json={"name": "Updated Company"},
        ).status_code
        == 200
    )
    assert client.delete(f"/companies/{company.id}").status_code == 204
    assert (
        client.post(
            "/companies",
            json={
                "name": "Example Company",
                "ticker": "EXM",
                "exchange": "NASDAQ",
            },
        ).status_code
        == 201
    )
