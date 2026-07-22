from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies.research import DatasourceServiceDependency, ImportJobServiceDependency
from app.api.dependencies.tenant import TemporaryOrganizationId
from app.schemas.datasource import DatasourceRead, DatasourceUpdate
from app.schemas.import_job import ImportJobCreate, ImportJobRead, ImportJobTransition

router = APIRouter(tags=["datasources"])


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
