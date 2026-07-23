from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.exceptions.company import (
    CompanyAlreadyExistsError,
    CompanyNotFoundError,
)
from app.exceptions.csv_mapping import (
    BlankSourceColumnError,
    DuplicateSourceColumnError,
    MissingRequiredCanonicalFieldError,
    UnknownCanonicalFieldError,
)
from app.exceptions.csv_processing import (
    CsvColumnLimitExceededError,
    CsvFileNotProcessableError,
    CsvRowLimitExceededError,
    EmptyCsvFileError,
    MalformedCsvError,
    UnsupportedCsvFileError,
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
from app.exceptions.storage import (
    ContentTypeMismatchError,
    EmptyUploadError,
    StorageWriteError,
    StoredFileNotFoundError,
    UnsafeStoragePathError,
    UnsupportedContentTypeError,
    UnsupportedFileExtensionError,
    UploadTooLargeError,
)
from app.exceptions.uploaded_file import (
    InvalidUploadedFileTransitionError,
    UploadedFileConflictError,
    UploadedFileNotFoundError,
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


async def storage_exception_handler(request: Request, error: Exception) -> JSONResponse:
    del request
    codes = {
        UnsupportedFileExtensionError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        UnsupportedContentTypeError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        ContentTypeMismatchError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        EmptyUploadError: status.HTTP_422_UNPROCESSABLE_CONTENT,
        UploadTooLargeError: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        UnsafeStoragePathError: status.HTTP_400_BAD_REQUEST,
        StorageWriteError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        StoredFileNotFoundError: status.HTTP_404_NOT_FOUND,
    }
    return JSONResponse(status_code=codes[type(error)], content={"detail": "Upload failed."})


async def csv_processing_exception_handler(request: Request, error: Exception) -> JSONResponse:
    del request
    status_code = (
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        if isinstance(error, UnsupportedCsvFileError)
        else status.HTTP_409_CONFLICT
        if isinstance(error, CsvFileNotProcessableError)
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return JSONResponse(status_code=status_code, content={"detail": "CSV processing failed."})


async def csv_mapping_exception_handler(request: Request, error: Exception) -> JSONResponse:
    del request, error
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "CSV mapping is invalid."},
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
    app.add_exception_handler(UploadedFileNotFoundError, research_not_found_exception_handler)
    app.add_exception_handler(
        InvalidImportJobTransitionError, import_job_conflict_exception_handler
    )
    app.add_exception_handler(IdempotencyConflictError, import_job_conflict_exception_handler)
    app.add_exception_handler(UploadedFileConflictError, import_job_conflict_exception_handler)
    app.add_exception_handler(
        InvalidUploadedFileTransitionError, import_job_conflict_exception_handler
    )
    app.add_exception_handler(InvalidImportJobCountersError, import_job_counter_exception_handler)
    for storage_error_type in (
        UnsupportedFileExtensionError,
        UnsupportedContentTypeError,
        ContentTypeMismatchError,
        EmptyUploadError,
        UploadTooLargeError,
        UnsafeStoragePathError,
        StorageWriteError,
        StoredFileNotFoundError,
    ):
        app.add_exception_handler(storage_error_type, storage_exception_handler)
    for csv_error_type in (
        UnsupportedCsvFileError,
        EmptyCsvFileError,
        MalformedCsvError,
        CsvRowLimitExceededError,
        CsvColumnLimitExceededError,
        CsvFileNotProcessableError,
    ):
        app.add_exception_handler(csv_error_type, csv_processing_exception_handler)
    for csv_mapping_error_type in (
        UnknownCanonicalFieldError,
        MissingRequiredCanonicalFieldError,
        DuplicateSourceColumnError,
        BlankSourceColumnError,
    ):
        app.add_exception_handler(csv_mapping_error_type, csv_mapping_exception_handler)
