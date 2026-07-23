import csv
from collections.abc import Iterator
from contextlib import contextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import ClassVar, Protocol
from uuid import UUID

from app.exceptions.csv_processing import CsvFileNotProcessableError, UnsupportedCsvFileError
from app.exceptions.research import DatasourceNotFoundError
from app.exceptions.uploaded_file import UploadedFileNotFoundError
from app.models.uploaded_file import UploadedFile, UploadedFileStatus
from app.repositories.uploaded_file import UploadedFileRepository
from app.storage.protocol import FileStorage


class CsvRowReader(Protocol):
    line_num: int

    def __iter__(self) -> "CsvRowReader": ...

    def __next__(self) -> list[str]: ...


class CsvFileAccessService:
    _content_types: ClassVar[set[str]] = {"text/csv", "application/csv", "application/octet-stream"}

    def __init__(self, repository: UploadedFileRepository, storage: FileStorage) -> None:
        self._repository = repository
        self._storage = storage

    async def get_processable_file(
        self, organization_id: UUID, datasource_id: UUID, uploaded_file_id: UUID
    ) -> UploadedFile:
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
        return uploaded_file

    @contextmanager
    def open_reader(self, uploaded_file: UploadedFile) -> Iterator[CsvRowReader]:
        with (
            self._storage.open(uploaded_file.storage_path) as binary_file,
            TextIOWrapper(binary_file, encoding="utf-8-sig", newline="") as text_file,
        ):
            yield csv.reader(text_file, strict=True)
