from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies.organization import OrganizationServiceDependency
from app.schemas.organization import OrganizationCreate, OrganizationRead

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    service: OrganizationServiceDependency,
) -> OrganizationRead:
    return OrganizationRead.model_validate(await service.create(payload))


@router.get("", response_model=list[OrganizationRead])
async def list_organizations(
    service: OrganizationServiceDependency,
) -> list[OrganizationRead]:
    return [OrganizationRead.model_validate(item) for item in await service.list()]


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(
    organization_id: UUID,
    service: OrganizationServiceDependency,
) -> OrganizationRead:
    return OrganizationRead.model_validate(await service.get_by_id(organization_id))
