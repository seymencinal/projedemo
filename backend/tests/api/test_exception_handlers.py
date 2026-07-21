import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.company import get_company_service
from app.api.dependencies.tenant import get_temporary_organization_id
from app.api.exception_handlers import (
    company_already_exists_exception_handler,
    company_not_found_exception_handler,
    organization_already_exists_exception_handler,
    organization_not_found_exception_handler,
    register_exception_handlers,
)
from app.api.routes.companies import router as companies_router
from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)
from app.exceptions.organization import OrganizationAlreadyExistsError, OrganizationNotFoundError
from app.services.company import CompanyService


def create_test_client(
    service: CompanyService,
) -> tuple[FastAPI, TestClient]:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(companies_router)
    app.dependency_overrides[get_company_service] = lambda: service
    app.dependency_overrides[get_temporary_organization_id] = uuid4
    return app, TestClient(app)


def test_register_exception_handlers_registers_expected_handlers() -> None:
    app = FastAPI()

    register_exception_handlers(app)

    assert app.exception_handlers[CompanyNotFoundError] is company_not_found_exception_handler
    assert (
        app.exception_handlers[CompanyAlreadyExistsError]
        is company_already_exists_exception_handler
    )
    assert (
        app.exception_handlers[OrganizationNotFoundError]
        is organization_not_found_exception_handler
    )
    assert (
        app.exception_handlers[OrganizationAlreadyExistsError]
        is organization_already_exists_exception_handler
    )
    assert Exception not in app.exception_handlers


def test_company_not_found_exception_returns_404() -> None:
    service = MagicMock(spec=CompanyService)
    company_id = uuid4()
    service.get_by_id = AsyncMock(
        side_effect=CompanyNotFoundError(company_id),
    )
    _, client = create_test_client(service)

    response = client.get(f"/companies/{company_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Company with id '{company_id}' was not found."}


def test_company_already_exists_exception_returns_409() -> None:
    service = MagicMock(spec=CompanyService)
    service.create = AsyncMock(
        side_effect=CompanyAlreadyExistsError(
            exchange="NASDAQ",
            ticker="EXM",
        ),
    )
    _, client = create_test_client(service)

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


@pytest.mark.asyncio
async def test_company_not_found_handler_returns_json_response() -> None:
    company_id = uuid4()
    response = await company_not_found_exception_handler(
        MagicMock(),
        CompanyNotFoundError(company_id),
    )

    assert response.status_code == 404
    assert json.loads(bytes(response.body)) == {
        "detail": f"Company with id '{company_id}' was not found."
    }


@pytest.mark.asyncio
async def test_company_already_exists_handler_returns_json_response() -> None:
    response = await company_already_exists_exception_handler(
        MagicMock(),
        CompanyAlreadyExistsError(
            exchange="NASDAQ",
            ticker="EXM",
        ),
    )

    assert response.status_code == 409
    assert json.loads(bytes(response.body)) == {
        "detail": "Company with exchange 'NASDAQ' and ticker 'EXM' already exists."
    }


@pytest.mark.asyncio
async def test_organization_exception_handlers_return_safe_responses() -> None:
    organization_id = uuid4()
    missing_response = await organization_not_found_exception_handler(
        MagicMock(), OrganizationNotFoundError(organization_id)
    )
    duplicate_response = await organization_already_exists_exception_handler(
        MagicMock(), OrganizationAlreadyExistsError("example")
    )

    assert missing_response.status_code == 404
    assert json.loads(bytes(missing_response.body)) == {
        "detail": f"Organization with id '{organization_id}' was not found."
    }
    assert duplicate_response.status_code == 409
    assert json.loads(bytes(duplicate_response.body)) == {
        "detail": "Organization with slug 'example' already exists."
    }
