from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.database import get_db_session
from app.services.organization import OrganizationService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_organization_service(session: DatabaseSession) -> OrganizationService:
    return OrganizationService(session)


OrganizationServiceDependency = Annotated[
    OrganizationService,
    Depends(get_organization_service),
]
