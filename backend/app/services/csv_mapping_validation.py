from collections.abc import Mapping

from app.exceptions.csv_mapping import (
    BlankSourceColumnError,
    DuplicateSourceColumnError,
    MissingRequiredCanonicalFieldError,
    UnknownCanonicalFieldError,
)

CANONICAL_CSV_FIELDS = frozenset(
    {
        "published_at",
        "author",
        "content",
        "engagement_count",
        "sentiment",
        "source_name",
    }
)


def validate_csv_mapping(mapping: Mapping[str, str]) -> dict[str, str]:
    if not set(mapping).issubset(CANONICAL_CSV_FIELDS):
        raise UnknownCanonicalFieldError()
    if "content" not in mapping:
        raise MissingRequiredCanonicalFieldError()
    normalized_mapping = {field: source_column.strip() for field, source_column in mapping.items()}
    if any(not source_column for source_column in normalized_mapping.values()):
        raise BlankSourceColumnError()
    if len(set(normalized_mapping.values())) != len(normalized_mapping):
        raise DuplicateSourceColumnError()
    return normalized_mapping
