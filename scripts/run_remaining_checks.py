from pathlib import Path
import sys
import json
import asyncio

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from src.core.config import get_settings
from src.factories.llm_factory import create_llm_provider

results = []

DOCUMENT_ID = "800836a7-b766-4a05-9628-feb85c30f387"
UNKNOWN_DOCUMENT_ID = "00000000-0000-0000-0000-000000000000"


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({
        "test": name,
        "status": status,
        "detail": str(detail),
    })
    print(f"[{status}] {name}: {detail}")


def skip(name, detail):
    results.append({
        "test": name,
        "status": "SKIP",
        "detail": str(detail),
    })
    print(f"[SKIP] {name}: {detail}")


async def main():
    settings = get_settings()
    base_url = f"http://{settings.host}:{settings.port}"
    prefix = settings.api_v1_prefix

    print("\n=== Additional RAG Behavior and LLM Checks ===\n")

    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=90,
        ) as client:

            # 1. Retrieval restricted to a specific document.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "What is Retrieval-Augmented Generation?",
                    "top_k": 5,
                    "document_id": DOCUMENT_ID,
                    "generate": False,
                },
            )

            if response.status_code == 200:
                body = response.json()
                data = body.get("data") or {}
                sources = data.get("sources") or []
                correct_documents = all(
                    source.get("document_id") == DOCUMENT_ID
                    for source in sources
                )
                check(
                    "Document ID filtering",
                    body.get("success") is True
                    and len(sources) > 0
                    and correct_documents,
                    f"sources={len(sources)}, "
                    f"all_match_requested_document={correct_documents}",
                )
            else:
                check(
                    "Document ID filtering",
                    False,
                    f"HTTP {response.status_code}: {response.text[:250]}",
                )

            # 1.1 Retrieved sources should contain valid metadata.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "What is Retrieval-Augmented Generation?",
                    "top_k": 3,
                    "document_id": DOCUMENT_ID,
                    "generate": False,
                },
            )

            if response.status_code == 200:
                body = response.json()
                data = body.get("data") or {}
                sources = data.get("sources") or []

                valid_sources = bool(sources) and all(
                    isinstance(source.get("document_id"), str)
                    and source.get("document_id") == DOCUMENT_ID
                    and isinstance(source.get("chunk_index"), int)
                    and isinstance(source.get("page_number"), int)
                    and isinstance(source.get("score"), (int, float))
                    and isinstance(source.get("text"), str)
                    and bool(source.get("text", "").strip())
                    for source in sources
                )

                check(
                    "Retrieved sources contain valid metadata",
                    body.get("success") is True and valid_sources,
                    f"sources={len(sources)}, valid_metadata={valid_sources}",
                )
            else:
                check(
                    "Retrieved sources contain valid metadata",
                    False,
                    f"HTTP {response.status_code}: {response.text[:250]}",
                )
            # 1.2 top_k=1 should return at most one source.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "What is Retrieval-Augmented Generation?",
                    "top_k": 1,
                    "generate": False,
                },
            )
            if response.status_code == 200:
                body = response.json()
                data = body.get("data") or {}
                sources = data.get("sources") or []
                check(
                    "top_k=1 returns at most one source",
                    body.get("success") is True and len(sources) <= 1,
                    f"returned={len(sources)}",
                )
            else:
                check(
                    "top_k=1 returns at most one source",
                    False,
                    f"HTTP {response.status_code}: {response.text[:250]}",
                )

            # 1.3 generate=False should not invoke answer generation.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "What is Retrieval-Augmented Generation?",
                    "top_k": 3,
                    "document_id": DOCUMENT_ID,
                    "generate": False,
                },
            )
            if response.status_code == 200:
                body = response.json()
                data = body.get("data") or {}
                sources = data.get("sources") or []
                check(
                    "generate=False skips answer generation",
                    body.get("success") is True
                    and data.get("generation_status") == "not_requested"
                    and data.get("answer") is None
                    and len(sources) > 0,
                    f"status={data.get('generation_status')}, "
                    f"answer_is_none={data.get('answer') is None}, "
                    f"sources={len(sources)}",
                )
            else:
                check(
                    "generate=False skips answer generation",
                    False,
                    f"HTTP {response.status_code}: {response.text[:250]}",
                )

            # 1.4 Non-numeric top_k should be rejected by request validation.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "Test invalid top_k type",
                    "top_k": "many",
                    "generate": False,
                },
            )
            check(
                "Reject non-numeric top_k",
                response.status_code == 422,
                f"HTTP {response.status_code}",
            )

            # 1.5 Missing required question should be rejected.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "top_k": 3,
                    "generate": False,
                },
            )
            check(
                "Reject request without question",
                response.status_code == 422,
                f"HTTP {response.status_code}",
            )
            # 2. top_k limits the maximum number of returned sources.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "What is Retrieval-Augmented Generation?",
                    "top_k": 2,
                    "generate": False,
                },
            )

            if response.status_code == 200:
                body = response.json()
                sources = (body.get("data") or {}).get("sources") or []
                check(
                    "top_k limits results",
                    body.get("success") is True and len(sources) <= 2,
                    f"requested=2, returned={len(sources)}",
                )
            else:
                check(
                    "top_k limits results",
                    False,
                    f"HTTP {response.status_code}",
                )

            # 3. Unknown document should produce no relevant context.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "Explain document retrieval.",
                    "top_k": 5,
                    "document_id": UNKNOWN_DOCUMENT_ID,
                    "generate": False,
                },
            )

            if response.status_code == 200:
                body = response.json()
                data = body.get("data") or {}
                sources = data.get("sources") or []
                check(
                    "Unknown document returns no sources",
                    body.get("success") is True
                    and len(sources) == 0
                    and data.get("generation_status")
                    == "no_relevant_context",
                    f"sources={len(sources)}, "
                    f"status={data.get('generation_status')}",
                )
            else:
                check(
                    "Unknown document returns no sources",
                    False,
                    f"HTTP {response.status_code}: {response.text[:250]}",
                )

            # 4. top_k lower boundary.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "Test top_k lower boundary",
                    "top_k": 0,
                    "generate": False,
                },
            )
            check(
                "Reject top_k=0",
                response.status_code == 422,
                f"HTTP {response.status_code}",
            )

            # 5. top_k upper boundary.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "Test top_k upper boundary",
                    "top_k": 21,
                    "generate": False,
                },
            )
            check(
                "Reject top_k above 20",
                response.status_code == 422,
                f"HTTP {response.status_code}",
            )

            # 6. Whitespace-only question passes basic length validation
            # but should be rejected after stripping in RAGService.
            response = await client.post(
                f"{prefix}/query",
                json={
                    "question": "   ",
                    "generate": False,
                },
            )
            check(
                "Reject whitespace-only question",
                response.status_code == 400,
                f"HTTP {response.status_code}",
            )

            # 7. LLM configuration and generation.
            try:
                llm = create_llm_provider(settings)
                configured = bool(llm.is_configured)
            except Exception as exc:
                llm = None
                configured = False
                skip(
                    "LLM provider initialization",
                    f"{type(exc).__name__}: {exc}",
                )

            if llm is not None:
                check(
                    "LLM provider initialization",
                    True,
                    f"provider={settings.llm_provider}, "
                    f"configured={configured}",
                )

            if llm is not None and configured:
                response = await client.post(
                    f"{prefix}/query",
                    json={
                        "question": (
                            "According to the indexed documents, "
                            "what is Retrieval-Augmented Generation?"
                        ),
                        "top_k": 3,
                        "document_id": DOCUMENT_ID,
                        "generate": True,
                    },
                )

                if response.status_code == 200:
                    body = response.json()
                    data = body.get("data") or {}
                    answer = data.get("answer")
                    generated = (
                        body.get("success") is True
                        and data.get("generation_status") == "generated"
                        and isinstance(answer, str)
                        and bool(answer.strip())
                        and len(data.get("sources") or []) > 0
                    )
                    check(
                        "LLM generates an answer with sources",
                        generated,
                        f"status={data.get('generation_status')}, "
                        f"answer_nonempty={bool(answer and answer.strip())}, "
                        f"sources={len(data.get('sources') or [])}",
                    )
                    if answer:
                        print("  Answer preview:", answer[:300])
                else:
                    check(
                        "LLM generates an answer with sources",
                        False,
                        f"HTTP {response.status_code}: "
                        f"{response.text[:400]}",
                    )
            else:
                # Test the API's documented unconfigured-provider behavior.
                response = await client.post(
                    f"{prefix}/query",
                    json={
                        "question": "Explain retrieval.",
                        "document_id": DOCUMENT_ID,
                        "generate": True,
                    },
                )

                if response.status_code == 200:
                    body = response.json()
                    data = body.get("data") or {}
                    status = data.get("generation_status")
                    if status == "generated":
                        check(
                            "LLM generation/configuration branch",
                            bool(data.get("answer")),
                            "An answer was generated by the configured runtime provider.",
                        )
                    else:
                        check(
                            "LLM generation/configuration branch",
                            status == "llm_not_configured",
                            f"status={status}",
                        )
                else:
                    check(
                        "LLM generation/configuration branch",
                        False,
                        f"HTTP {response.status_code}: "
                        f"{response.text[:300]}",
                    )

    except Exception as exc:
        check(
            "Additional API checks completed",
            False,
            f"{type(exc).__name__}: {exc}",
        )

    print("\n=== ADDITIONAL CHECK REPORT ===")
    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    skipped = sum(r["status"] == "SKIP" for r in results)

    print(f"PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")

    report_path = PROJECT_ROOT / "scripts" / "remaining_check_report.json"
    report_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Report saved to: {report_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
