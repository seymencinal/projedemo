from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.import_job import ImportJobStatus
from app.schemas.csv_mapping import CsvImportMappingAcceptedRead, CsvImportMappingRequest


def test_mapping_request_normalizes_idempotency_key_and_preserves_exact_mapping() -> None:
    payload = CsvImportMappingRequest(
        idempotency_key=" mapping-key ",
        mapping={"content": "Body", "author": "Author"},
    )

    assert payload.idempotency_key == "mapping-key"
    assert payload.mapping == {"content": "Body", "author": "Author"}


def test_mapping_request_rejects_blank_key_and_mapping_sizes_outside_limits() -> None:
    with pytest.raises(ValidationError):
        CsvImportMappingRequest(idempotency_key="   ", mapping={"content": "body"})
    with pytest.raises(ValidationError):
        CsvImportMappingRequest(idempotency_key="key", mapping={})
    with pytest.raises(ValidationError):
        CsvImportMappingRequest(
            idempotency_key="key",
            mapping={
                "content": "content",
                "author": "author",
                "published_at": "published_at",
                "engagement_count": "engagement_count",
                "sentiment": "sentiment",
                "source_name": "source_name",
                "unexpected": "unexpected",
            },
        )


def test_mapping_accepted_response_contains_only_public_preparation_data() -> None:
    import_job_id = uuid4()
    uploaded_file_id = uuid4()
    datasource_id = uuid4()

    response = CsvImportMappingAcceptedRead(
        import_job_id=import_job_id,
        status=ImportJobStatus.PENDING,
        uploaded_file_id=uploaded_file_id,
        datasource_id=datasource_id,
        accepted_mapping={"content": "body"},
    )

    assert response.model_dump(mode="json") == {
        "import_job_id": str(import_job_id),
        "status": "pending",
        "uploaded_file_id": str(uploaded_file_id),
        "datasource_id": str(datasource_id),
        "accepted_mapping": {"content": "body"},
    }
