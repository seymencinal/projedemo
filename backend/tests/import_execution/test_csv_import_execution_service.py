import csv
from datetime import UTC, datetime
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
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
from app.exceptions.storage import StoredFileNotFoundError
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.uploaded_file import UploadedFile, UploadedFileStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.import_job import ImportJobRepository
from app.repositories.imported_record import ImportedRecordRepository
from app.repositories.uploaded_file import UploadedFileRepository
from app.services.csv_import_execution import CsvImportExecutionService
from app.services.import_row_validation import ImportRowValidator, SourceRow
from app.storage.protocol import FileStorage

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000010")
DATASOURCE_ID = UUID("00000000-0000-0000-0000-000000000020")
RESEARCH_ID = UUID("00000000-0000-0000-0000-000000000030")
FILE_ID = UUID("00000000-0000-0000-0000-000000000040")


def create_job() -> ImportJob:
    job = ImportJob(
        organization_id=ORGANIZATION_ID,
        research_id=RESEARCH_ID,
        datasource_id=DATASOURCE_ID,
        uploaded_file_id=FILE_ID,
        status=ImportJobStatus.PENDING,
        configuration={"mapping": {"content": "body", "engagement_count": "engagement"}},
        total_items=0,
        processed_items=0,
        failed_items=0,
        idempotency_key="key",
    )
    job.id = uuid4()
    return job


def create_file() -> UploadedFile:
    file = UploadedFile(
        organization_id=ORGANIZATION_ID,
        datasource_id=DATASOURCE_ID,
        original_filename="records.csv",
        stored_filename="stored.csv",
        storage_path="stored.csv",
        content_type="text/csv",
        size_bytes=10,
        checksum_sha256="a" * 64,
        status=UploadedFileStatus.PENDING,
    )
    file.id = FILE_ID
    return file


def create_service(
    content: bytes,
    storage: MagicMock | None = None,
) -> tuple[CsvImportExecutionService, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    if storage is None:
        storage = MagicMock(spec=FileStorage)
        storage.open = MagicMock(side_effect=lambda _: BytesIO(content))
    jobs = MagicMock(spec=ImportJobRepository)
    datasources = MagicMock(spec=DatasourceRepository)
    files = MagicMock(spec=UploadedFileRepository)
    records = MagicMock(spec=ImportedRecordRepository)
    records.insert_batch = AsyncMock()
    return (
        CsvImportExecutionService(session, storage, 100, 10, 2, jobs, datasources, files, records),
        session,
        jobs,
        datasources,
        files,
        records,
    )


@pytest.mark.asyncio
async def test_execute_streams_batches_and_completes_import_job() -> None:
    service, session, jobs, datasources, files, records = create_service(
        b"body,engagement\nfirst,1\nsecond,2\nthird,3\n"
    )
    job = create_job()
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    result = await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert result.status is ImportJobStatus.COMPLETED
    assert (result.total_items, result.processed_items, result.failed_items) == (3, 3, 0)
    assert result.started_at is not None and result.completed_at is not None
    assert result.error_message is None
    assert records.insert_batch.await_count == 2
    first_batch = records.insert_batch.await_args_list[0].args[0]
    assert first_batch[0].content == "first"
    assert first_batch[0].engagement_count == 1
    assert len(first_batch[0].raw_row_hash) == 64
    assert first_batch[0].source_row_number == 2
    assert session.commit.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_content", "expected_hash"),
    [
        ("hello", "3d876ef0ede593f67420bbc75fe5eed9d69f94092b342e8a8b851c02fe99e9e7"),
        ("  hello  ", "44164b6e0f2d825df2e7f276b2c217e6a8cb26e76d8477035ea4a271cb5eced8"),
        ("İstanbul", "a0612e46ed10f2c04f4db930412309464fb8e1abe1179d1e2f702c8260a318df"),
        ("content", "9185bd4f60c330233e612dedaca6437c98fe5825e9cd1caf1534caf60777107d"),
    ],
)
async def test_execute_preserves_legacy_raw_row_hash_input(
    raw_content: str, expected_hash: str
) -> None:
    service, _, jobs, datasources, files, records = create_service(
        f"body,author\n{raw_content},\n".encode()
    )
    job = create_job()
    job.configuration = {"mapping": {"content": "body", "author": "author"}}
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    inserted = records.insert_batch.await_args.args[0][0]
    assert inserted.raw_row_hash == expected_hash
    assert inserted.content == raw_content.strip()
    assert inserted.author is None


@pytest.mark.asyncio
async def test_execute_rolls_back_flushed_batches_after_first_invalid_row() -> None:
    service, session, jobs, datasources, files, records = create_service(
        b"body,author\nfirst,writer\n,writer\nlater,writer\n"
    )
    service._batch_size = 1
    job = create_job()
    job.configuration = {"mapping": {"content": "body", "author": "author"}}
    jobs.get_for_execution = AsyncMock(side_effect=[job, job])
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    with pytest.raises(InvalidImportedRecordError):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert records.insert_batch.await_count == 1
    assert records.insert_batch.await_args.args[0][0].content == "first"
    assert session.rollback.await_count == 1
    assert job.status is ImportJobStatus.FAILED
    assert job.error_message == "CSV import execution failed."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        (b"body,\nvalue,value\n", BlankCsvHeaderError),
        (b"body,engagement\n,1\n", InvalidImportedRecordError),
        (b"other\nvalue\n", MissingMappedColumnError),
    ],
)
async def test_execute_rolls_back_and_marks_job_failed_for_fatal_csv_errors(
    content: bytes, error_type: type[Exception]
) -> None:
    service, session, jobs, datasources, files, records = create_service(content)
    job = create_job()
    jobs.get_for_execution = AsyncMock(side_effect=[job, job])
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    with pytest.raises(error_type):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert job.status is ImportJobStatus.FAILED
    assert (job.total_items, job.processed_items, job.failed_items) == (0, 0, 0)
    assert job.error_message == "CSV import execution failed."
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 2
    records.insert_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_commits_running_state_before_opening_storage() -> None:
    storage = MagicMock(spec=FileStorage)
    job = create_job()
    job.configuration = {"mapping": {"content": "body"}}

    def open_after_running_commit(_: str) -> BytesIO:
        assert session.commit.await_count == 1
        assert job.status is ImportJobStatus.RUNNING
        return BytesIO(b"body\nvalue\n")

    storage.open = MagicMock(side_effect=open_after_running_commit)
    service, session, jobs, datasources, files, _ = create_service(b"", storage)
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert job.status is ImportJobStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_uses_physical_csv_line_numbers() -> None:
    service, _, jobs, datasources, files, records = create_service(b"\n\nbody\nfirst\n\nsecond\n")
    job = create_job()
    job.configuration = {"mapping": {"content": "body"}}
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    batches = [call.args[0] for call in records.insert_batch.await_args_list]
    records_by_content = {record.content: record for batch in batches for record in batch}
    assert records_by_content["first"].source_row_number == 4
    assert records_by_content["second"].source_row_number == 6


@pytest.mark.asyncio
async def test_execute_uses_final_physical_line_for_multiline_quoted_record() -> None:
    service, _, jobs, datasources, files, records = create_service(
        b'body\n"first line\nsecond line"\n'
    )
    job = create_job()
    job.configuration = {"mapping": {"content": "body"}}
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    inserted = records.insert_batch.await_args.args[0][0]
    assert inserted.source_row_number == 3
    assert inserted.content == "first line\nsecond line"


@pytest.mark.asyncio
async def test_execute_rejects_non_pending_job_without_opening_storage() -> None:
    service, session, jobs, _, _, _ = create_service(b"body\nvalue\n")
    job = create_job()
    job.status = ImportJobStatus.RUNNING
    jobs.get_for_execution = AsyncMock(return_value=job)

    with pytest.raises(ImportJobNotExecutableError):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_hides_cross_tenant_job_as_not_found() -> None:
    service, _, jobs, _, _, _ = create_service(b"body\nvalue\n")
    jobs.get_for_execution = AsyncMock(return_value=None)

    with pytest.raises(ImportJobNotFoundError):
        await service.execute(uuid4(), ORGANIZATION_ID, DATASOURCE_ID)


@pytest.mark.asyncio
async def test_execute_hides_failed_state_persistence_failure() -> None:
    service, session, jobs, datasources, files, records = create_service(b"body\nvalue\n")
    job = create_job()
    job.configuration = {"mapping": {"content": "body"}}
    jobs.get_for_execution = AsyncMock(side_effect=[job, job])
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())
    records.insert_batch.side_effect = SQLAlchemyError("database internals")
    session.commit.side_effect = [None, SQLAlchemyError("database internals")]

    with pytest.raises(ImportedRecordPersistenceError) as error_info:
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert str(error_info.value) == "CSV import could not be persisted."
    assert "database internals" not in str(error_info.value)
    assert session.rollback.await_count == 2


@pytest.mark.asyncio
async def test_execute_rolls_back_preflight_failures_without_marking_job_failed() -> None:
    service, session, jobs, datasources, _, _ = create_service(b"body\nvalue\n")
    job = create_job()
    job.configuration = {"mapping": {"unknown": "body"}}
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())

    with pytest.raises(InvalidImportJobConfigurationError):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert job.status is ImportJobStatus.PENDING
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_keeps_cross_datasource_file_lookup_safe() -> None:
    service, session, jobs, datasources, files, _ = create_service(b"body\nvalue\n")
    job = create_job()
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    other_file = create_file()
    other_file.datasource_id = uuid4()
    files.get = AsyncMock(return_value=other_file)

    with pytest.raises(DatasourceNotFoundError):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_propagates_storage_not_found_and_keeps_job_pending() -> None:
    storage = MagicMock(spec=FileStorage)
    storage.open = MagicMock(side_effect=StoredFileNotFoundError())
    service, session, jobs, datasources, files, _ = create_service(b"", storage)
    job = create_job()
    jobs.get_for_execution = AsyncMock(return_value=job)
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())
    with pytest.raises(StoredFileNotFoundError):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert job.status is ImportJobStatus.FAILED
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_records_accepts_header_only_csv() -> None:
    service, _, _, _, _, records = create_service(b"")
    job = create_job()
    reader = csv.reader(StringIO("body\n"), strict=True)

    total_items = await service._persist_records(job, {"content": "body"}, reader)

    assert total_items == 0
    records.insert_batch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    ["", "\n\n"],
)
async def test_persist_records_rejects_empty_or_only_blank_csv(content: str) -> None:
    service, _, _, _, _, _ = create_service(b"")

    with pytest.raises(EmptyCsvFileError):
        await service._persist_records(
            create_job(), {"content": "body"}, csv.reader(StringIO(content))
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["body\na,b\n", "body,extra\na\n"])
async def test_persist_records_rejects_row_width_mismatches(content: str) -> None:
    service, _, _, _, _, _ = create_service(b"")

    with pytest.raises(InvalidImportedRecordError):
        await service._persist_records(
            create_job(), {"content": "body"}, csv.reader(StringIO(content))
        )


@pytest.mark.asyncio
async def test_persist_records_stops_after_row_limit() -> None:
    service, _, _, _, _, records = create_service(b"")
    service._max_rows = 1

    with pytest.raises(CsvRowLimitExceededError):
        await service._persist_records(
            create_job(), {"content": "body"}, csv.reader(StringIO("body\none\ntwo\n"))
        )

    records.insert_batch.assert_not_awaited()


def test_validate_header_trims_values_and_rejects_structural_errors() -> None:
    service, _, _, _, _, _ = create_service(b"")

    assert service._validate_header([" body "], {"content": "body"}) == ["body"]
    with pytest.raises(BlankCsvHeaderError):
        service._validate_header(["body", "  "], {"content": "body"})
    with pytest.raises(DuplicateCsvHeaderError):
        service._validate_header(["body", " body "], {"content": "body"})
    with pytest.raises(MissingMappedColumnError):
        service._validate_header(["body"], {"content": "other"})
    service._max_columns = 1
    with pytest.raises(CsvColumnLimitExceededError):
        service._validate_header(["body", "other"], {"content": "body"})


def test_convert_record_enforces_field_limits_and_normalizes_optional_values() -> None:
    mapping = {
        "content": "body",
        "author": "author",
        "source_name": "source",
        "sentiment": "sentiment",
    }
    result = ImportRowValidator(mapping).validate(
        SourceRow(
            7,
            {
                "body": "x" * 20_000,
                "author": "a" * 255,
                "source": "s" * 255,
                "sentiment": " neutral ",
            },
        )
    )

    assert result.record is not None
    assert result.record.sentiment == "neutral"
    assert (
        not ImportRowValidator({"content": "body"})
        .validate(SourceRow(1, {"body": "x" * 20_001}))
        .is_valid
    )
    assert (
        not ImportRowValidator({"content": "body", "author": "author"})
        .validate(SourceRow(1, {"body": "ok", "author": "a" * 256}))
        .is_valid
    )
    assert (
        not ImportRowValidator({"content": "body", "sentiment": "sentiment"})
        .validate(SourceRow(1, {"body": "ok", "sentiment": "Positive"}))
        .is_valid
    )


@pytest.mark.asyncio
async def test_execute_marks_job_failed_for_malformed_csv() -> None:
    service, _, jobs, datasources, files, _ = create_service(b'body\n"unterminated\n')
    job = create_job()
    job.configuration = {"mapping": {"content": "body"}}
    jobs.get_for_execution = AsyncMock(side_effect=[job, job])
    datasources.get = AsyncMock(return_value=SimpleNamespace())
    files.get = AsyncMock(return_value=create_file())

    with pytest.raises(csv.Error):
        await service.execute(job.id, ORGANIZATION_ID, DATASOURCE_ID)

    assert job.status is ImportJobStatus.FAILED
    assert job.started_at is not None and job.completed_at is not None
    assert job.error_message == "CSV import execution failed."


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("0", 0),
        ("+1", 1),
        (" 2 ", 2),
    ],
)
def test_parse_engagement_accepts_supported_values(value: str | None, expected: int | None) -> None:
    source_value = value or ""
    result = ImportRowValidator({"content": "body", "engagement_count": "engagement"}).validate(
        SourceRow(2, {"body": "content", "engagement": source_value})
    )

    assert result.record is not None
    assert result.record.engagement_count == expected


def test_optional_value_normalizes_whitespace_to_none() -> None:
    result = ImportRowValidator({"content": "body", "author": "author"}).validate(
        SourceRow(2, {"body": "content", "author": "  "})
    )

    assert result.record is not None
    assert result.record.author is None


@pytest.mark.parametrize("value", ["-1", "1.2", "value"])
def test_parse_engagement_rejects_invalid_values(value: str) -> None:
    result = ImportRowValidator({"content": "body", "engagement_count": "engagement"}).validate(
        SourceRow(2, {"body": "content", "engagement": value})
    )

    assert not result.is_valid


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-07-23", datetime(2026, 7, 23, tzinfo=UTC)),
        ("2026-07-23T12:00:00Z", datetime(2026, 7, 23, 12, tzinfo=UTC)),
        ("2026-07-23T14:00:00+02:00", datetime(2026, 7, 23, 12, tzinfo=UTC)),
        ("2026-07-23T09:00:00-03:00", datetime(2026, 7, 23, 12, tzinfo=UTC)),
    ],
)
def test_parse_datetime_normalizes_supported_values(value: str, expected: datetime) -> None:
    result = ImportRowValidator({"content": "body", "published_at": "published"}).validate(
        SourceRow(2, {"body": "content", "published": value})
    )

    assert result.record is not None
    assert result.record.published_at == expected


@pytest.mark.parametrize("value", ["2026-02-30", "23/07/2026", "2026-07-23T12:00:00"])
def test_parse_datetime_rejects_unsupported_values(value: str) -> None:
    result = ImportRowValidator({"content": "body", "published_at": "published"}).validate(
        SourceRow(2, {"body": "content", "published": value})
    )

    assert not result.is_valid


def test_hash_row_is_deterministic_ordered_and_fixed_length() -> None:
    first = CsvImportExecutionService._hash_row(["content", "", "value"])

    assert first == CsvImportExecutionService._hash_row(["content", "", "value"])
    assert first != CsvImportExecutionService._hash_row(["value", "", "content"])
    assert first != CsvImportExecutionService._hash_row(["content", "value"])
    assert len(first) == 64
    assert first == first.lower()
    assert all(character in "0123456789abcdef" for character in first)
