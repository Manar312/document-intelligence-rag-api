from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.exception_handlers import (
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.core.exceptions import AppException
from src.core.lifespan import lifespan
from src.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(settings.log_level)

    is_production = settings.environment == "production"

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug and not is_production,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )

    application.add_exception_handler(
        AppException,
        app_exception_handler,
    )

    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    application.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )

    application.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )

    application.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_app()
