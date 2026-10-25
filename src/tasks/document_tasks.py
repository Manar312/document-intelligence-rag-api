import asyncio
import logging

from src.tasks.celery_app import celery_app
from pymongo import AsyncMongoClient

from src.core.config import get_settings
from src.services.document_processing_service import (
    DocumentProcessingService,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="src.tasks.document_tasks.process_document",
    max_retries=3,
    default_retry_delay=10,
)
def process_document(self, document_id: str) -> dict:
    """Celery entry point for processing a document."""

    try:
        return asyncio.run(
            _process_document_async(document_id)
        )
    except Exception as exc:
        logger.exception(
            "Document processing failed for %s",
            document_id,
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        raise


async def _process_document_async(
    document_id: str,
) -> dict:
    settings = get_settings()

    client = AsyncMongoClient(
        host=settings.mongo_host,
        port=settings.mongo_port,
        username=settings.mongo_app_username,
        password=settings.mongo_app_password.get_secret_value(),
        authSource=settings.mongo_auth_source,
        serverSelectionTimeoutMS=5000,
    )

    try:
        await client.admin.command("ping")

        database = client[settings.mongo_database]

        processor = DocumentProcessingService(
            database,
            settings,
        )

        return await processor.process(document_id)

    finally:
        await client.close()
