from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies.research import DatasourceServiceDependency, ResearchServiceDependency
from app.api.dependencies.tenant import TemporaryOrganizationId
from app.schemas.datasource import DatasourceCreate, DatasourceRead
from app.schemas.research import ResearchCreate, ResearchRead, ResearchUpdate

router = APIRouter(prefix="/researches", tags=["researches"])


@router.post("", response_model=ResearchRead, status_code=status.HTTP_201_CREATED)
async def create_research(
    payload: ResearchCreate,
    service: ResearchServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> ResearchRead:
    return ResearchRead.model_validate(await service.create(organization_id, payload))


@router.get("", response_model=list[ResearchRead])
async def list_researches(
    service: ResearchServiceDependency, organization_id: TemporaryOrganizationId
) -> list[ResearchRead]:
    return [ResearchRead.model_validate(item) for item in await service.list(organization_id)]


@router.get("/{research_id}", response_model=ResearchRead)
async def get_research(
    research_id: UUID, service: ResearchServiceDependency, organization_id: TemporaryOrganizationId
) -> ResearchRead:
    return ResearchRead.model_validate(await service.get(research_id, organization_id))


@router.patch("/{research_id}", response_model=ResearchRead)
async def update_research(
    research_id: UUID,
    payload: ResearchUpdate,
    service: ResearchServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> ResearchRead:
    return ResearchRead.model_validate(await service.update(research_id, organization_id, payload))


@router.delete("/{research_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_research(
    research_id: UUID, service: ResearchServiceDependency, organization_id: TemporaryOrganizationId
) -> Response:
    await service.delete(research_id, organization_id)
    return Response(status_code=204)


@router.post(
    "/{research_id}/datasources", response_model=DatasourceRead, status_code=status.HTTP_201_CREATED
)
async def create_datasource(
    research_id: UUID,
    payload: DatasourceCreate,
    service: DatasourceServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> DatasourceRead:
    return DatasourceRead.model_validate(
        await service.create(research_id, organization_id, payload)
    )


@router.get("/{research_id}/datasources", response_model=list[DatasourceRead])
async def list_datasources(
    research_id: UUID,
    service: DatasourceServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> list[DatasourceRead]:
    return [
        DatasourceRead.model_validate(item)
        for item in await service.list(research_id, organization_id)
    ]
