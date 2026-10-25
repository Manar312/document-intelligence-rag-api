import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymongo import AsyncMongoClient

from src.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # Create the local upload directory.
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

    mongo_client = AsyncMongoClient(
        host=settings.mongo_host,
        port=settings.mongo_port,
        username=settings.mongo_app_username,
        password=settings.mongo_app_password.get_secret_value(),
        authSource=settings.mongo_auth_source,
        serverSelectionTimeoutMS=5000,
    )

    try:
        # Verify the MongoDB connection before starting the application.
        await mongo_client.admin.command("ping")

        app.state.mongo_client = mongo_client
        app.state.db = mongo_client[settings.mongo_database]

        logger.info(
            "MongoDB connected successfully to database '%s'",
            settings.mongo_database,
        )
        logger.info(
            "Starting %s in %s environment",
            settings.app_name,
            settings.environment,
        )

        yield

    except Exception:
        logger.exception("Application startup or runtime failed")
        raise

    finally:
        await mongo_client.close()
        logger.info("MongoDB connection closed")
