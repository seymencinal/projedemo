from typing import cast

from sqlalchemy import Enum, Table, UniqueConstraint

from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User


def test_identity_models_are_registered_with_expected_table_names() -> None:
    assert Organization.__tablename__ == "organizations"
    assert User.__tablename__ == "users"
    assert Membership.__tablename__ == "memberships"


def test_membership_role_is_typed_and_persisted_as_an_enum() -> None:
    role = Membership.__table__.columns["role"]

    assert list(MembershipRole) == [
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        MembershipRole.MEMBER,
        MembershipRole.VIEWER,
    ]
    assert isinstance(role.type, Enum)
    assert role.type.enums == ["owner", "admin", "member", "viewer"]


def test_identity_models_enforce_expected_uniqueness() -> None:
    organization_constraints = [
        constraint
        for constraint in cast(Table, Organization.__table__).constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    user_constraints = [
        constraint
        for constraint in cast(Table, User.__table__).constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    membership_constraints = [
        constraint
        for constraint in cast(Table, Membership.__table__).constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert [column.name for column in organization_constraints[0].columns] == ["slug"]
    assert [column.name for column in user_constraints[0].columns] == ["email"]
    assert [column.name for column in membership_constraints[0].columns] == [
        "organization_id",
        "user_id",
    ]
