from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, ClassVar
from uuid import uuid4

from app.exceptions.storage import (
    ContentTypeMismatchError,
    EmptyUploadError,
    StorageWriteError,
    StoredFileNotFoundError,
    UnsafeStoragePathError,
    UnsupportedContentTypeError,
    UnsupportedFileExtensionError,
    UploadTooLargeError,
)
from app.storage.protocol import StoredFile


class LocalFileStorage:
    _extensions: ClassVar[set[str]] = {".csv", ".xlsx"}
    _content_types: ClassVar[dict[str, set[str]]] = {
        ".csv": {"text/csv", "application/csv", "application/octet-stream"},
        ".xlsx": {
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        },
    }

    def __init__(self, root: Path, max_size_bytes: int) -> None:
        self._root = root.resolve()
        self._max_size_bytes = max_size_bytes

    def save(
        self, original_filename: str, content_type: str, chunks: Iterable[bytes]
    ) -> StoredFile:
        extension = self._validate_upload(original_filename, content_type)
        self._root.mkdir(parents=True, exist_ok=True)
        stored_filename = f"{uuid4().hex}{extension}"
        target = self.resolve(stored_filename)
        digest = sha256()
        size_bytes = 0
        try:
            with target.open("xb") as handle:
                for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise StorageWriteError("Upload chunks must be bytes.")
                    size_bytes += len(chunk)
                    if size_bytes > self._max_size_bytes:
                        raise UploadTooLargeError("Upload exceeds the maximum configured size.")
                    digest.update(chunk)
                    handle.write(chunk)
            if size_bytes == 0:
                raise EmptyUploadError("Uploads cannot be empty.")
        except (EmptyUploadError, UploadTooLargeError, StorageWriteError):
            target.unlink(missing_ok=True)
            raise
        except OSError as error:
            target.unlink(missing_ok=True)
            raise StorageWriteError("Unable to write upload.") from error
        return StoredFile(stored_filename, stored_filename, size_bytes, digest.hexdigest())

    def open(self, storage_path: str) -> BinaryIO:
        target = self.resolve(storage_path)
        if not target.is_file():
            raise StoredFileNotFoundError(storage_path)
        return target.open("rb")

    def delete(self, storage_path: str) -> None:
        target = self.resolve(storage_path)
        if not target.is_file():
            raise StoredFileNotFoundError(storage_path)
        target.unlink()

    def exists(self, storage_path: str) -> bool:
        return self.resolve(storage_path).is_file()

    def resolve(self, storage_path: str) -> Path:
        candidate = (self._root / storage_path).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise UnsafeStoragePathError("Storage path must remain under the configured root.")
        return candidate

    def _validate_upload(self, original_filename: str, content_type: str) -> str:
        if not original_filename or not original_filename.strip():
            raise UnsafeStoragePathError("Upload filename is required.")
        if "/" in original_filename or "\\" in original_filename:
            raise UnsafeStoragePathError("Upload filename cannot contain path separators.")
        extension = Path(original_filename.strip()).suffix.lower()
        if extension not in self._extensions:
            raise UnsupportedFileExtensionError(extension)
        if content_type not in {item for values in self._content_types.values() for item in values}:
            raise UnsupportedContentTypeError(content_type)
        if content_type not in self._content_types[extension]:
            raise ContentTypeMismatchError(content_type)
        return extension
