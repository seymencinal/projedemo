from uuid import UUID


class UploadedFileNotFoundError(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"Uploaded file with id '{item_id}' was not found.")


class UploadedFileConflictError(Exception):
    def __init__(self, checksum_sha256: str) -> None:
        super().__init__(f"Uploaded file with checksum '{checksum_sha256}' already exists.")


class InvalidUploadedFileTransitionError(Exception):
    def __init__(self) -> None:
        super().__init__("Uploaded file status transition is not allowed.")
