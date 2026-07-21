from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.membership import MembershipRole
from app.schemas.membership import MembershipRead
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.schemas.user import UserCreate, UserRead


def test_organization_slug_is_normalized_and_validated() -> None:
    organization = OrganizationCreate(name="Example", slug="  Example-Org  ")

    assert organization.slug == "example-org"
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Example", slug="invalid slug")
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Example", slug=cast(str, 123))


def test_user_email_is_normalized() -> None:
    user = UserCreate(email="  USER@EXAMPLE.COM ", display_name="Example User")

    assert str(user.email) == "user@example.com"
    with pytest.raises(ValidationError):
        UserCreate(email=cast(str, 123), display_name="Example User")


def test_identity_read_schemas_support_attribute_sources() -> None:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    organization_id = uuid4()
    user_id = uuid4()
    membership_id = uuid4()
    organization = OrganizationRead.model_validate(
        SimpleNamespace(
            id=organization_id,
            name="Example",
            slug="example",
            created_at=now,
            updated_at=now,
        )
    )
    user = UserRead.model_validate(
        SimpleNamespace(
            id=user_id,
            email="user@example.com",
            display_name="Example User",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    membership = MembershipRead.model_validate(
        SimpleNamespace(
            id=membership_id,
            organization_id=organization_id,
            user_id=user_id,
            role=MembershipRole.OWNER,
            created_at=now,
            updated_at=now,
        )
    )

    assert organization.id == organization_id
    assert user.email == "user@example.com"
    assert membership.role is MembershipRole.OWNER
