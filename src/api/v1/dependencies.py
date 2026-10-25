from fastapi import Request

from src.core.config import get_settings
from src.factories.llm_factory import create_llm_provider
from src.providers.document_parser_provider import DocumentParserProvider
from src.providers.embedding_provider import EmbeddingProvider
from src.providers.local_storage_provider import LocalStorageProvider
from src.providers.qdrant_provider import QdrantProvider
from src.repositories.document_chunk_repository import DocumentChunkRepository
from src.repositories.document_content_repository import DocumentContentRepository
from src.repositories.document_repository import DocumentRepository
from src.services.chunking_service import ChunkingService
from src.services.document_service import DocumentService
from src.services.rag_service import RAGService


def get_document_service(request: Request) -> DocumentService:
    settings = get_settings()
    database = request.app.state.db

    return DocumentService(
        repository=DocumentRepository(database),
        storage=LocalStorageProvider(
            settings.storage_dir,
            settings.max_upload_size_mb,
        ),
        content_repository=DocumentContentRepository(database),
        parser=DocumentParserProvider(),
        chunk_repository=DocumentChunkRepository(database),
        chunker=ChunkingService(
            settings.chunk_size,
            settings.chunk_overlap,
        ),
        embedding_provider=EmbeddingProvider(
            settings.embedding_model,
            settings.embedding_dimensions,
        ),
        qdrant_provider=QdrantProvider(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_dimensions,
        ),
    )


def get_rag_service() -> RAGService:
    settings = get_settings()

    return RAGService(
        embedding_provider=EmbeddingProvider(
            settings.embedding_model,
            settings.embedding_dimensions,
        ),
        qdrant_provider=QdrantProvider(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_dimensions,
        ),
        llm_provider=create_llm_provider(settings),
        default_top_k=settings.retrieval_top_k,
    )
