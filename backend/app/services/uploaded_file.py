from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.research import DatasourceNotFoundError
from app.exceptions.uploaded_file import (
    InvalidUploadedFileTransitionError,
    UploadedFileConflictError,
    UploadedFileNotFoundError,
)
from app.models.uploaded_file import UploadedFile, UploadedFileStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.uploaded_file import UploadedFileCreate, UploadedFileStatusUpdate


class UploadedFileService:
    def __init__(
        self,
        session: AsyncSession,
        repository: UploadedFileRepository | None = None,
        datasource_repository: DatasourceRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or UploadedFileRepository(session)
        self._datasource_repository = datasource_repository or DatasourceRepository(session)

    async def get(self, item_id: UUID, organization_id: UUID) -> UploadedFile:
        item = await self._repository.get(item_id, organization_id)
        if item is None:
            raise UploadedFileNotFoundError(item_id)
        return item

    async def list(self, datasource_id: UUID, organization_id: UUID) -> list[UploadedFile]:
        if await self._datasource_repository.get(datasource_id, organization_id) is None:
            raise DatasourceNotFoundError(datasource_id)
        return await self._repository.list(datasource_id, organization_id)

    async def create(
        self, datasource_id: UUID, organization_id: UUID, payload: UploadedFileCreate
    ) -> UploadedFile:
        if await self._datasource_repository.get(datasource_id, organization_id) is None:
            raise DatasourceNotFoundError(datasource_id)
        if await self._repository.find_by_checksum(
            datasource_id, organization_id, payload.checksum_sha256
        ):
            raise UploadedFileConflictError(payload.checksum_sha256)
        item = await self._repository.add(
            UploadedFile(
                organization_id=organization_id,
                datasource_id=datasource_id,
                status=UploadedFileStatus.PENDING,
                **payload.model_dump(),
            )
        )
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def mark_ready(self, item_id: UUID, organization_id: UUID) -> UploadedFile:
        return await self._transition(
            item_id, organization_id, UploadedFileStatusUpdate(status=UploadedFileStatus.READY)
        )

    async def mark_failed(
        self, item_id: UUID, organization_id: UUID, error_message: str
    ) -> UploadedFile:
        return await self._transition(
            item_id,
            organization_id,
            UploadedFileStatusUpdate(status=UploadedFileStatus.FAILED, error_message=error_message),
        )

    async def mark_deleted(self, item_id: UUID, organization_id: UUID) -> UploadedFile:
        return await self._transition(
            item_id, organization_id, UploadedFileStatusUpdate(status=UploadedFileStatus.DELETED)
        )

    async def _transition(
        self, item_id: UUID, organization_id: UUID, payload: UploadedFileStatusUpdate
    ) -> UploadedFile:
        item = await self.get(item_id, organization_id)
        allowed = {
            UploadedFileStatus.PENDING: {UploadedFileStatus.READY, UploadedFileStatus.FAILED},
            UploadedFileStatus.READY: {UploadedFileStatus.DELETED},
            UploadedFileStatus.FAILED: {UploadedFileStatus.DELETED},
        }
        if payload.status not in allowed.get(item.status, set()):
            raise InvalidUploadedFileTransitionError()
        item.status = payload.status
        item.error_message = payload.error_message
        await self._session.commit()
        await self._session.refresh(item)
        return item
