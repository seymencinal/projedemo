from collections.abc import Iterator
from contextlib import suppress
from uuid import UUID

from fastapi import APIRouter, Response, UploadFile, status

from app.api.dependencies.research import (
    DatasourceServiceDependency,
    FileStorageDependency,
    ImportJobServiceDependency,
    UploadedFileServiceDependency,
)
from app.api.dependencies.tenant import TemporaryOrganizationId
from app.schemas.datasource import DatasourceRead, DatasourceUpdate
from app.schemas.import_job import ImportJobCreate, ImportJobRead, ImportJobTransition
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
