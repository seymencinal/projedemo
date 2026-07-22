from collections.abc import Iterable
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, UploadFile as FastAPIUploadFile
from fastapi.testclient import TestClient

from app.api.dependencies.research import get_file_storage, get_uploaded_file_service
from app.api.exception_handlers import register_exception_handlers
from app.api.routes.datasources import router, upload_file
from app.exceptions.research import DatasourceNotFoundError
from app.exceptions.storage import (
    ContentTypeMismatchError,
    EmptyUploadError,
    StorageWriteError,
    StoredFileNotFoundError,
    UnsafeStoragePathError,
    UnsupportedContentTypeError,
    UnsupportedFileExtensionError,
    UploadTooLargeError,
)
from app.exceptions.uploaded_file import UploadedFileConflictError
from app.models.uploaded_file import UploadedFileStatus
from app.services.uploaded_file import UploadedFileService
from app.storage.protocol import StoredFile

ORG = uuid4()
SOURCE = uuid4()


class UploadFileSpy:
    def __init__(self) -> None:
        self.filename: str | None = "source.csv"
        self.content_type: str | None = "text/csv"
        self.file = BytesIO(b"abc")
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def item() -> SimpleNamespace:
    now = datetime(2026, 7, 22, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        organization_id=ORG,
        datasource_id=SOURCE,
        original_filename="source.csv",
        stored_filename="internal.csv",
        storage_path="/private/internal.csv",
        content_type="text/csv",
        size_bytes=3,
        checksum_sha256="a" * 64,
        status=UploadedFileStatus.PENDING,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def client(
    storage: MagicMock | None = None, service: MagicMock | None = None
) -> tuple[TestClient, MagicMock, MagicMock]:
    storage = storage or MagicMock()
    storage.save.return_value = StoredFile("private.csv", "private.csv", 3, "a" * 64)
    service = service or MagicMock(spec=UploadedFileService)
    service.create = AsyncMock(return_value=item())
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_file_storage] = lambda: storage
    app.dependency_overrides[get_uploaded_file_service] = lambda: service
    return TestClient(app), storage, service


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("source.csv", "text/csv"), ("source.xlsx", "application/vnd.ms-excel")],
)
def test_upload_returns_public_metadata_only(filename: str, content_type: str) -> None:
    test_client, storage, service = client()
    chunks: list[bytes] = []

    def save(_: str, __: str, stream: Iterable[bytes]) -> StoredFile:
        chunks.extend(stream)
        return StoredFile("private.csv", "private.csv", 3, "a" * 64)

    storage.save.side_effect = save
    response = test_client.post(
        f"/datasources/{SOURCE}/files",
        headers={"X-Organization-ID": str(ORG)},
        files={"file": (filename, b"abc", content_type)},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert "storage_path" not in response.json() and "stored_filename" not in response.json()
    assert service.create.await_args.args[:2] == (SOURCE, ORG)
    assert chunks == [b"abc"]


@pytest.mark.parametrize(
    "error",
    [
        UnsupportedFileExtensionError(),
        UnsupportedContentTypeError(),
        ContentTypeMismatchError(),
        EmptyUploadError(),
        UploadTooLargeError(),
        UnsafeStoragePathError(),
        StorageWriteError(),
        StoredFileNotFoundError(),
    ],
)
def test_upload_maps_storage_errors(error: Exception) -> None:
    test_client, storage, service = client()
    storage.save.side_effect = error
    response = test_client.post(
        f"/datasources/{SOURCE}/files",
        headers={"X-Organization-ID": str(ORG)},
        files={"file": ("source.csv", b"abc", "text/csv")},
    )
    assert response.status_code in {400, 404, 413, 415, 422, 500}
    service.create.assert_not_awaited()


def test_upload_validation_and_compensation() -> None:
    test_client, storage, service = client()
    assert (
        test_client.post(
            f"/datasources/{SOURCE}/files", headers={"X-Organization-ID": str(ORG)}
        ).status_code
        == 422
    )
    assert (
        test_client.post(
            "/datasources/not-a-uuid/files",
            headers={"X-Organization-ID": str(ORG)},
            files={"file": ("x.csv", b"x", "text/csv")},
        ).status_code
        == 422
    )
    assert (
        test_client.post(
            f"/datasources/{SOURCE}/files", files={"file": ("x.csv", b"x", "text/csv")}
        ).status_code
        == 422
    )
    service.create.side_effect = DatasourceNotFoundError(SOURCE)
    response = test_client.post(
        f"/datasources/{SOURCE}/files",
        headers={"X-Organization-ID": str(ORG)},
        files={"file": ("x.csv", b"x", "text/csv")},
    )
    assert response.status_code == 404
    storage.delete.assert_called_once_with("private.csv")
    service.create.side_effect = UploadedFileConflictError("a" * 64)


@pytest.mark.parametrize(
    ("filename", "content_type", "error", "status_code"),
    [
        (" ", "text/csv", UnsafeStoragePathError(), 400),
        ("../source.csv", "text/csv", UnsafeStoragePathError(), 400),
        ("source.txt", "text/csv", UnsupportedFileExtensionError(), 415),
        ("source.csv", "image/png", UnsupportedContentTypeError(), 415),
        ("source.csv", "application/vnd.ms-excel", ContentTypeMismatchError(), 415),
        ("source.csv", "text/csv", EmptyUploadError(), 422),
        ("source.csv", "text/csv", UploadTooLargeError(), 413),
    ],
)
def test_upload_validation_errors_are_mapped(
    filename: str, content_type: str, error: Exception, status_code: int
) -> None:
    test_client, storage, _ = client()
    storage.save.side_effect = error
    response = test_client.post(
        f"/datasources/{SOURCE}/files",
        headers={"X-Organization-ID": str(ORG)},
        files={"file": (filename, b"abc", content_type)},
    )
    assert response.status_code == status_code


def test_upload_maps_checksum_conflict_and_cleanup_failure_preserves_original() -> None:
    test_client, storage, service = client()
    service.create.side_effect = UploadedFileConflictError("a" * 64)
    storage.delete.side_effect = StorageWriteError()
    response = test_client.post(
        f"/datasources/{SOURCE}/files",
        headers={"X-Organization-ID": str(ORG)},
        files={"file": ("source.csv", b"abc", "text/csv")},
    )
    assert response.status_code == 409
    storage.delete.assert_called_once_with("private.csv")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, StorageWriteError(), DatasourceNotFoundError(SOURCE)])
async def test_upload_file_closes_upload_on_success_and_failures(failure: Exception | None) -> None:
    upload = UploadFileSpy()
    storage = MagicMock()
    storage.save.return_value = StoredFile("private.csv", "private.csv", 3, "a" * 64)
    service = MagicMock(spec=UploadedFileService)
    service.create = AsyncMock(return_value=item())
    if isinstance(failure, StorageWriteError):
        storage.save.side_effect = failure
    if failure is not None and not isinstance(failure, StorageWriteError):
        service.create.side_effect = failure
    if failure is None:
        await upload_file(SOURCE, cast(FastAPIUploadFile, upload), service, storage, ORG)
    else:
        with pytest.raises((StorageWriteError, DatasourceNotFoundError)):
            await upload_file(SOURCE, cast(FastAPIUploadFile, upload), service, storage, ORG)
    assert upload.closed is True
