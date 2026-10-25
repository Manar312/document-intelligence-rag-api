import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import AppException
from src.enums.error_code import ErrorCode
from src.schemas.response_schema import (
    ErrorDetails,
    ErrorResponse,
)


logger = logging.getLogger(__name__)


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    response = ErrorResponse(
        message=exc.message,
        error=ErrorDetails(
            code=exc.code,
            details=exc.details,
        ),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json"),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "location": list(error.get("loc", ())),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]

    response = ErrorResponse(
        message="The request contains invalid data",
        error=ErrorDetails(
            code=ErrorCode.VALIDATION_ERROR,
            details=details,
        ),
    )

    return JSONResponse(
        status_code=422,
        content=response.model_dump(mode="json"),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    status_code_to_error_code = {
        401: ErrorCode.AUTHENTICATION_REQUIRED,
        403: ErrorCode.PERMISSION_DENIED,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        409: ErrorCode.RESOURCE_CONFLICT,
        413: ErrorCode.FILE_TOO_LARGE,
        415: ErrorCode.UNSUPPORTED_FILE_TYPE,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }

    code = status_code_to_error_code.get(
        exc.status_code,
        ErrorCode.HTTP_ERROR,
    )

    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else "The request could not be completed"
    )

    response = ErrorResponse(
        message=message,
        error=ErrorDetails(code=code),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json"),
        headers=exc.headers,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled application exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    response = ErrorResponse(
        message="An unexpected server error occurred",
        error=ErrorDetails(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
        ),
    )

    return JSONResponse(
        status_code=500,
        content=response.model_dump(mode="json"),
    )
