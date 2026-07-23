class ImportJobNotExecutableError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV import job is not executable.")


class InvalidImportJobConfigurationError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV import job configuration is invalid.")


class BlankCsvHeaderError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV header contains a blank column.")


class DuplicateCsvHeaderError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV header contains duplicate columns.")


class MissingMappedColumnError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV header does not contain every mapped column.")


class InvalidImportedRecordError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV import contains an invalid record.")


class ImportedRecordPersistenceError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV import could not be persisted.")
