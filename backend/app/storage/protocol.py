from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class StoredFile:
    storage_path: str
    stored_filename: str
    size_bytes: int
    checksum_sha256: str


class FileStorage(Protocol):
    def save(
        self, original_filename: str, content_type: str, chunks: Iterable[bytes]
    ) -> StoredFile: ...

    def open(self, storage_path: str) -> BinaryIO: ...

    def delete(self, storage_path: str) -> None: ...

    def exists(self, storage_path: str) -> bool: ...

    def resolve(self, storage_path: str) -> Path: ...
