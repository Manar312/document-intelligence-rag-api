from typing import Any

from src.enums.error_code import ErrorCode


class AppException(Exception):
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        status_code: int,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
