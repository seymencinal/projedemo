from typing import Annotated

from fastapi import Depends

from app.api.dependencies.company import DatabaseSession
from app.core.config import get_settings
from app.repositories.uploaded_file import UploadedFileRepository
from app.services.datasource import DatasourceService
from app.services.import_job import ImportJobService
from app.services.research import ResearchService
from app.services.uploaded_file import UploadedFileService
from app.storage.local import LocalFileStorage
from app.storage.protocol import FileStorage


def get_research_service(session: DatabaseSession) -> ResearchService:
    return ResearchService(session)


def get_datasource_service(session: DatabaseSession) -> DatasourceService:
    return DatasourceService(session)


def get_import_job_service(session: DatabaseSession) -> ImportJobService:
    return ImportJobService(session)


def get_file_storage() -> FileStorage:
    settings = get_settings()
    return LocalFileStorage(settings.upload_storage_root, settings.max_upload_size_bytes)


def get_uploaded_file_repository(session: DatabaseSession) -> UploadedFileRepository:
    return UploadedFileRepository(session)


def get_uploaded_file_service(session: DatabaseSession) -> UploadedFileService:
    return UploadedFileService(session)


ResearchServiceDependency = Annotated[ResearchService, Depends(get_research_service)]
DatasourceServiceDependency = Annotated[DatasourceService, Depends(get_datasource_service)]
ImportJobServiceDependency = Annotated[ImportJobService, Depends(get_import_job_service)]
FileStorageDependency = Annotated[FileStorage, Depends(get_file_storage)]
UploadedFileRepositoryDependency = Annotated[
    UploadedFileRepository, Depends(get_uploaded_file_repository)
]
UploadedFileServiceDependency = Annotated[UploadedFileService, Depends(get_uploaded_file_service)]
