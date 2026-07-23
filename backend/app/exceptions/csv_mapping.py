class UnknownCanonicalFieldError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV mapping contains an unsupported canonical field.")


class MissingRequiredCanonicalFieldError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV mapping must include the required content field.")


class DuplicateSourceColumnError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV mapping cannot map one source column more than once.")


class BlankSourceColumnError(Exception):
    def __init__(self) -> None:
        super().__init__("CSV mapping source columns cannot be blank.")
