from typing import cast
from uuid import uuid4

from sqlalchemy import Boolean, String, Table, Text, UniqueConstraint

from app.db.base import Base
from app.models.company import Company


def test_company_table_is_registered() -> None:
    assert Company.__tablename__ == "companies"
    assert "companies" in Base.metadata.tables
    assert Base.metadata.tables["companies"] is Company.__table__


def test_company_defines_expected_columns() -> None:
    assert set(Company.__table__.columns.keys()) == {
        "id",
        "organization_id",
        "name",
        "ticker",
        "exchange",
        "isin",
        "website",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    }


def test_company_required_string_columns() -> None:
    name = Company.__table__.columns["name"]
    ticker = Company.__table__.columns["ticker"]
    exchange = Company.__table__.columns["exchange"]

    assert isinstance(name.type, String)
    assert name.type.length == 255
    assert name.nullable is False
    assert isinstance(ticker.type, String)
    assert ticker.type.length == 32
    assert ticker.nullable is False
    assert isinstance(exchange.type, String)
    assert exchange.type.length == 32
    assert exchange.nullable is False


def test_company_optional_columns() -> None:
    isin = Company.__table__.columns["isin"]
    website = Company.__table__.columns["website"]
    description = Company.__table__.columns["description"]

    assert isinstance(isin.type, String)
    assert isin.type.length == 12
    assert isin.nullable is True
    assert isinstance(website.type, String)
    assert website.type.length == 2048
    assert website.nullable is True
    assert isinstance(description.type, Text)
    assert description.nullable is True


def test_company_is_active_configuration() -> None:
    is_active = Company.__table__.columns["is_active"]

    assert isinstance(is_active.type, Boolean)
    assert is_active.nullable is False
    assert is_active.default is not None
    assert is_active.server_default is not None


def test_company_inherits_common_columns() -> None:
    assert Company.__table__.columns["id"].primary_key is True
    assert Company.__table__.columns["created_at"].nullable is False
    assert Company.__table__.columns["updated_at"].nullable is False


def test_company_has_organization_exchange_ticker_unique_constraint() -> None:
    table = cast(Table, Company.__table__)
    unique_constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns]
        == ["organization_id", "exchange", "ticker"]
    )

    assert unique_constraint.name == "uq_companies_organization_id"


def test_company_has_isin_unique_constraint() -> None:
    table = cast(Table, Company.__table__)
    unique_constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["isin"]
    )

    assert unique_constraint.name == "uq_companies_isin"


def test_company_has_name_index() -> None:
    table = cast(Table, Company.__table__)
    index = next(
        index for index in table.indexes if [column.name for column in index.columns] == ["name"]
    )

    assert index.name == "ix_companies_name"
    assert index.unique is False


def test_company_can_be_instantiated_without_database() -> None:
    company = Company(
        organization_id=uuid4(),
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
