from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
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
from app.services.uploaded_file import UploadedFileService

ORGANIZATION_ID = uuid4()
DATASOURCE_ID = uuid4()
CHECKSUM = "a" * 64


def payload() -> UploadedFileCreate:
    return UploadedFileCreate(
        original_filename=" source.csv ",
        stored_filename=" source-id ",
        storage_path=" uploads/source-id ",
        content_type=" text/csv ",
        size_bytes=1,
        checksum_sha256=CHECKSUM,
    )


def item(status: UploadedFileStatus = UploadedFileStatus.PENDING) -> UploadedFile:
    value = UploadedFile(
        organization_id=ORGANIZATION_ID,
        datasource_id=DATASOURCE_ID,
        status=status,
        **payload().model_dump(),
    )
    value.id = uuid4()
    return value


def service() -> tuple[UploadedFileService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    repository = MagicMock(spec=UploadedFileRepository)
    datasources = MagicMock(spec=DatasourceRepository)
    return UploadedFileService(session, repository, datasources), session, repository, datasources


def test_schemas_normalize_and_validate_upload_metadata_and_status() -> None:
    created = payload()
    assert created.original_filename == "source.csv"
    assert created.content_type == "text/csv"
    for field, value in (
        ("original_filename", " "),
        ("checksum_sha256", "A" * 64),
        ("size_bytes", 0),
    ):
        values = payload().model_dump()
        values[field] = value
        with pytest.raises(ValidationError):
            UploadedFileCreate(**values)
    assert (
        UploadedFileStatusUpdate(
            status=UploadedFileStatus.FAILED, error_message=" failed "
        ).error_message
        == "failed"
    )
    for update in (UploadedFileStatusUpdate,):
        with pytest.raises(ValidationError):
            update(status=UploadedFileStatus.FAILED)
        with pytest.raises(ValidationError):
            update(status=UploadedFileStatus.READY, error_message="error")


@pytest.mark.asyncio
async def test_repository_queries_are_tenant_datasource_and_checksum_scoped() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = item()
    result.scalars.return_value.all.return_value = [item()]
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    repository = UploadedFileRepository(session)
    assert await repository.add(item())
    assert await repository.get(uuid4(), ORGANIZATION_ID)
    assert await repository.list(DATASOURCE_ID, ORGANIZATION_ID)
    assert await repository.find_by_checksum(DATASOURCE_ID, ORGANIZATION_ID, CHECKSUM)
    assert ORGANIZATION_ID in session.execute.await_args.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_service_create_is_tenant_scoped_and_checks_checksum_conflict() -> None:
    target, session, repository, datasources = service()
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    repository.find_by_checksum = AsyncMock(return_value=None)
    repository.add = AsyncMock(side_effect=lambda value: value)
    created = await target.create(DATASOURCE_ID, ORGANIZATION_ID, payload())
    assert created.status is UploadedFileStatus.PENDING
    session.commit.assert_awaited_once()
    repository.find_by_checksum.assert_awaited_once_with(DATASOURCE_ID, ORGANIZATION_ID, CHECKSUM)
    datasources.get = AsyncMock(return_value=None)
    with pytest.raises(DatasourceNotFoundError):
        await target.create(DATASOURCE_ID, ORGANIZATION_ID, payload())
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    repository.find_by_checksum = AsyncMock(return_value=item())
    with pytest.raises(UploadedFileConflictError):
        await target.create(DATASOURCE_ID, ORGANIZATION_ID, payload())


@pytest.mark.asyncio
async def test_service_get_list_and_lifecycle_transitions() -> None:
    target, _, repository, datasources = service()
    value = item()
    repository.get = AsyncMock(return_value=value)
    repository.list = AsyncMock(return_value=[value])
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    assert await target.get(value.id, ORGANIZATION_ID) is value
    assert await target.list(DATASOURCE_ID, ORGANIZATION_ID) == [value]
    assert (await target.mark_ready(value.id, ORGANIZATION_ID)).status is UploadedFileStatus.READY
    assert (
        await target.mark_deleted(value.id, ORGANIZATION_ID)
    ).status is UploadedFileStatus.DELETED
    repository.get = AsyncMock(return_value=None)
    with pytest.raises(UploadedFileNotFoundError):
        await target.get(uuid4(), ORGANIZATION_ID)
    datasources.get = AsyncMock(return_value=None)
    with pytest.raises(DatasourceNotFoundError):
        await target.list(DATASOURCE_ID, ORGANIZATION_ID)


@pytest.mark.asyncio
async def test_service_failed_and_invalid_transitions() -> None:
    target, _, repository, _ = service()
    value = item()
    repository.get = AsyncMock(return_value=value)
    assert (
        await target.mark_failed(value.id, ORGANIZATION_ID, " reason ")
    ).error_message == "reason"
    value.status = UploadedFileStatus.DELETED
    with pytest.raises(InvalidUploadedFileTransitionError):
        await target.mark_ready(value.id, ORGANIZATION_ID)
