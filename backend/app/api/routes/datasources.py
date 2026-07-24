from collections.abc import Iterator
from contextlib import suppress
from uuid import UUID

from fastapi import APIRouter, Query, Response, UploadFile, status

from app.api.dependencies.research import (
    CsvImportExecutionServiceDependency,
    CsvProcessingServiceDependency,
    DatasourceServiceDependency,
    FileStorageDependency,
    ImportJobServiceDependency,
    ImportValidationIssueServiceDependency,
    MappingPreparationServiceDependency,
    UploadedFileServiceDependency,
)
from app.api.dependencies.tenant import TemporaryOrganizationId
from app.schemas.csv_mapping import CsvImportMappingAcceptedRead, CsvImportMappingRequest
from app.schemas.csv_processing import CsvSummaryRead
from app.schemas.datasource import DatasourceRead, DatasourceUpdate
from app.schemas.import_job import ImportJobCreate, ImportJobRead, ImportJobTransition
from app.schemas.import_validation_issue import ImportValidationIssuePage
from app.schemas.uploaded_file import UploadedFileCreate, UploadedFileRead

router = APIRouter(tags=["datasources"])


def upload_chunks(upload: UploadFile) -> Iterator[bytes]:
    while chunk := upload.file.read(64 * 1024):
        yield chunk


@router.get("/datasources/{datasource_id}", response_model=DatasourceRead)
async def get_datasource(
    datasource_id: UUID,
    service: DatasourceServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> DatasourceRead:
    return DatasourceRead.model_validate(await service.get(datasource_id, organization_id))


@router.patch("/datasources/{datasource_id}", response_model=DatasourceRead)
async def update_datasource(
    datasource_id: UUID,
    payload: DatasourceUpdate,
    service: DatasourceServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> DatasourceRead:
    return DatasourceRead.model_validate(
        await service.update(datasource_id, organization_id, payload)
    )


@router.delete("/datasources/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    datasource_id: UUID,
    service: DatasourceServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> Response:
    await service.delete(datasource_id, organization_id)
    return Response(status_code=204)


@router.post(
    "/datasources/{datasource_id}/import-jobs",
    response_model=ImportJobRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_import_job(
    datasource_id: UUID,
    payload: ImportJobCreate,
    service: ImportJobServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> ImportJobRead:
    return ImportJobRead.model_validate(
        await service.create(datasource_id, organization_id, payload)
    )


@router.post(
    "/datasources/{datasource_id}/files",
    response_model=UploadedFileRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    datasource_id: UUID,
    file: UploadFile,
    service: UploadedFileServiceDependency,
    storage: FileStorageDependency,
    organization_id: TemporaryOrganizationId,
) -> UploadedFileRead:
    try:
        stored = storage.save(file.filename or "", file.content_type or "", upload_chunks(file))
        try:
            item = await service.create(
                datasource_id,
                organization_id,
                UploadedFileCreate(
                    original_filename=file.filename or "",
                    stored_filename=stored.stored_filename,
                    storage_path=stored.storage_path,
                    content_type=file.content_type or "",
                    size_bytes=stored.size_bytes,
                    checksum_sha256=stored.checksum_sha256,
                ),
            )
        except Exception:
            with suppress(Exception):
                storage.delete(stored.storage_path)
            raise
        return UploadedFileRead.model_validate(item)
    finally:
        await file.close()


@router.post(
    "/datasources/{datasource_id}/files/{uploaded_file_id}/imports",
    response_model=CsvImportMappingAcceptedRead,
    status_code=status.HTTP_201_CREATED,
)
async def prepare_csv_import(
    datasource_id: UUID,
    uploaded_file_id: UUID,
    payload: CsvImportMappingRequest,
    service: MappingPreparationServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> CsvImportMappingAcceptedRead:
    return await service.prepare(datasource_id, uploaded_file_id, organization_id, payload)


@router.post(
    "/datasources/{datasource_id}/import-jobs/{import_job_id}/execute",
    response_model=ImportJobRead,
)
async def execute_csv_import(
    datasource_id: UUID,
    import_job_id: UUID,
    service: CsvImportExecutionServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> ImportJobRead:
    return ImportJobRead.model_validate(
        await service.execute(import_job_id, organization_id, datasource_id)
    )


@router.get(
    "/datasources/{datasource_id}/import-jobs/{import_job_id}/validation-issues",
    response_model=ImportValidationIssuePage,
)
async def list_import_validation_issues(
    datasource_id: UUID,
    import_job_id: UUID,
    service: ImportValidationIssueServiceDependency,
    organization_id: TemporaryOrganizationId,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> ImportValidationIssuePage:
    return await service.list_for_import_job(
        organization_id,
        datasource_id,
        import_job_id,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/datasources/{datasource_id}/files/{uploaded_file_id}/csv-summary",
    response_model=CsvSummaryRead,
)
async def summarize_csv(
    datasource_id: UUID,
    uploaded_file_id: UUID,
    service: CsvProcessingServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> CsvSummaryRead:
    return await service.summarize(organization_id, datasource_id, uploaded_file_id)


@router.get("/datasources/{datasource_id}/import-jobs", response_model=list[ImportJobRead])
async def list_import_jobs(
    datasource_id: UUID,
    service: ImportJobServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> list[ImportJobRead]:
    return [
        ImportJobRead.model_validate(item)
        for item in await service.list(datasource_id, organization_id)
    ]


@router.get("/import-jobs/{import_job_id}", response_model=ImportJobRead)
async def get_import_job(
    import_job_id: UUID,
    service: ImportJobServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> ImportJobRead:
    return ImportJobRead.model_validate(await service.get(import_job_id, organization_id))


@router.patch("/import-jobs/{import_job_id}/status", response_model=ImportJobRead)
async def transition_import_job(
    import_job_id: UUID,
    payload: ImportJobTransition,
    service: ImportJobServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> ImportJobRead:
    return ImportJobRead.model_validate(
        await service.transition(import_job_id, organization_id, payload)
    )
