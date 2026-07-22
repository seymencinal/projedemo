class UnsupportedCsvFileError(Exception):
    def __init__(self) -> None:
        super().__init__("Only supported CSV files can be processed.")


class EmptyCsvFileError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV file does not contain a header.")


class MalformedCsvError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV file format is invalid.")


class CsvRowLimitExceededError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV row limit was exceeded.")


class CsvColumnLimitExceededError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV column limit was exceeded.")


class CsvFileNotProcessableError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV file cannot be processed in its current state.")
