from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.uploaded_file import UploadedFile


class UploadedFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: UploadedFile) -> UploadedFile:
        self._session.add(item)
        await self._session.flush()
        return item

    async def get(self, item_id: UUID, organization_id: UUID) -> UploadedFile | None:
        result = await self._session.execute(
            select(UploadedFile).where(
                UploadedFile.id == item_id, UploadedFile.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list(self, datasource_id: UUID, organization_id: UUID) -> list[UploadedFile]:
        result = await self._session.execute(
            select(UploadedFile)
            .where(
                UploadedFile.datasource_id == datasource_id,
                UploadedFile.organization_id == organization_id,
            )
            .order_by(UploadedFile.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_checksum(
        self, datasource_id: UUID, organization_id: UUID, checksum_sha256: str
    ) -> UploadedFile | None:
        result = await self._session.execute(
            select(UploadedFile).where(
                UploadedFile.datasource_id == datasource_id,
                UploadedFile.organization_id == organization_id,
                UploadedFile.checksum_sha256 == checksum_sha256,
            )
        )
        return result.scalar_one_or_none()
