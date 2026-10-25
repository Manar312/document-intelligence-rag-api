from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock
from src.core.exceptions import AppException
from src.enums.error_code import ErrorCode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.rag_service import RAGService


class FakeEmbeddingProvider:
    def __init__(self):
        self.embed_query = Mock(return_value=[0.1, 0.2, 0.3])


class FakeQdrantProvider:
    def __init__(self, matches=None):
        self.matches = matches or []
        self.search = Mock(return_value=self.matches)


class FakeLLMProvider:
    def __init__(self, configured=True, answer="Answer from context."):
        self.is_configured = configured
        self.generate_answer = AsyncMock(return_value=answer)


def sample_matches():
    return [
        {
            "document_id": "doc-123",
            "chunk_index": 2,
            "page_number": 3,
            "score": 0.91,
            "text": "RAG combines retrieval with generation.",
            "extra_internal_field": "should not be returned",
        }
    ]


class TestRAGService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.embedding = FakeEmbeddingProvider()
        self.qdrant = FakeQdrantProvider(sample_matches())
        self.llm = FakeLLMProvider()

        self.service = RAGService(
            embedding_provider=self.embedding,
            qdrant_provider=self.qdrant,
            llm_provider=self.llm,
            default_top_k=5,
        )

    async def test_whitespace_question_is_rejected_before_retrieval(self):
        with self.assertRaisesRegex(ValueError, "Question cannot be empty"):
            await self.service.query("   ")

        self.embedding.embed_query.assert_not_called()
        self.qdrant.search.assert_not_called()
        self.llm.generate_answer.assert_not_called()

    async def test_no_matches_skips_llm(self):
        self.qdrant.search.return_value = []

        result = await self.service.query("Explain RAG")

        self.assertEqual(result["generation_status"], "no_relevant_context")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["sources"], [])
        self.llm.generate_answer.assert_not_called()

    async def test_generate_false_skips_llm(self):
        result = await self.service.query(
            "Explain RAG",
            generate=False,
        )

        self.assertEqual(result["generation_status"], "not_requested")
        self.assertIsNone(result["answer"])
        self.assertEqual(len(result["sources"]), 1)
        self.llm.generate_answer.assert_not_called()

    async def test_unconfigured_llm_returns_expected_status(self):
        self.llm.is_configured = False

        result = await self.service.query("Explain RAG")

        self.assertEqual(result["generation_status"], "llm_not_configured")
        self.assertIsNone(result["answer"])
        self.llm.generate_answer.assert_not_called()

    async def test_configured_llm_generates_answer(self):
        result = await self.service.query("Explain RAG")

        self.assertEqual(result["generation_status"], "generated")
        self.assertEqual(result["answer"], "Answer from context.")
        self.llm.generate_answer.assert_awaited_once()

    async def test_retrieval_receives_limit_and_document_filter(self):
        await self.service.query(
            "Explain RAG",
            top_k=3,
            document_id="doc-123",
            generate=False,
        )

        args, kwargs = self.qdrant.search.call_args
        self.assertEqual(kwargs["limit"], 3)
        self.assertEqual(kwargs["document_id"], "doc-123")
        self.assertEqual(args[0], [0.1, 0.2, 0.3])

    async def test_default_top_k_is_used_when_not_provided(self):
        await self.service.query("Explain RAG", generate=False)

        _, kwargs = self.qdrant.search.call_args
        self.assertEqual(kwargs["limit"], 5)

    async def test_question_is_stripped_before_embedding_and_response(self):
        result = await self.service.query(
            "  Explain RAG  ",
            generate=False,
        )

        self.embedding.embed_query.assert_called_once_with("Explain RAG")
        self.assertEqual(result["question"], "Explain RAG")

    async def test_sources_expose_expected_fields(self):
        result = await self.service.query(
            "Explain RAG",
            generate=False,
        )

        source = result["sources"][0]
        self.assertEqual(
            set(source.keys()),
            {
                "document_id",
                "chunk_index",
                "page_number",
                "score",
                "text",
            },
        )
        self.assertEqual(source["document_id"], "doc-123")
        self.assertEqual(source["page_number"], 3)

    async def test_llm_failure_returns_service_unavailable_error(self):
        self.llm.generate_answer.side_effect = RuntimeError(
            "simulated LLM failure"
        )

        with self.assertRaises(AppException) as context:
            await self.service.query("Explain RAG")

        self.assertEqual(
            context.exception.code,
            ErrorCode.SERVICE_UNAVAILABLE,
        )
        self.assertEqual(context.exception.status_code, 503)
        self.assertNotIn(
            "simulated LLM failure",
            context.exception.message,
        )
        self.llm.generate_answer.assert_awaited_once()
    async def test_embedding_failure_propagates_without_retrieval(self):
        self.embedding.embed_query.side_effect = RuntimeError(
            "simulated embedding failure"
        )

        with self.assertRaisesRegex(RuntimeError, "simulated embedding failure"):
            await self.service.query("Explain RAG")

        self.qdrant.search.assert_not_called()
        self.llm.generate_answer.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
