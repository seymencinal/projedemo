import csv
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.csv_import_execution import (
    BlankCsvHeaderError,
    DuplicateCsvHeaderError,
    ImportedRecordPersistenceError,
    ImportJobNotExecutableError,
    InvalidImportedRecordError,
    InvalidImportJobConfigurationError,
    MissingMappedColumnError,
)
from app.exceptions.csv_processing import (
    CsvColumnLimitExceededError,
    CsvRowLimitExceededError,
    EmptyCsvFileError,
)
from app.exceptions.research import DatasourceNotFoundError, ImportJobNotFoundError
from app.models.import_job import ImportJob, ImportJobStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.import_job import ImportJobRepository
from app.repositories.import_validation_issue import ImportValidationIssueRepository
from app.repositories.imported_record import ImportedRecordRepository
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.imported_record import ImportedRecordInsert
from app.services.csv_file_access import CsvFileAccessService, CsvRowReader
from app.services.csv_mapping_validation import validate_csv_mapping
from app.services.import_row_validation import (
    ImportRowValidator,
    RowValidationIssue,
    SourceRow,
    ValidatedImportRecord,
)
from app.storage.protocol import FileStorage


class CsvImportExecutionService:
    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorage,
        max_rows: int,
        max_columns: int,
        batch_size: int,
        import_job_repository: ImportJobRepository | None = None,
        datasource_repository: DatasourceRepository | None = None,
        uploaded_file_repository: UploadedFileRepository | None = None,
        imported_record_repository: ImportedRecordRepository | None = None,
        import_validation_issue_repository: ImportValidationIssueRepository | None = None,
    ) -> None:
        self._session = session
        self._max_rows = max_rows
        self._max_columns = max_columns
        self._batch_size = batch_size
        self._import_jobs = import_job_repository or ImportJobRepository(session)
        self._datasources = datasource_repository or DatasourceRepository(session)
        self._files = uploaded_file_repository or UploadedFileRepository(session)
        self._records = imported_record_repository or ImportedRecordRepository(session)
        self._issues = import_validation_issue_repository or ImportValidationIssueRepository(
            session
        )
        self._file_access = CsvFileAccessService(self._files, storage)

    async def execute(
        self, import_job_id: UUID, organization_id: UUID, datasource_id: UUID
    ) -> ImportJob:
        job = await self._import_jobs.get_for_execution(
            import_job_id, organization_id, datasource_id
        )
        if job is None:
            raise ImportJobNotFoundError(import_job_id)
        if job.status is not ImportJobStatus.PENDING:
            await self._session.rollback()
            raise ImportJobNotExecutableError()
        if job.uploaded_file_id is None:
            await self._session.rollback()
            raise InvalidImportJobConfigurationError()
        if await self._datasources.get(datasource_id, organization_id) is None:
            await self._session.rollback()
            raise DatasourceNotFoundError(datasource_id)

        try:
            mapping = self._get_mapping(job.configuration)
            uploaded_file = await self._file_access.get_processable_file(
                organization_id, datasource_id, job.uploaded_file_id
            )
        except Exception:
            await self._session.rollback()
            raise
        job.status = ImportJobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.completed_at = None
        job.error_message = None
        await self._session.commit()

        try:
            with self._file_access.open_reader(uploaded_file) as reader:
                total_items = await self._persist_records(job, mapping, reader)
            job.status = ImportJobStatus.COMPLETED
            job.total_items = total_items
            job.processed_items = total_items
            job.failed_items = 0
            job.completed_at = datetime.now(UTC)
            job.error_message = None
            await self._session.commit()
            await self._session.refresh(job)
            return job
        except SQLAlchemyError as error:
            await self._session.rollback()
            await self._mark_failed_without_masking_error(
                import_job_id, organization_id, datasource_id
            )
            raise ImportedRecordPersistenceError() from error
        except InvalidImportedRecordError as error:
            await self._session.rollback()
            await self._mark_failed_without_masking_error(
                import_job_id, organization_id, datasource_id, error.issues
            )
            raise
        except (
            csv.Error,
            UnicodeDecodeError,
            MissingMappedColumnError,
            BlankCsvHeaderError,
            DuplicateCsvHeaderError,
        ):
            await self._session.rollback()
            await self._mark_failed_without_masking_error(
                import_job_id, organization_id, datasource_id
            )
            raise
        except Exception:
            await self._session.rollback()
            await self._mark_failed_without_masking_error(
                import_job_id, organization_id, datasource_id
            )
            raise

    async def _persist_records(
        self,
        job: ImportJob,
        mapping: dict[str, str],
        reader: CsvRowReader,
    ) -> int:
        header: list[str] | None = None
        indexes: dict[str, int] | None = None
        total_items = 0
        batch: list[ImportedRecordInsert] = []
        validator = ImportRowValidator(mapping)
        for record in reader:
            if not any(value.strip() for value in record):
                continue
            if header is None:
                header = self._validate_header(record, mapping)
                indexes = {column: index for index, column in enumerate(header)}
                continue
            if len(record) != len(header):
                raise InvalidImportedRecordError(
                    (
                        RowValidationIssue(
                            source_row_number=reader.line_num,
                            canonical_field="row",
                            source_column=None,
                            code="row_width",
                            message="CSV import contains an invalid record.",
                        ),
                    )
                )
            total_items += 1
            if total_items > self._max_rows:
                raise CsvRowLimitExceededError()
            if indexes is None:
                raise InvalidImportedRecordError()
            source_row = SourceRow(
                source_row_number=reader.line_num,
                values={column: record[index] for column, index in indexes.items()},
            )
            result = validator.validate(source_row)
            if not result.is_valid or result.record is None:
                raise InvalidImportedRecordError(result.issues)
            batch.append(self._to_insert(job, result.record, record, reader.line_num))
            if len(batch) == self._batch_size:
                await self._records.insert_batch(tuple(batch))
                batch.clear()
        if header is None:
            raise EmptyCsvFileError()
        if batch:
            await self._records.insert_batch(tuple(batch))
        return total_items

    def _validate_header(self, record: list[str], mapping: Mapping[str, str]) -> list[str]:
        header = [value.strip() for value in record]
        if len(header) > self._max_columns:
            raise CsvColumnLimitExceededError()
        if any(not value for value in header):
            raise BlankCsvHeaderError()
        if len(set(header)) != len(header):
            raise DuplicateCsvHeaderError()
        if not set(mapping.values()).issubset(header):
            raise MissingMappedColumnError()
        return header

    def _to_insert(
        self,
        job: ImportJob,
        record: ValidatedImportRecord,
        raw_record: list[str],
        source_row_number: int,
    ) -> ImportedRecordInsert:
        return ImportedRecordInsert(
            organization_id=job.organization_id,
            research_id=job.research_id,
            datasource_id=job.datasource_id,
            import_job_id=job.id,
            source_row_number=source_row_number,
            raw_row_hash=self._hash_row(raw_record),
            content=record.content,
            published_at=record.published_at,
            author=record.author,
            engagement_count=record.engagement_count,
            sentiment=record.sentiment,
            source_name=record.source_name,
        )

    def _get_mapping(self, configuration: object) -> dict[str, str]:
        if not isinstance(configuration, dict):
            raise InvalidImportJobConfigurationError()
        mapping = configuration.get("mapping")
        if not isinstance(mapping, dict) or not all(
            isinstance(field, str) and isinstance(column, str) for field, column in mapping.items()
        ):
            raise InvalidImportJobConfigurationError()
        try:
            return validate_csv_mapping(mapping)
        except (
            BlankCsvHeaderError,
            DuplicateCsvHeaderError,
            MissingMappedColumnError,
            InvalidImportedRecordError,
            InvalidImportJobConfigurationError,
        ) as error:
            raise InvalidImportJobConfigurationError() from error
        except Exception as error:
            raise InvalidImportJobConfigurationError() from error

    @staticmethod
    def _hash_row(record: list[str]) -> str:
        serialized = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def _mark_failed(
        self,
        import_job_id: UUID,
        organization_id: UUID,
        datasource_id: UUID,
        issues: tuple[RowValidationIssue, ...] = (),
    ) -> None:
        job = await self._import_jobs.get_for_execution(
            import_job_id, organization_id, datasource_id
        )
        if job is None:
            return
        if job.status is not ImportJobStatus.RUNNING:
            return
        job.status = ImportJobStatus.FAILED
        job.total_items = 0
        job.processed_items = 0
        job.failed_items = 0
        job.completed_at = datetime.now(UTC)
        job.error_message = "CSV import execution failed."
        await self._issues.insert_many(job.id, issues)
        await self._session.commit()

    async def _mark_failed_without_masking_error(
        self,
        import_job_id: UUID,
        organization_id: UUID,
        datasource_id: UUID,
        issues: tuple[RowValidationIssue, ...] = (),
    ) -> None:
        try:
            await self._mark_failed(import_job_id, organization_id, datasource_id, issues)
        except Exception:
            await self._session.rollback()
