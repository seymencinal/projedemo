from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.database import get_db_session
from app.services.company import CompanyService

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


def get_company_service(
    session: DatabaseSession,
) -> CompanyService:
    return CompanyService(session)


CompanyServiceDependency = Annotated[
    CompanyService,
    Depends(get_company_service),
]
