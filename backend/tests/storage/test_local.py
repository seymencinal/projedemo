from hashlib import sha256
from pathlib import Path

import pytest

from app.exceptions.storage import (
    ContentTypeMismatchError,
    EmptyUploadError,
    StoredFileNotFoundError,
    UnsafeStoragePathError,
    UnsupportedContentTypeError,
    UnsupportedFileExtensionError,
    UploadTooLargeError,
)
from app.storage.local import LocalFileStorage


def storage(tmp_path: Path, maximum: int = 10) -> LocalFileStorage:
    return LocalFileStorage(tmp_path / "uploads", maximum)


def test_saves_csv_streams_chunks_and_calculates_checksum(tmp_path: Path) -> None:
    value = storage(tmp_path).save("report.csv", "text/csv", [b"a,", b"b\n1,2\n"])

    assert value.stored_filename.endswith(".csv")
    assert value.stored_filename != "report.csv"
    assert value.size_bytes == 8
    assert value.checksum_sha256 == sha256(b"a,b\n1,2\n").hexdigest()
    assert storage(tmp_path).open(value.storage_path).read() == b"a,b\n1,2\n"


def test_saves_xlsx_generates_unique_names_and_supports_lifecycle(tmp_path: Path) -> None:
    target = storage(tmp_path)
    first = target.save("source.xlsx", "application/vnd.ms-excel", [b"one"])
    second = target.save("source.xlsx", "application/vnd.ms-excel", [b"two"])

    assert first.stored_filename != second.stored_filename
    assert target.exists(first.storage_path)
    target.delete(first.storage_path)
    assert not target.exists(first.storage_path)
    with pytest.raises(StoredFileNotFoundError):
        target.delete(first.storage_path)


@pytest.mark.parametrize(
    ("filename", "content_type", "error"),
    [
        ("../report.csv", "text/csv", UnsafeStoragePathError),
        ("report.txt", "text/csv", UnsupportedFileExtensionError),
        ("report.csv", "image/png", UnsupportedContentTypeError),
        ("report.csv", "application/vnd.ms-excel", ContentTypeMismatchError),
    ],
)
def test_rejects_unsafe_or_incompatible_upload_metadata(
    tmp_path: Path, filename: str, content_type: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        storage(tmp_path).save(filename, content_type, [b"data"])


def test_rejects_empty_oversized_and_escaping_paths_with_cleanup(tmp_path: Path) -> None:
    target = storage(tmp_path, maximum=3)
    with pytest.raises(EmptyUploadError):
        target.save("empty.csv", "application/csv", [])
    with pytest.raises(UploadTooLargeError):
        target.save("large.csv", "application/csv", [b"12", b"34"])
    assert list((tmp_path / "uploads").iterdir()) == []
    with pytest.raises(UnsafeStoragePathError):
        target.resolve("../escape.csv")
    with pytest.raises(StoredFileNotFoundError):
        target.open("missing.csv")
