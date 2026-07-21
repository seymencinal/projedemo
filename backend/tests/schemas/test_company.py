from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.company import (
    CompanyBase,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
)


def test_company_base_accepts_valid_data() -> None:
    company = CompanyBase(
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
    )

    assert company.name == "Example Company"
    assert company.ticker == "EXM"
    assert company.exchange == "NASDAQ"
    assert company.isin is None
    assert company.website is None
    assert company.description is None
    assert company.is_active is True


def test_company_create_inherits_company_base_fields() -> None:
    company = CompanyCreate(
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
        isin="US1234567890",
        website="https://example.com",
        description="Example description",
        is_active=False,
    )

    assert company.name == "Example Company"
    assert company.ticker == "EXM"
    assert company.exchange == "NASDAQ"
    assert company.isin == "US1234567890"
    assert company.website == "https://example.com"
    assert company.description == "Example description"
    assert company.is_active is False


@pytest.mark.parametrize(
    "missing_field",
    [
        "name",
        "ticker",
        "exchange",
    ],
)
def test_company_create_requires_core_fields(missing_field: str) -> None:
    data = {
        "name": "Example Company",
        "ticker": "EXM",
        "exchange": "NASDAQ",
    }
    data.pop(missing_field)

    with pytest.raises(ValidationError):
        CompanyCreate.model_validate(data)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("name", ""),
        ("name", "x" * 256),
        ("ticker", ""),
        ("ticker", "x" * 33),
        ("exchange", ""),
        ("exchange", "x" * 33),
        ("isin", "x" * 11),
        ("isin", "x" * 13),
        ("website", "x" * 2049),
    ],
)
def test_company_create_rejects_invalid_string_lengths(
    field_name: str,
    field_value: str,
) -> None:
    data = {
        "name": "Example Company",
        "ticker": "EXM",
        "exchange": "NASDAQ",
    }
    data[field_name] = field_value

    with pytest.raises(ValidationError):
        CompanyCreate.model_validate(data)


def test_company_create_accepts_twelve_character_isin() -> None:
    company = CompanyCreate(
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
        isin="US1234567890",
    )

    assert company.isin == "US1234567890"


def test_company_create_preserves_input_values() -> None:
    company = CompanyCreate(
        name="  Example Company  ",
        ticker="exm",
        exchange="nasdaq",
    )

    assert company.name == "  Example Company  "
    assert company.ticker == "exm"
    assert company.exchange == "nasdaq"


def test_company_update_accepts_empty_payload() -> None:
    update = CompanyUpdate()

    assert update.model_dump() == {
        "name": None,
        "ticker": None,
        "exchange": None,
        "isin": None,
        "website": None,
        "description": None,
        "is_active": None,
    }
    assert update.model_fields_set == set()


def test_company_update_tracks_provided_fields() -> None:
    update = CompanyUpdate(
        name="Updated Company",
        is_active=False,
    )

    assert update.name == "Updated Company"
    assert update.is_active is False
    assert update.model_fields_set == {
        "name",
        "is_active",
    }


def test_company_update_tracks_explicit_null() -> None:
    update = CompanyUpdate(description=None)

    assert update.description is None
    assert update.model_fields_set == {"description"}


def test_company_read_accepts_dictionary_data() -> None:
    company_id = uuid4()
    created_at = datetime(2026, 1, 1, 10, 30, tzinfo=UTC)
    updated_at = datetime(2026, 1, 2, 11, 45, tzinfo=UTC)
    company = CompanyRead(
        id=company_id,
        organization_id=uuid4(),
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
        isin=None,
        website=None,
        description=None,
        is_active=True,
        created_at=created_at,
        updated_at=updated_at,
    )

    assert company.id == company_id
    assert company.name == "Example Company"
    assert company.ticker == "EXM"
    assert company.exchange == "NASDAQ"
    assert company.isin is None
    assert company.website is None
    assert company.description is None
    assert company.is_active is True
    assert company.created_at == created_at
    assert company.updated_at == updated_at


def test_company_read_supports_attribute_based_validation() -> None:
    source = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        name="Example Company",
        ticker="EXM",
        exchange="NASDAQ",
        isin=None,
        website=None,
        description=None,
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    company = CompanyRead.model_validate(source)

    assert company.id == source.id
    assert company.name == source.name
    assert company.ticker == source.ticker
    assert company.exchange == source.exchange
    assert company.isin == source.isin
    assert company.website == source.website
    assert company.description == source.description
    assert company.is_active is source.is_active
    assert company.created_at == source.created_at
    assert company.updated_at == source.updated_at


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "created_at",
        "updated_at",
    ],
)
def test_company_read_requires_system_fields(missing_field: str) -> None:
    data: dict[str, object] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "name": "Example Company",
        "ticker": "EXM",
        "exchange": "NASDAQ",
        "isin": None,
        "website": None,
        "description": None,
        "is_active": True,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    data.pop(missing_field)

    with pytest.raises(ValidationError):
        CompanyRead.model_validate(data)
