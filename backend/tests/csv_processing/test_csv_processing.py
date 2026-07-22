from io import BytesIO
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.exceptions.csv_processing import (
    CsvColumnLimitExceededError,
    CsvFileNotProcessableError,
    CsvRowLimitExceededError,
    EmptyCsvFileError,
    MalformedCsvError,
    UnsupportedCsvFileError,
)
from app.exceptions.research import DatasourceNotFoundError
from app.exceptions.storage import StoredFileNotFoundError
from app.models.uploaded_file import UploadedFile, UploadedFileStatus
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.csv_processing import CsvSummaryRead
from app.services.csv_processing import CsvProcessingService
from app.storage.protocol import FileStorage

ORG = uuid4()
SOURCE = uuid4()
FILE_ID = uuid4()


class RepositoryFake:
    def __init__(self, value: UploadedFile | None) -> None:
        self.value = value
        self.calls: list[tuple[object, object]] = []

    async def get(self, item_id: object, organization_id: object) -> UploadedFile | None:
        self.calls.append((item_id, organization_id))
        return self.value


class StorageFake:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.paths: list[str] = []

    def open(self, storage_path: str) -> BytesIO:
        self.paths.append(storage_path)
        return BytesIO(self.content)


class StorageFailureFake:
    def open(self, storage_path: str) -> BytesIO:
        raise StoredFileNotFoundError(storage_path)


def uploaded_file(status: UploadedFileStatus = UploadedFileStatus.PENDING) -> UploadedFile:
    item = UploadedFile(
        organization_id=ORG,
        datasource_id=SOURCE,
        original_filename="source.CSV",
        stored_filename="internal.csv",
        storage_path="private.csv",
        content_type="text/csv",
        size_bytes=1,
        checksum_sha256="a" * 64,
        status=status,
    )
    item.id = FILE_ID
    return item


def service(
    content: bytes, *, rows: int = 10, columns: int = 10, item: UploadedFile | None = None
) -> CsvProcessingService:
    return CsvProcessingService(
        cast(UploadedFileRepository, RepositoryFake(item or uploaded_file())),
        cast(FileStorage, StorageFake(content)),
        rows,
        columns,
    )


def test_schema_and_settings_validate_limits() -> None:
    assert CsvSummaryRead(uploaded_file_id=FILE_ID, row_count=0, column_count=1, column_names=["a"])
    for row_count, column_count in ((-1, 1), (0, 0)):
        with pytest.raises(ValidationError):
            CsvSummaryRead(
                uploaded_file_id=FILE_ID,
                row_count=row_count,
                column_count=column_count,
                column_names=["a"],
            )
    with pytest.raises(ValidationError):
        Settings(max_csv_rows=0)
    with pytest.raises(ValidationError):
        Settings(max_csv_columns=0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_rows"),
    [(b"\xef\xbb\xbfa,b\n", 0), (b"\n\na,b\n1,2\n", 1), (b"a,b\n1,2\n\n3,4\n", 2)],
)
async def test_summarize_streams_csv_and_skips_empty_records(
    content: bytes, expected_rows: int
) -> None:
    result = await service(content).summarize(ORG, SOURCE, FILE_ID)
    assert result.row_count == expected_rows
    assert result.column_count == 2
    assert result.column_names == ["a", "b"]
    assert not hasattr(result, "storage_path")


@pytest.mark.asyncio
async def test_summarize_returns_only_public_summary_fields() -> None:
    result = await service(b"name,score\nAda,10\n").summarize(ORG, SOURCE, FILE_ID)

    assert set(result.model_dump()) == {
        "uploaded_file_id",
        "row_count",
        "column_count",
        "column_names",
    }


@pytest.mark.asyncio
async def test_summarize_rejects_invalid_content_and_limits() -> None:
    with pytest.raises(EmptyCsvFileError):
        await service(b"\n\n").summarize(ORG, SOURCE, FILE_ID)
    with pytest.raises(MalformedCsvError):
        await service(b'a,b\n"unterminated\n').summarize(ORG, SOURCE, FILE_ID)
    with pytest.raises(MalformedCsvError):
        await service(b"a,b\n1\n").summarize(ORG, SOURCE, FILE_ID)
    with pytest.raises(CsvRowLimitExceededError):
        await service(b"a\n1\n2\n", rows=1).summarize(ORG, SOURCE, FILE_ID)
    with pytest.raises(CsvColumnLimitExceededError):
        await service(b"a,b\n", columns=1).summarize(ORG, SOURCE, FILE_ID)


@pytest.mark.asyncio
async def test_summarize_enforces_tenant_datasource_status_and_csv_metadata() -> None:
    mismatch = uploaded_file()
    mismatch.datasource_id = uuid4()
    with pytest.raises(DatasourceNotFoundError):
        await service(b"a\n", item=mismatch).summarize(ORG, SOURCE, FILE_ID)
    for status in (UploadedFileStatus.FAILED, UploadedFileStatus.DELETED):
        with pytest.raises(CsvFileNotProcessableError):
            await service(b"a\n", item=uploaded_file(status)).summarize(ORG, SOURCE, FILE_ID)
    invalid = uploaded_file()
    invalid.original_filename = "source.xlsx"
    with pytest.raises(UnsupportedCsvFileError):
        await service(b"a\n", item=invalid).summarize(ORG, SOURCE, FILE_ID)


@pytest.mark.asyncio
async def test_summarize_propagates_storage_not_found_error() -> None:
    processor = CsvProcessingService(
        cast(UploadedFileRepository, RepositoryFake(uploaded_file())),
        cast(FileStorage, StorageFailureFake()),
        10,
        10,
    )

    with pytest.raises(StoredFileNotFoundError):
        await processor.summarize(ORG, SOURCE, FILE_ID)
    invalid = uploaded_file()
    invalid.content_type = "application/vnd.ms-excel"
    with pytest.raises(UnsupportedCsvFileError):
        await service(b"a\n", item=invalid).summarize(ORG, SOURCE, FILE_ID)
