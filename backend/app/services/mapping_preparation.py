from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.csv_mapping import (
    BlankSourceColumnError,
    DuplicateSourceColumnError,
    MissingRequiredCanonicalFieldError,
    UnknownCanonicalFieldError,
)
from app.exceptions.research import DatasourceNotFoundError, IdempotencyConflictError
from app.exceptions.uploaded_file import UploadedFileNotFoundError
from app.models.import_job import ImportJob, ImportJobStatus
from app.repositories.datasource import DatasourceRepository
from app.repositories.import_job import ImportJobRepository
from app.repositories.uploaded_file import UploadedFileRepository
from app.schemas.csv_mapping import CsvImportMappingAcceptedRead, CsvImportMappingRequest


class MappingPreparationService:
    _canonical_fields = frozenset(
        {
            "published_at",
            "author",
            "content",
            "engagement_count",
            "sentiment",
            "source_name",
        }
    )

    def __init__(
        self,
        session: AsyncSession,
        import_job_repository: ImportJobRepository | None = None,
        datasource_repository: DatasourceRepository | None = None,
        uploaded_file_repository: UploadedFileRepository | None = None,
    ) -> None:
        self._session = session
        self._import_job_repository = import_job_repository or ImportJobRepository(session)
        self._datasource_repository = datasource_repository or DatasourceRepository(session)
        self._uploaded_file_repository = uploaded_file_repository or UploadedFileRepository(session)

    async def prepare(
        self,
        datasource_id: UUID,
        uploaded_file_id: UUID,
        organization_id: UUID,
        payload: CsvImportMappingRequest,
    ) -> CsvImportMappingAcceptedRead:
        datasource = await self._datasource_repository.get(datasource_id, organization_id)
        if datasource is None:
            raise DatasourceNotFoundError(datasource_id)

        uploaded_file = await self._uploaded_file_repository.get(uploaded_file_id, organization_id)
        if uploaded_file is None:
            raise UploadedFileNotFoundError(uploaded_file_id)
        if uploaded_file.datasource_id != datasource_id:
            raise DatasourceNotFoundError(datasource_id)

        accepted_mapping = self._validate_mapping(payload.mapping)
        existing = await self._import_job_repository.get_by_key(
            organization_id,
            datasource_id,
            payload.idempotency_key,
        )
        if existing is not None:
            raise IdempotencyConflictError(payload.idempotency_key)

        item = await self._import_job_repository.add(
            ImportJob(
                organization_id=organization_id,
                research_id=datasource.research_id,
                datasource_id=datasource_id,
                uploaded_file_id=uploaded_file_id,
                status=ImportJobStatus.PENDING,
                total_items=0,
                processed_items=0,
                failed_items=0,
                configuration={"mapping": accepted_mapping},
                idempotency_key=payload.idempotency_key,
            )
        )
        await self._session.commit()
        await self._session.refresh(item)
        return CsvImportMappingAcceptedRead(
            import_job_id=item.id,
            status=item.status,
            uploaded_file_id=uploaded_file_id,
            datasource_id=datasource_id,
            accepted_mapping=accepted_mapping,
        )

    def _validate_mapping(self, mapping: Mapping[str, str]) -> dict[str, str]:
        if not set(mapping).issubset(self._canonical_fields):
            raise UnknownCanonicalFieldError()
        if "content" not in mapping:
            raise MissingRequiredCanonicalFieldError()

        normalized_mapping = {
            field: source_column.strip() for field, source_column in mapping.items()
        }
        if any(not source_column for source_column in normalized_mapping.values()):
            raise BlankSourceColumnError()
        if len(set(normalized_mapping.values())) != len(normalized_mapping):
            raise DuplicateSourceColumnError()
        return normalized_mapping
