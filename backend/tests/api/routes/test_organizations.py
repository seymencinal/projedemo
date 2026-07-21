from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.company import get_company_service
from app.api.dependencies.organization import get_organization_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.organizations import router
from app.exceptions.organization import OrganizationAlreadyExistsError, OrganizationNotFoundError
from app.models.organization import Organization
from app.services.organization import OrganizationService


def create_organization() -> Organization:
    organization = Organization(name="Example", slug="example")
    organization.id = uuid4()
    organization.created_at = datetime(2026, 7, 21, tzinfo=UTC)
    organization.updated_at = datetime(2026, 7, 21, tzinfo=UTC)
    return organization


def create_client(service: MagicMock) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_organization_service] = lambda: service
    return TestClient(app)


def test_create_organization_returns_created_resource() -> None:
    organization = create_organization()
    service = MagicMock(spec=OrganizationService)
    service.create = AsyncMock(return_value=organization)

    response = create_client(service).post(
        "/organizations", json={"name": "Example", "slug": "example"}
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "example"
    payload = service.create.await_args.args[0]
    assert payload.slug == "example"


def test_list_and_get_organization_return_scoped_domain_resource() -> None:
    organization = create_organization()
    service = MagicMock(spec=OrganizationService)
    service.list = AsyncMock(return_value=[organization])
    service.get_by_id = AsyncMock(return_value=organization)
    client = create_client(service)

    assert client.get("/organizations").json()[0]["id"] == str(organization.id)
    assert client.get(f"/organizations/{organization.id}").json()["id"] == str(organization.id)


def test_organization_routes_validate_payloads_and_ids() -> None:
    service = MagicMock(spec=OrganizationService)
    client = create_client(service)

    assert (
        client.post("/organizations", json={"name": "", "slug": "invalid slug"}).status_code == 422
    )
    assert client.get("/organizations/not-a-uuid").status_code == 422
    service.create.assert_not_awaited()
    service.get_by_id.assert_not_awaited()


def test_organization_routes_return_safe_not_found_and_conflict_responses() -> None:
    service = MagicMock(spec=OrganizationService)
    organization_id = uuid4()
    service.get_by_id = AsyncMock(side_effect=OrganizationNotFoundError(organization_id))
    service.create = AsyncMock(side_effect=OrganizationAlreadyExistsError("example"))
    client = create_client(service)

    missing = client.get(f"/organizations/{organization_id}")
    duplicate = client.post("/organizations", json={"name": "Example", "slug": "example"})

    assert missing.status_code == 404
    assert missing.json() == {"detail": f"Organization with id '{organization_id}' was not found."}
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Organization with slug 'example' already exists."}


def test_company_routes_require_temporary_organization_header() -> None:
    from app.api.routes.companies import router as companies_router

    app = FastAPI()
    app.include_router(companies_router)
    app.dependency_overrides[get_company_service] = lambda: MagicMock(spec=OrganizationService)

    response = TestClient(app).get("/companies")

    assert response.status_code == 422


def test_company_routes_forward_temporary_organization_header_to_service() -> None:
    from app.api.routes.companies import router as companies_router
    from app.services.company import CompanyService

    organization_id = uuid4()
    service = MagicMock(spec=CompanyService)
    service.list = AsyncMock(return_value=[])
    app = FastAPI()
    app.include_router(companies_router)
    app.dependency_overrides[get_company_service] = lambda: service

    response = TestClient(app).get(
        "/companies",
        headers={"X-Organization-ID": str(organization_id)},
    )

    assert response.status_code == 200
    service.list.assert_awaited_once_with(organization_id, offset=0, limit=100)
