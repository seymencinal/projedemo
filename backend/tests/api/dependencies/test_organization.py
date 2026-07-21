from inspect import signature
from typing import Annotated, get_args, get_origin, get_type_hints
from unittest.mock import MagicMock

from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.database import get_db_session
from app.api.dependencies.organization import (
    DatabaseSession,
    OrganizationServiceDependency,
    get_organization_service,
)
from app.services.organization import OrganizationService


def test_get_organization_service_returns_service_with_session() -> None:
    session = MagicMock(spec=AsyncSession)

    service = get_organization_service(session)

    assert isinstance(service, OrganizationService)
    assert service._session is session


def test_organization_dependency_metadata_is_override_friendly() -> None:
    database_arguments = get_args(DatabaseSession)
    service_arguments = get_args(OrganizationServiceDependency)

    assert get_origin(DatabaseSession) is Annotated
    assert database_arguments[0] is AsyncSession
    assert isinstance(database_arguments[1], Depends)
    assert database_arguments[1].dependency is get_db_session
    assert get_origin(OrganizationServiceDependency) is Annotated
    assert service_arguments[0] is OrganizationService
    assert isinstance(service_arguments[1], Depends)
    assert service_arguments[1].dependency is get_organization_service


def test_get_organization_service_has_a_typed_session_parameter() -> None:
    type_hints = get_type_hints(get_organization_service, include_extras=True)

    assert list(signature(get_organization_service).parameters) == ["session"]
    assert type_hints["session"] == DatabaseSession
    assert type_hints["return"] is OrganizationService
