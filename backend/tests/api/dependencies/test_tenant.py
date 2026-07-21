from inspect import signature
from typing import Annotated, get_args, get_origin, get_type_hints
from uuid import UUID, uuid4

from fastapi.params import Depends, Header

from app.api.dependencies.tenant import (
    TemporaryOrganizationId,
    get_temporary_organization_id,
)


def test_temporary_organization_dependency_returns_header_value() -> None:
    organization_id = uuid4()

    assert get_temporary_organization_id(organization_id) == organization_id


def test_temporary_organization_dependency_metadata_uses_required_header() -> None:
    parameter_hint = get_type_hints(get_temporary_organization_id, include_extras=True)[
        "organization_id"
    ]
    header = get_args(parameter_hint)[1]
    dependency = get_args(TemporaryOrganizationId)[1]

    assert get_origin(parameter_hint) is Annotated
    assert get_args(parameter_hint)[0] is UUID
    assert isinstance(header, Header)
    assert header.alias == "X-Organization-ID"
    assert header.is_required()
    assert get_origin(TemporaryOrganizationId) is Annotated
    assert get_args(TemporaryOrganizationId)[0] is UUID
    assert isinstance(dependency, Depends)
    assert dependency.dependency is get_temporary_organization_id
    assert list(signature(get_temporary_organization_id).parameters) == ["organization_id"]
