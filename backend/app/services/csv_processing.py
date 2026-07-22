import csv
from collections.abc import Iterable
from io import TextIOWrapper
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from app.exceptions.csv_processing import (
    CsvColumnLimitExceededError,
    CsvFileNotProcessableError,
    CsvRowLimitExceededError,
    EmptyCsvFileError,
    MalformedCsvError,
    UnsupportedCsvFileError,
)
from app.exceptions.research import DatasourceNotFoundError
from app.exceptions.uploaded_file import UploadedFileNotFoundError
from app.models.uploaded_file import UploadedFileStatus
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.csv_processing import CsvSummaryRead
from app.storage.protocol import FileStorage


class CsvProcessingService:
    _content_types: ClassVar[set[str]] = {"text/csv", "application/csv", "application/octet-stream"}

    def __init__(
        self,
        repository: UploadedFileRepository,
        storage: FileStorage,
        max_rows: int,
        max_columns: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_rows = max_rows
        self._max_columns = max_columns

    async def summarize(
        self, organization_id: UUID, datasource_id: UUID, uploaded_file_id: UUID
    ) -> CsvSummaryRead:
        uploaded_file = await self._repository.get(uploaded_file_id, organization_id)
        if uploaded_file is None:
            raise UploadedFileNotFoundError(uploaded_file_id)
        if uploaded_file.datasource_id != datasource_id:
            raise DatasourceNotFoundError(datasource_id)
        if uploaded_file.status in {UploadedFileStatus.FAILED, UploadedFileStatus.DELETED}:
            raise CsvFileNotProcessableError()
        if (
            Path(uploaded_file.original_filename).suffix.lower() != ".csv"
            or uploaded_file.content_type not in self._content_types
        ):
            raise UnsupportedCsvFileError()
        try:
            with (
                self._storage.open(uploaded_file.storage_path) as binary_file,
                TextIOWrapper(binary_file, encoding="utf-8-sig", newline="") as text_file,
            ):
                reader = csv.reader(text_file, strict=True)
                return self._read_summary(reader, uploaded_file_id)
        except (CsvColumnLimitExceededError, CsvRowLimitExceededError, EmptyCsvFileError):
            raise
        except (csv.Error, UnicodeDecodeError) as error:
            raise MalformedCsvError() from error

    def _read_summary(self, reader: Iterable[list[str]], uploaded_file_id: UUID) -> CsvSummaryRead:
        header: list[str] | None = None
        row_count = 0
        for record in reader:
            if not any(value.strip() for value in record):
                continue
            if header is None:
                header = record
                if len(header) > self._max_columns:
                    raise CsvColumnLimitExceededError()
                continue
            if len(record) != len(header):
                raise MalformedCsvError()
            row_count += 1
            if row_count > self._max_rows:
                raise CsvRowLimitExceededError()
        if header is None:
            raise EmptyCsvFileError()
        return CsvSummaryRead(
            uploaded_file_id=uploaded_file_id,
            row_count=row_count,
            column_count=len(header),
            column_names=header,
        )
