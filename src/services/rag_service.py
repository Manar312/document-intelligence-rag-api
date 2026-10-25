
import logging
from typing import Any

from src.core.exceptions import AppException
from src.enums.error_code import ErrorCode
from src.interfaces.llm_interface import LLMInterface
from src.providers.embedding_provider import EmbeddingProvider
from src.providers.qdrant_provider import QdrantProvider


logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        qdrant_provider: QdrantProvider,
        llm_provider: LLMInterface,
        default_top_k: int = 5,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.qdrant_provider = qdrant_provider
        self.llm_provider = llm_provider
        self.default_top_k = default_top_k

    async def query(
        self,
        question: str,
        top_k: int | None = None,
        document_id: str | None = None,
        generate: bool = True,
    ) -> dict[str, Any]:
        question = question.strip()

        if not question:
            raise ValueError("Question cannot be empty.")

        vector = self.embedding_provider.embed_query(question)

        matches = self.qdrant_provider.search(
            vector,
            limit=top_k or self.default_top_k,
            document_id=document_id,
        )

        answer = None
        generation_status = "not_requested"

        if not matches:
            generation_status = "no_relevant_context"

        elif generate and self.llm_provider.is_configured:
            try:
                answer = await self.llm_provider.generate_answer(
                    question,
                    matches,
                )
            except Exception as exc:
                logger.exception(
                    "LLM answer generation failed"
                )
                raise AppException(
                    message=(
                        "The language model service is temporarily "
                        "unavailable."
                    ),
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    status_code=503,
                ) from exc

            generation_status = "generated"

        elif generate:
            generation_status = "llm_not_configured"

        return {
            "question": question,
            "answer": answer,
            "generation_status": generation_status,
            "sources": [
                {
                    "document_id": item.get("document_id"),
                    "chunk_index": item.get("chunk_index"),
                    "page_number": item.get("page_number"),
                    "score": item.get("score"),
                    "text": item.get("text"),
                }
                for item in matches
            ],
        }
