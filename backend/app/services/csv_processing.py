import csv
from collections.abc import Iterable
from uuid import UUID

from app.exceptions.csv_processing import (
    CsvColumnLimitExceededError,
    CsvRowLimitExceededError,
    EmptyCsvFileError,
    MalformedCsvError,
)
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.csv_processing import CsvSummaryRead
from app.services.csv_file_access import CsvFileAccessService
from app.storage.protocol import FileStorage


class CsvProcessingService:
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
        self._file_access = CsvFileAccessService(repository, storage)

    async def summarize(
        self, organization_id: UUID, datasource_id: UUID, uploaded_file_id: UUID
    ) -> CsvSummaryRead:
        uploaded_file = await self._file_access.get_processable_file(
            organization_id, datasource_id, uploaded_file_id
        )
        try:
            with self._file_access.open_reader(uploaded_file) as reader:
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
