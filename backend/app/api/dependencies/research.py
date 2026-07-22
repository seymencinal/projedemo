from typing import Annotated

from fastapi import Depends

from app.api.dependencies.company import DatabaseSession
from app.services.datasource import DatasourceService
from app.services.import_job import ImportJobService
from app.services.research import ResearchService


def get_research_service(session: DatabaseSession) -> ResearchService:
    return ResearchService(session)


def get_datasource_service(session: DatabaseSession) -> DatasourceService:
    return DatasourceService(session)


def get_import_job_service(session: DatabaseSession) -> ImportJobService:
    return ImportJobService(session)


ResearchServiceDependency = Annotated[ResearchService, Depends(get_research_service)]
DatasourceServiceDependency = Annotated[DatasourceService, Depends(get_datasource_service)]
ImportJobServiceDependency = Annotated[ImportJobService, Depends(get_import_job_service)]
