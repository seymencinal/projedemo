from uuid import UUID


class ResearchNotFoundError(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"Research with id '{item_id}' was not found.")


class DatasourceNotFoundError(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"Datasource with id '{item_id}' was not found.")


class ImportJobNotFoundError(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"Import job with id '{item_id}' was not found.")


class InvalidImportJobTransitionError(Exception):
    def __init__(self) -> None:
        super().__init__("Import job status transition is not allowed.")


class InvalidImportJobCountersError(Exception):
    def __init__(self) -> None:
        super().__init__("Import job counters are invalid.")


class IdempotencyConflictError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"Import job with idempotency key '{key}' already exists.")
