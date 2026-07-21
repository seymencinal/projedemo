from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies.company import CompanyServiceDependency
from app.api.dependencies.tenant import TemporaryOrganizationId
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    payload: CompanyCreate,
    service: CompanyServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> CompanyRead:
    company = await service.create(organization_id, payload)

    return CompanyRead.model_validate(company)


@router.get(
    "",
    response_model=list[CompanyRead],
)
async def list_companies(
    service: CompanyServiceDependency,
    organization_id: TemporaryOrganizationId,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[CompanyRead]:
    companies = await service.list(
        organization_id,
        offset=offset,
        limit=limit,
    )

    return [CompanyRead.model_validate(company) for company in companies]


@router.get(
    "/{company_id}",
    response_model=CompanyRead,
)
async def get_company(
    company_id: UUID,
    service: CompanyServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> CompanyRead:
    company = await service.get_by_id(company_id, organization_id)

    return CompanyRead.model_validate(company)


@router.patch(
    "/{company_id}",
    response_model=CompanyRead,
)
async def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    service: CompanyServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> CompanyRead:
    company = await service.update(
        company_id,
        organization_id,
        payload,
    )

    return CompanyRead.model_validate(company)


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_company(
    company_id: UUID,
    service: CompanyServiceDependency,
    organization_id: TemporaryOrganizationId,
) -> Response:
    await service.delete(company_id, organization_id)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
