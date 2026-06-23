class PlatformError(Exception):
    """Base platform error with user-safe code support."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        object.__setattr__(self, "code", code)
