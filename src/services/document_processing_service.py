import logging
from typing import Any

from src.core.config import Settings
from src.enums.document_status import DocumentStatus
from src.providers.document_parser_provider import DocumentParserProvider
from src.providers.embedding_provider import EmbeddingProvider
from src.providers.qdrant_provider import QdrantProvider
from src.repositories.document_chunk_repository import DocumentChunkRepository
from src.repositories.document_content_repository import DocumentContentRepository
from src.repositories.document_repository import DocumentRepository
from src.services.chunking_service import ChunkingService


logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Parse, chunk, embed, and index an existing document."""

    def __init__(
        self,
        database: Any,
        settings: Settings,
    ) -> None:
        self.repository = DocumentRepository(database)
        self.content_repository = DocumentContentRepository(database)
        self.chunk_repository = DocumentChunkRepository(database)

        self.parser = DocumentParserProvider()
        self.chunker = ChunkingService(
            settings.chunk_size,
            settings.chunk_overlap,
        )
        self.embedding_provider = EmbeddingProvider(
            settings.embedding_model,
            settings.embedding_dimensions,
        )
        self.qdrant_provider = QdrantProvider(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_dimensions,
        )

    async def process(
        self,
        document_id: str,
    ) -> dict[str, Any]:
        document = None

        try:
            document = await self.repository.get_by_id(document_id)
            if document is None:
                raise ValueError(
                    f"Document {document_id} was not found."
                )

            await self.repository.update_status(
                document_id,
                DocumentStatus.PROCESSING.value,
            )

            pages = self.parser.extract_pages(document["storage_path"])
            has_text = any(
                str(page.get("text", "")).strip()
                for page in pages
            )
            if not has_text:
                raise ValueError(
                    "No text could be extracted. "
                    "For image-heavy PDFs, verify OCR model setup."
                )

            await self.content_repository.save_pages(document_id, pages)

            chunks = self.chunker.chunk_pages(document_id, pages)
            if not chunks:
                raise ValueError(
                    "No chunks were produced from the extracted text."
                )

            await self.chunk_repository.replace_chunks(
                document_id,
                chunks,
            )

            self.qdrant_provider.ensure_collection()
            vectors = self.embedding_provider.embed_texts(
                [str(chunk["text"]) for chunk in chunks]
            )
            self.qdrant_provider.upsert_chunks(chunks, vectors)

            valid_chunk_indices = [
                int(chunk["chunk_index"])
                for chunk in chunks
            ]
            self.qdrant_provider.delete_stale_chunks(
                document_id,
                valid_chunk_indices,
            )

            updated = await self.repository.update_status(
                document_id,
                DocumentStatus.INDEXED.value,
                page_count=len(pages),
                chunk_count=len(chunks),
            )

            if updated is None:
                raise RuntimeError("Document status update failed.")

            return {
                "document_id": document_id,
                "status": DocumentStatus.INDEXED.value,
                "page_count": len(pages),
                "chunk_count": len(chunks),
            }

        except Exception as exc:
            if document is not None:
                try:
                    await self.repository.update_status(
                        document_id,
                        DocumentStatus.FAILED.value,
                        str(exc)[:1000],
                    )
                except Exception:
                    logger.exception(
                        "Could not mark document %s as failed.",
                        document_id,
                    )

            logger.exception(
                "Document processing failed for %s.",
                document_id,
            )
            raise

        finally:
            self.qdrant_provider.close()
