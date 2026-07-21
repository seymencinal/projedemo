from inspect import signature
from typing import Annotated, get_args, get_origin, get_type_hints
from unittest.mock import MagicMock

from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.company import (
    CompanyServiceDependency,
    DatabaseSession,
    get_company_service,
)
from app.api.dependencies.database import get_db_session
from app.services.company import CompanyService


def test_get_company_service_returns_service_with_session() -> None:
    session = MagicMock(spec=AsyncSession)

    service = get_company_service(session)

    assert isinstance(service, CompanyService)
    assert service._session is session


def test_get_company_service_returns_new_instance_each_time() -> None:
    session = MagicMock(spec=AsyncSession)

    first = get_company_service(session)
    second = get_company_service(session)

    assert first is not second
    assert first._session is session
    assert second._session is session


def test_database_session_dependency_metadata() -> None:
    arguments = get_args(DatabaseSession)
    dependency = arguments[1]

    assert get_origin(DatabaseSession) is Annotated
    assert arguments[0] is AsyncSession
    assert isinstance(dependency, Depends)
    assert dependency.dependency is get_db_session


def test_company_service_dependency_metadata() -> None:
    arguments = get_args(CompanyServiceDependency)
    dependency = arguments[1]

    assert get_origin(CompanyServiceDependency) is Annotated
    assert arguments[0] is CompanyService
    assert isinstance(dependency, Depends)
    assert dependency.dependency is get_company_service


def test_get_company_service_has_single_session_parameter() -> None:
    parameters = signature(get_company_service).parameters
    type_hints = get_type_hints(
        get_company_service,
        include_extras=True,
    )

    assert list(parameters) == ["session"]
    assert type_hints["session"] == DatabaseSession
    assert type_hints["return"] is CompanyService
