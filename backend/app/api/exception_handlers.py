from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)
from app.exceptions.organization import OrganizationAlreadyExistsError, OrganizationNotFoundError
from app.exceptions.research import (
    DatasourceNotFoundError,
    IdempotencyConflictError,
    ImportJobNotFoundError,
    InvalidImportJobCountersError,
    InvalidImportJobTransitionError,
    ResearchNotFoundError,
)


async def company_not_found_exception_handler(
    request: Request,
    error: CompanyNotFoundError,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(error),
        },
    )


async def company_already_exists_exception_handler(
    request: Request,
    error: CompanyAlreadyExistsError,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(error),
        },
    )


async def organization_not_found_exception_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(error)},
    )


async def organization_already_exists_exception_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(error)},
    )


async def research_not_found_exception_handler(request: Request, error: Exception) -> JSONResponse:
    del request
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})


async def import_job_conflict_exception_handler(request: Request, error: Exception) -> JSONResponse:
    del request
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)})


async def import_job_counter_exception_handler(request: Request, error: Exception) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(error)}
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        CompanyNotFoundError,
        company_not_found_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(
        OrganizationNotFoundError,
        organization_not_found_exception_handler,
    )
    app.add_exception_handler(
        OrganizationAlreadyExistsError,
        organization_already_exists_exception_handler,
    )
    app.add_exception_handler(
        CompanyAlreadyExistsError,
        company_already_exists_exception_handler,  # type: ignore[arg-type]
    )
    app.add_exception_handler(ResearchNotFoundError, research_not_found_exception_handler)
    app.add_exception_handler(DatasourceNotFoundError, research_not_found_exception_handler)
    app.add_exception_handler(ImportJobNotFoundError, research_not_found_exception_handler)
    app.add_exception_handler(
        InvalidImportJobTransitionError, import_job_conflict_exception_handler
    )
    app.add_exception_handler(IdempotencyConflictError, import_job_conflict_exception_handler)
    app.add_exception_handler(InvalidImportJobCountersError, import_job_counter_exception_handler)
