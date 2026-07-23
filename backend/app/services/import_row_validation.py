import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from types import MappingProxyType

type NormalizedFieldValue = str | int | datetime | None


@dataclass(frozen=True, slots=True)
class ImportFieldDefinition:
    canonical_field: str
    required: bool
    converter: Callable[[str | None], NormalizedFieldValue]


@dataclass(frozen=True, slots=True)
class SourceRow:
    source_row_number: int
    values: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.source_row_number < 1:
            raise ValueError("Source row number must be positive.")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class RowValidationIssue:
    source_row_number: int
    canonical_field: str
    source_column: str | None
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidatedImportRecord:
    content: str
    published_at: datetime | None
    author: str | None
    engagement_count: int | None
    sentiment: str | None
    source_name: str | None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    record: ValidatedImportRecord | None
    issues: tuple[RowValidationIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (self.record is None) != bool(self.issues):
            raise ValueError("ValidationResult must contain either a record or validation issues.")

    @property
    def is_valid(self) -> bool:
        return self.record is not None


class ImportRowValidator:
    _date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    _sentiments = frozenset({"positive", "negative", "neutral"})

    def __init__(self, mapping: Mapping[str, str]) -> None:
        self._mapping = dict(mapping)
        self._definitions = (
            ImportFieldDefinition("content", True, self._convert_content),
            ImportFieldDefinition("published_at", False, self._convert_datetime),
            ImportFieldDefinition("author", False, self._convert_short_text),
            ImportFieldDefinition("engagement_count", False, self._convert_engagement),
            ImportFieldDefinition("sentiment", False, self._convert_sentiment),
            ImportFieldDefinition("source_name", False, self._convert_short_text),
        )

    def validate(self, source_row: SourceRow) -> ValidationResult:
        values: dict[str, NormalizedFieldValue] = {}
        issues: list[RowValidationIssue] = []
        for definition in self._definitions:
            source_column = self._mapping.get(definition.canonical_field)
            if source_column is not None and source_column not in source_row.values:
                issues.append(
                    RowValidationIssue(
                        source_row_number=source_row.source_row_number,
                        canonical_field=definition.canonical_field,
                        source_column=source_column,
                        code="missing_source_column",
                        message="CSV import contains an invalid record.",
                    )
                )
                continue
            raw_value = (
                self._optional_value(source_row.values[source_column])
                if source_column is not None
                else None
            )
            try:
                converted = definition.converter(raw_value)
            except ValueError as error:
                issues.append(
                    RowValidationIssue(
                        source_row_number=source_row.source_row_number,
                        canonical_field=definition.canonical_field,
                        source_column=source_column,
                        code=str(error),
                        message="CSV import contains an invalid record.",
                    )
                )
                continue
            if definition.required and converted is None:
                issues.append(
                    RowValidationIssue(
                        source_row_number=source_row.source_row_number,
                        canonical_field=definition.canonical_field,
                        source_column=source_column,
                        code="required",
                        message="CSV import contains an invalid record.",
                    )
                )
                continue
            values[definition.canonical_field] = converted
        if issues:
            return ValidationResult(record=None, issues=tuple(issues))
        content = values["content"]
        if not isinstance(content, str):
            raise RuntimeError("Content validation invariant failed.")
        return ValidationResult(
            record=ValidatedImportRecord(
                content=content,
                published_at=self._datetime_value(values.get("published_at")),
                author=self._string_value(values.get("author")),
                engagement_count=self._integer_value(values.get("engagement_count")),
                sentiment=self._string_value(values.get("sentiment")),
                source_name=self._string_value(values.get("source_name")),
            )
        )

    @staticmethod
    def _optional_value(value: str) -> str | None:
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _convert_content(value: str | None) -> str | None:
        if value is not None and len(value) > 20_000:
            raise ValueError("content_too_long")
        return value

    @staticmethod
    def _convert_short_text(value: str | None) -> str | None:
        if value is not None and len(value) > 255:
            raise ValueError("value_too_long")
        return value

    def _convert_datetime(self, value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            if self._date_pattern.fullmatch(value):
                return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)
            if "T" not in value:
                raise ValueError
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError
            return parsed.astimezone(UTC)
        except ValueError as error:
            raise ValueError("invalid_datetime") from error

    @staticmethod
    def _convert_engagement(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError as error:
            raise ValueError("invalid_integer") from error
        if parsed < 0:
            raise ValueError("negative_integer")
        return parsed

    def _convert_sentiment(self, value: str | None) -> str | None:
        if value is not None and value not in self._sentiments:
            raise ValueError("invalid_sentiment")
        return value

    @staticmethod
    def _datetime_value(value: NormalizedFieldValue | None) -> datetime | None:
        return value if isinstance(value, datetime) else None

    @staticmethod
    def _integer_value(value: NormalizedFieldValue | None) -> int | None:
        return value if isinstance(value, int) else None

    @staticmethod
    def _string_value(value: NormalizedFieldValue | None) -> str | None:
        return value if isinstance(value, str) else None
