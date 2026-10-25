from pathlib import Path
from typing import Any

from fastapi import UploadFile

from src.enums.document_status import DocumentStatus
from src.models.document_model import DocumentModel
from src.providers.local_storage_provider import LocalStorageProvider
from src.repositories.document_chunk_repository import DocumentChunkRepository
from src.repositories.document_content_repository import DocumentContentRepository
from src.repositories.document_repository import DocumentRepository
from src.tasks.document_tasks import process_document


class DocumentService:
    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".txt",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
    }

    def __init__(
        self,
        repository: DocumentRepository,
        storage: LocalStorageProvider,
        content_repository: DocumentContentRepository,
        parser: Any,
        chunk_repository: DocumentChunkRepository,
        chunker: Any,
        embedding_provider: Any,
        qdrant_provider: Any,
    ) -> None:
        # Preserve the existing dependency-injection constructor.
        self.repository = repository
        self.storage = storage
        self.content_repository = content_repository
        self.parser = parser
        self.chunk_repository = chunk_repository
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.qdrant_provider = qdrant_provider

    async def upload_document(
        self,
        upload_file: UploadFile,
    ) -> dict[str, Any]:
        filename = Path(upload_file.filename or "").name

        if not filename:
            raise ValueError("A filename is required.")

        extension = Path(filename).suffix.lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported file extension.")

        content_type = (
            upload_file.content_type
            or "application/octet-stream"
        )

        storage_path, size_bytes = await self.storage.save(
            upload_file
        )

        document = DocumentModel(
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            status=DocumentStatus.QUEUED,
        )

        try:
            saved = await self.repository.create(document)
        except Exception:
            # Avoid leaving an unregistered file if Mongo insert fails.
            Path(storage_path).unlink(missing_ok=True)
            raise

        document_id = saved["id"]

        try:
            process_document.delay(document_id)
        except Exception as exc:
            await self.repository.update_status(
                document_id,
                DocumentStatus.FAILED.value,
                f"Could not enqueue processing task: {str(exc)[:800]}",
            )
            raise RuntimeError(
                "Document was saved but background processing "
                "could not be queued."
            ) from exc

        result = (
            await self.repository.get_by_id(document_id)
            or saved
        )
        result["page_count"] = None
        result["chunk_count"] = None

        return result

    async def get_document(
        self,
        document_id: str,
    ) -> dict[str, Any] | None:
        return await self.repository.get_by_id(document_id)

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return await self.repository.list_documents(
            skip=skip,
            limit=limit,
        )

    async def get_pages(
        self,
        document_id: str,
    ) -> list[dict[str, Any]]:
        return await self.content_repository.get_pages(
            document_id
        )

    async def get_chunks(
        self,
        document_id: str,
    ) -> list[dict[str, Any]]:
        return await self.chunk_repository.list_for_document(
            document_id
        )

    async def delete_document(
        self,
        document_id: str,
    ) -> bool:
        document = await self.repository.get_by_id(document_id)

        if document is None:
            return False

        await self.repository.update_status(
            document_id,
            DocumentStatus.DELETING.value,
        )

        self.qdrant_provider.delete_document(document_id)

        await self.content_repository.delete_for_document(
            document_id
        )
        await self.chunk_repository.delete_for_document(
            document_id
        )

        Path(document["storage_path"]).unlink(missing_ok=True)
        await self.repository.delete(document_id)

        return True
