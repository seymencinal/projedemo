from uuid import uuid4

import pytest

from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)


def test_company_not_found_error_is_exception() -> None:
    assert issubclass(CompanyNotFoundError, Exception)


def test_company_not_found_error_stores_company_id() -> None:
    company_id = uuid4()
    error = CompanyNotFoundError(company_id)

    assert error.company_id == company_id
    assert error.args == (f"Company with id '{company_id}' was not found.",)
    assert str(error) == f"Company with id '{company_id}' was not found."


def test_company_not_found_error_can_be_raised() -> None:
    company_id = uuid4()

    with pytest.raises(CompanyNotFoundError) as exc_info:
        raise CompanyNotFoundError(company_id)

    assert exc_info.value.company_id == company_id


def test_company_already_exists_error_is_exception() -> None:
    assert issubclass(CompanyAlreadyExistsError, Exception)


def test_company_already_exists_error_stores_identifiers() -> None:
    error = CompanyAlreadyExistsError(
        exchange="NASDAQ",
        ticker="EXM",
    )

    assert error.exchange == "NASDAQ"
    assert error.ticker == "EXM"
    assert error.args == ("Company with exchange 'NASDAQ' and ticker 'EXM' already exists.",)
    assert str(error) == "Company with exchange 'NASDAQ' and ticker 'EXM' already exists."


def test_company_already_exists_error_can_be_raised() -> None:
    with pytest.raises(CompanyAlreadyExistsError) as exc_info:
        raise CompanyAlreadyExistsError(
            exchange="NYSE",
            ticker="TEST",
        )

    assert exc_info.value.exchange == "NYSE"
    assert exc_info.value.ticker == "TEST"


def test_company_already_exists_error_preserves_values() -> None:
    error = CompanyAlreadyExistsError(
        exchange=" nasdaq ",
        ticker="exm",
    )

    assert error.exchange == " nasdaq "
    assert error.ticker == "exm"
    assert str(error) == "Company with exchange ' nasdaq ' and ticker 'exm' already exists."
