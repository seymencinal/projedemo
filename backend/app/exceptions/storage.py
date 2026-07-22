class UnsupportedFileExtensionError(Exception):
    pass


class UnsupportedContentTypeError(Exception):
    pass


class ContentTypeMismatchError(Exception):
    pass


class EmptyUploadError(Exception):
    pass


class UploadTooLargeError(Exception):
    pass


class UnsafeStoragePathError(Exception):
    pass


class StorageWriteError(Exception):
    pass


class StoredFileNotFoundError(Exception):
    pass
