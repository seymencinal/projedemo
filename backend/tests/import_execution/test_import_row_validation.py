from datetime import UTC, datetime

import pytest

from app.services.import_row_validation import (
    ImportRowValidator,
    RowValidationIssue,
    SourceRow,
    ValidatedImportRecord,
    ValidationResult,
)


def validate(values: dict[str, str], mapping: dict[str, str] | None = None) -> ValidationResult:
    return ImportRowValidator(mapping or {"content": "body"}).validate(SourceRow(7, values))


def test_source_row_preserves_physical_number_and_is_immutable() -> None:
    original_values = {"body": "value"}
    row = SourceRow(7, original_values)
    original_values["body"] = "changed outside"

    assert row.source_row_number == 7
    assert row.values == {"body": "value"}
    with pytest.raises(TypeError):
        row.values["body"] = "changed"
    with pytest.raises(ValueError):
        SourceRow(0, {})


def test_validation_result_requires_exactly_one_state() -> None:
    valid = ValidatedImportRecord("value", None, None, None, None, None)

    assert ValidationResult(valid).is_valid
    with pytest.raises(ValueError):
        ValidationResult(None)
    with pytest.raises(ValueError):
        ValidationResult(valid, (RowValidationIssue(1, "content", "body", "required", "safe"),))


@pytest.mark.parametrize("value", [" value ", "x" * 20_000])
def test_content_is_trimmed_and_accepts_boundary(value: str) -> None:
    result = validate({"body": value})

    assert result.is_valid
    assert result.record is not None
    assert result.record.content == value.strip()


@pytest.mark.parametrize("value", ["", "  ", "x" * 20_001])
def test_content_rejects_blank_and_over_limit(value: str) -> None:
    result = validate({"body": value})

    assert not result.is_valid
    assert result.issues[0].canonical_field == "content"
    assert result.issues[0].source_column == "body"
    assert result.issues[0].source_row_number == 7
    assert result.issues[0].code in {"required", "content_too_long"}


@pytest.mark.parametrize("field", ["author", "source_name"])
@pytest.mark.parametrize("value", ["", "  ", " value ", "x" * 255])
def test_optional_short_text_fields_preserve_normalization(field: str, value: str) -> None:
    mapping = {"content": "body", field: field}
    result = validate({"body": "content", field: value}, mapping)

    assert result.is_valid
    assert result.record is not None
    assert getattr(result.record, field) == (value.strip() or None)


@pytest.mark.parametrize("field", ["author", "source_name"])
def test_optional_short_text_fields_reject_over_limit(field: str) -> None:
    result = validate({"body": "content", field: "x" * 256}, {"content": "body", field: field})

    assert not result.is_valid
    assert result.issues[0].canonical_field == field
    assert result.issues[0].code == "value_too_long"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", None), ("  ", None), ("0", 0), ("+1", 1), (" 2 ", 2)],
)
def test_engagement_preserves_existing_conversion(value: str, expected: int | None) -> None:
    result = validate(
        {"body": "content", "engagement": value},
        {"content": "body", "engagement_count": "engagement"},
    )

    assert result.is_valid
    assert result.record is not None
    assert result.record.engagement_count == expected


@pytest.mark.parametrize("value", ["-1", "1.2", "value"])
def test_engagement_rejects_invalid_values(value: str) -> None:
    result = validate(
        {"body": "content", "engagement": value},
        {"content": "body", "engagement_count": "engagement"},
    )

    assert not result.is_valid
    assert result.issues[0].canonical_field == "engagement_count"
    assert result.issues[0].code in {"invalid_integer", "negative_integer"}


@pytest.mark.parametrize("value", ["", "  ", "positive", "negative", "neutral"])
def test_sentiment_accepts_only_existing_lowercase_values(value: str) -> None:
    result = validate(
        {"body": "content", "sentiment": value}, {"content": "body", "sentiment": "sentiment"}
    )

    assert result.is_valid
    assert result.record is not None
    assert result.record.sentiment == (value.strip() or None)


@pytest.mark.parametrize("value", ["Positive", "unknown"])
def test_sentiment_rejects_invalid_values(value: str) -> None:
    result = validate(
        {"body": "content", "sentiment": value}, {"content": "body", "sentiment": "sentiment"}
    )

    assert not result.is_valid
    assert result.issues[0].canonical_field == "sentiment"
    assert result.issues[0].code == "invalid_sentiment"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", None),
        ("2026-07-23", datetime(2026, 7, 23, tzinfo=UTC)),
        ("2026-07-23T12:00:00Z", datetime(2026, 7, 23, 12, tzinfo=UTC)),
    ],
)
def test_published_at_preserves_supported_formats(value: str, expected: datetime | None) -> None:
    result = validate(
        {"body": "content", "published": value}, {"content": "body", "published_at": "published"}
    )

    assert result.is_valid
    assert result.record is not None
    assert result.record.published_at == expected


@pytest.mark.parametrize("value", ["2026-07-23T12:00:00", "23/07/2026"])
def test_published_at_rejects_naive_and_malformed_values(value: str) -> None:
    result = validate(
        {"body": "content", "published": value}, {"content": "body", "published_at": "published"}
    )

    assert not result.is_valid
    assert result.issues[0].canonical_field == "published_at"
    assert result.issues[0].code == "invalid_datetime"


def test_validator_collects_stable_multiple_field_issues() -> None:
    result = validate(
        {"body": "", "engagement": "-1", "sentiment": "Positive"},
        {"content": "body", "engagement_count": "engagement", "sentiment": "sentiment"},
    )

    assert [issue.canonical_field for issue in result.issues] == [
        "content",
        "engagement_count",
        "sentiment",
    ]
    assert [issue.code for issue in result.issues] == [
        "required",
        "negative_integer",
        "invalid_sentiment",
    ]


def test_validator_returns_safe_issue_for_a_missing_mapped_source_column() -> None:
    result = validate({"body": "content"}, {"content": "body", "author": "missing"})

    assert not result.is_valid
    assert result.issues == (
        RowValidationIssue(
            source_row_number=7,
            canonical_field="author",
            source_column="missing",
            code="missing_source_column",
            message="CSV import contains an invalid record.",
        ),
    )


def test_unmapped_optional_fields_remain_none() -> None:
    result = validate({"body": "content"})

    assert result.is_valid
    assert result.record is not None
    assert result.record.author is None
    assert result.record.source_name is None
