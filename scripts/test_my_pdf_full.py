from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REPORT = SCRIPTS / "my_pdf_full_test_report.json"

BASE_URL = "http://127.0.0.1:8000"
PROCESSING_TIMEOUT = 300
POLL_INTERVAL = 2

RESULTS = []
DOCUMENT_ID = None


def record(name, status, detail=""):
    RESULTS.append({
        "test": name,
        "status": status,
        "detail": str(detail),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[{status}] {name}: {detail}")


def passed(name, detail=""):
    record(name, "PASS", detail)


def failed(name, detail=""):
    record(name, "FAIL", detail)


def skipped(name, detail=""):
    record(name, "SKIP", detail)


def get_json(response):
    try:
        value = response.json()
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def get_data(response):
    data = get_json(response).get("data")
    return data if isinstance(data, dict) else {}


def tokens(text):
    return set(
        word.casefold()
        for word in re.findall(r"[^\W_]{3,}", text, flags=re.UNICODE)
    )


def run_existing_script(name, script_path):
    if not script_path.is_file():
        skipped(name, f"Script not found: {script_path}")
        return {
            "name": name,
            "status": "SKIP",
            "return_code": None,
        }

    print(f"\n{'=' * 65}")
    print(f"Running existing test: {script_path.name}")
    print("=" * 65)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )

        output = result.stdout or ""
        if result.stderr:
            output += "\n" + result.stderr

        print(output.strip() or "(No console output)")

        status = "PASS" if result.returncode == 0 else "FAIL"

        record(
            name,
            status,
            f"return_code={result.returncode}; "
            f"output_tail={output[-1500:]}",
        )

        return {
            "name": name,
            "status": status,
            "return_code": result.returncode,
            "output_tail": output[-4000:],
        }

    except subprocess.TimeoutExpired:
        failed(name, "Test exceeded the 900-second timeout.")
        return {
            "name": name,
            "status": "FAIL",
            "return_code": None,
        }

    except Exception as exc:
        failed(name, repr(exc))
        return {
            "name": name,
            "status": "FAIL",
            "return_code": None,
        }


def finish(suite_results=None):
    passed_count = sum(r["status"] == "PASS" for r in RESULTS)
    failed_count = sum(r["status"] == "FAIL" for r in RESULTS)
    skipped_count = sum(r["status"] == "SKIP" for r in RESULTS)

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS" if failed_count == 0 else "FAIL",
        "api_base_url": BASE_URL,
        "uploaded_document_id": DOCUMENT_ID,
        "summary": {
            "passed": passed_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "total": len(RESULTS),
        },
        "results": RESULTS,
        "existing_test_suites": suite_results or [],
        "limitations": [
            "Lexical overlap is a heuristic, not proof of factual correctness.",
            "Expected concepts are checked only when supplied by the user.",
            "Existing tests may use historical document IDs.",
            "OCR text extraction does not provide visual image understanding.",
        ],
    }

    try:
        SCRIPTS.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"\nCould not save report: {exc!r}")
        return 2

    print("\n" + "=" * 65)
    print("FINAL TEST SUMMARY")
    print("=" * 65)
    print(f"Overall: {report['overall_status']}")
    print(
        f"PASS: {passed_count} | FAIL: {failed_count} | "
        f"SKIP: {skipped_count} | TOTAL: {len(RESULTS)}"
    )

    if DOCUMENT_ID:
        print(f"Document ID: {DOCUMENT_ID}")

    print(f"Report: {REPORT}")

    return 0 if failed_count == 0 else 1


def main():
    global DOCUMENT_ID

    SCRIPTS.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("FULL PDF + RAG TEST")
    print("=" * 65)
    print(f"API: {BASE_URL}")
    print("Existing documents will not be deleted.\n")

    raw_path = input("Enter the full path to your PDF: ").strip()
    raw_path = raw_path.strip('"').strip()

    pdf_path = Path(raw_path).expanduser()

    if not pdf_path.is_absolute():
        pdf_path = (Path.cwd() / pdf_path).resolve()

    if not pdf_path.is_file():
        failed("PDF file exists", f"File not found: {pdf_path}")
        return finish()

    if pdf_path.suffix.lower() != ".pdf":
        failed("PDF extension", f"Expected .pdf; got {pdf_path.suffix}")
        return finish()

    if pdf_path.stat().st_size == 0:
        failed("PDF is non-empty", "File size is zero.")
        return finish()

    passed(
        "PDF file validation",
        f"name={pdf_path.name}; size={pdf_path.stat().st_size} bytes",
    )

    question = input(
        "\nWrite a question whose answer should be inside this PDF: "
    ).strip()

    if not question:
        question = (
            "Summarize the main topic of this document and its key points."
        )
        print(f"Using default question: {question}")

    expected_input = input(
        "Expected keywords/concepts separated by commas "
        "(press Enter to skip): "
    ).strip()

    expected_terms = [
        term.strip().casefold()
        for term in expected_input.split(",")
        if term.strip()
    ]

    try:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0)
        ) as client:

            # --------------------------------------------------
            # 1. API health
            # --------------------------------------------------

            for endpoint, label in [
                ("/api/v1/health/live", "API liveness"),
                ("/api/v1/health/ready", "API readiness"),
            ]:
                try:
                    response = client.get(BASE_URL + endpoint)
                    payload = get_json(response)

                    if (
                        response.status_code == 200
                        and payload.get("success") is True
                    ):
                        passed(label, f"HTTP {response.status_code}")
                    else:
                        failed(
                            label,
                            f"HTTP {response.status_code}: "
                            f"{response.text[:500]}",
                        )
                except Exception as exc:
                    failed(label, repr(exc))
                    return finish()

            # --------------------------------------------------
            # 2. Invalid file extension
            # --------------------------------------------------

            try:
                response = client.post(
                    f"{BASE_URL}/api/v1/documents",
                    files={
                        "file": (
                            "invalid.exe",
                            b"not a supported document",
                            "application/octet-stream",
                        )
                    },
                )

                if response.status_code == 400:
                    passed(
                        "Unsupported extension rejected",
                        "HTTP 400",
                    )
                else:
                    failed(
                        "Unsupported extension rejected",
                        f"Expected HTTP 400, got "
                        f"{response.status_code}: {response.text[:400]}",
                    )

            except Exception as exc:
                failed("Unsupported extension rejected", repr(exc))

            # --------------------------------------------------
            # 3. Upload selected PDF
            # --------------------------------------------------

            print("\nUploading your PDF...")

            try:
                with pdf_path.open("rb") as pdf_file:
                    response = client.post(
                        f"{BASE_URL}/api/v1/documents",
                        files={
                            "file": (
                                pdf_path.name,
                                pdf_file,
                                "application/pdf",
                            )
                        },
                        timeout=httpx.Timeout(120.0, connect=10.0),
                    )

                data = get_data(response)
                DOCUMENT_ID = data.get("id")

                if response.status_code == 201 and DOCUMENT_ID:
                    DOCUMENT_ID = str(DOCUMENT_ID)
                    passed(
                        "PDF upload",
                        f"HTTP 201; id={DOCUMENT_ID}; "
                        f"status={data.get('status')}",
                    )
                else:
                    failed(
                        "PDF upload",
                        f"HTTP {response.status_code}: "
                        f"{response.text[:1000]}",
                    )
                    return finish()

            except Exception as exc:
                failed("PDF upload", repr(exc))
                return finish()

            # --------------------------------------------------
            # 4. Background processing
            # --------------------------------------------------

            print("\nWaiting for document processing...")

            deadline = time.monotonic() + PROCESSING_TIMEOUT
            document = {}
            status = "unknown"

            while time.monotonic() < deadline:
                try:
                    response = client.get(
                        f"{BASE_URL}/api/v1/documents/{DOCUMENT_ID}",
                        timeout=10.0,
                    )

                    if response.status_code == 200:
                        document = get_data(response)
                        status = str(
                            document.get("status", "unknown")
                        ).lower()

                        print(f"  Current status: {status}")

                        if status in {"indexed", "failed"}:
                            break
                    else:
                        print(
                            f"  Status request returned "
                            f"HTTP {response.status_code}"
                        )

                except Exception as exc:
                    print(f"  Polling error: {exc!r}")

                time.sleep(POLL_INTERVAL)

            if status == "indexed":
                passed(
                    "Background processing",
                    "Document reached indexed status.",
                )

            elif status == "failed":
                failed(
                    "Background processing",
                    json.dumps(document, ensure_ascii=False)[:1200],
                )

            else:
                failed(
                    "Background processing",
                    f"Timeout after {PROCESSING_TIMEOUT}s; "
                    f"last status={status}. Check Celery worker and broker.",
                )

            if status != "indexed":
                for test_name in [
                    "Extracted pages and text",
                    "Chunks and metadata",
                    "Retrieval without generation",
                    "RAG answer generation",
                    "Answer source provenance",
                    "Answer/source overlap",
                    "Expected concepts",
                    "Invalid query validation",
                ]:
                    skipped(test_name, "Document was not indexed.")

            else:
                # ----------------------------------------------
                # 5. Pages and extracted text
                # ----------------------------------------------

                response = client.get(
                    f"{BASE_URL}/api/v1/documents/{DOCUMENT_ID}/pages"
                )

                payload = get_json(response)
                pages = payload.get("data")

                if (
                    response.status_code == 200
                    and payload.get("success") is True
                    and isinstance(pages, list)
                    and len(pages) > 0
                ):
                    nonempty_pages = [
                        page for page in pages
                        if isinstance(page, dict)
                        and str(page.get("text", "")).strip()
                    ]

                    extracted_text = "\n".join(
                        str(page.get("text", ""))
                        for page in pages
                        if isinstance(page, dict)
                    )

                    methods = sorted({
                        str(page.get("extraction_method", "unknown"))
                        for page in pages
                        if isinstance(page, dict)
                    })

                    if nonempty_pages:
                        passed(
                            "Extracted pages and text",
                            f"pages={len(pages)}; "
                            f"nonempty={len(nonempty_pages)}; "
                            f"characters={len(extracted_text)}; "
                            f"methods={methods}",
                        )
                    else:
                        failed(
                            "Extracted pages and text",
                            "Pages returned but all page text is empty.",
                        )

                else:
                    extracted_text = ""
                    failed(
                        "Extracted pages and text",
                        f"HTTP {response.status_code}: "
                        f"{response.text[:800]}",
                    )

                # ----------------------------------------------
                # 6. Chunks and metadata
                # ----------------------------------------------

                response = client.get(
                    f"{BASE_URL}/api/v1/documents/{DOCUMENT_ID}/chunks"
                )

                payload = get_json(response)
                chunks = payload.get("data")

                if (
                    response.status_code == 200
                    and payload.get("success") is True
                    and isinstance(chunks, list)
                    and chunks
                ):
                    valid_chunks = [
                        chunk for chunk in chunks
                        if isinstance(chunk, dict)
                        and str(chunk.get("text", "")).strip()
                        and chunk.get("document_id") == DOCUMENT_ID
                        and isinstance(chunk.get("page_number"), int)
                        and chunk["page_number"] >= 1
                    ]

                    if len(valid_chunks) == len(chunks):
                        passed(
                            "Chunks and metadata",
                            f"chunks={len(chunks)}; "
                            "all chunks have text and valid document/page metadata",
                        )
                    else:
                        failed(
                            "Chunks and metadata",
                            f"total={len(chunks)}; valid={len(valid_chunks)}",
                        )

                else:
                    chunks = []
                    failed(
                        "Chunks and metadata",
                        f"HTTP {response.status_code}: "
                        f"{response.text[:800]}",
                    )

                # ----------------------------------------------
                # 7. Retrieval only (LLM disabled)
                # ----------------------------------------------

                query = {
                    "question": question,
                    "top_k": 5,
                    "document_id": DOCUMENT_ID,
                    "generate": False,
                }

                response = client.post(
                    f"{BASE_URL}/api/v1/query",
                    json=query,
                    timeout=90.0,
                )

                query_data = get_data(response)
                sources = query_data.get("sources")

                if (
                    response.status_code == 200
                    and isinstance(sources, list)
                    and sources
                ):
                    valid_sources = [
                        source for source in sources
                        if isinstance(source, dict)
                        and source.get("document_id") == DOCUMENT_ID
                        and str(source.get("text", "")).strip()
                    ]

                    if len(valid_sources) == len(sources):
                        passed(
                            "Retrieval without generation",
                            f"sources={len(sources)}; "
                            "all sources belong to this PDF",
                        )
                    else:
                        failed(
                            "Retrieval without generation",
                            f"total={len(sources)}; "
                            f"valid={len(valid_sources)}",
                        )

                elif response.status_code == 200:
                    failed(
                        "Retrieval without generation",
                        "HTTP 200 but no sources returned.",
                    )

                else:
                    failed(
                        "Retrieval without generation",
                        f"HTTP {response.status_code}: "
                        f"{response.text[:800]}",
                    )

                # ----------------------------------------------
                # 8. Generate answer using LLM
                # ----------------------------------------------

                query["generate"] = True

                response = client.post(
                    f"{BASE_URL}/api/v1/query",
                    json=query,
                    timeout=180.0,
                )

                answer_data = get_data(response)
                answer = str(answer_data.get("answer") or "").strip()
                answer_sources = answer_data.get("sources")
                generation_status = answer_data.get(
                    "generation_status", "unknown"
                )

                if response.status_code == 200 and answer:
                    passed(
                        "RAG answer generation",
                        f"answer_chars={len(answer)}; "
                        f"generation_status={generation_status}",
                    )
                else:
                    failed(
                        "RAG answer generation",
                        f"HTTP {response.status_code}; "
                        f"generation_status={generation_status}; "
                        f"body={response.text[:800]}",
                    )

                # ----------------------------------------------
                # 9. Source provenance
                # ----------------------------------------------

                if isinstance(answer_sources, list) and answer_sources:
                    valid_sources = [
                        source for source in answer_sources
                        if isinstance(source, dict)
                        and source.get("document_id") == DOCUMENT_ID
                        and str(source.get("text", "")).strip()
                    ]

                    if len(valid_sources) == len(answer_sources):
                        passed(
                            "Answer source provenance",
                            f"all {len(answer_sources)} sources belong "
                            "to the uploaded PDF",
                        )
                    else:
                        failed(
                            "Answer source provenance",
                            f"total={len(answer_sources)}; "
                            f"valid={len(valid_sources)}",
                        )
                else:
                    failed(
                        "Answer source provenance",
                        "No sources were returned with the generated answer.",
                    )

                # ----------------------------------------------
                # 10. Lexical overlap diagnostic
                # ----------------------------------------------

                source_text = " ".join(
                    str(source.get("text", ""))
                    for source in (
                        answer_sources
                        if isinstance(answer_sources, list)
                        else []
                    )
                    if isinstance(source, dict)
                )

                answer_tokens = tokens(answer)
                source_tokens = tokens(source_text)

                if answer_tokens:
                    overlap = (
                        len(answer_tokens & source_tokens)
                        / len(answer_tokens)
                    )

                    passed(
                        "Answer/source overlap diagnostic",
                        f"lexical overlap={overlap:.1%}; "
                        "this is not proof of factual correctness",
                    )
                else:
                    skipped(
                        "Answer/source overlap diagnostic",
                        "No tokenizable words in answer.",
                    )

                # ----------------------------------------------
                # 11. User-supplied expected concepts
                # ----------------------------------------------

                if expected_terms:
                    matched = [
                        term for term in expected_terms
                        if term in answer.casefold()
                    ]

                    if matched:
                        passed(
                            "Expected concepts",
                            f"matched={matched}; expected={expected_terms}",
                        )
                    else:
                        failed(
                            "Expected concepts",
                            f"No expected concept found in answer; "
                            f"expected={expected_terms}",
                        )
                else:
                    skipped(
                        "Expected concepts",
                        "No expected concepts supplied.",
                    )

                # ----------------------------------------------
                # 12. Query input validation
                # ----------------------------------------------

                response = client.post(
                    f"{BASE_URL}/api/v1/query",
                    json={
                        "question": "",
                        "top_k": 5,
                        "generate": False,
                    },
                    timeout=30.0,
                )

                if response.status_code == 422:
                    passed(
                        "Invalid query validation",
                        "Empty question rejected with HTTP 422.",
                    )
                else:
                    failed(
                        "Invalid query validation",
                        f"Expected HTTP 422; received "
                        f"{response.status_code}: {response.text[:400]}",
                    )

    except Exception as exc:
        failed("Unexpected test runner exception", repr(exc))

    # ----------------------------------------------------------
    # 13. Existing project test suites
    # ----------------------------------------------------------

    suite_results = []

    suites = [
        (
            "Existing unit and API integration suite",
            SCRIPTS / "test_rag_full.py",
        ),
        (
            "Existing grounding quality suite",
            SCRIPTS / "test_rag_grounding_quality.py",
        ),
        (
            "Existing infrastructure and historical-ID checks",
            SCRIPTS / "run_all_checks.py",
        ),
    ]

    print("\nRunning existing project test suites...")

    for name, script_path in suites:
        suite_results.append(
            run_existing_script(name, script_path)
        )

    # ----------------------------------------------------------
    # 14. Optional cleanup: only this run's uploaded document
    # ----------------------------------------------------------

    if DOCUMENT_ID:
        choice = input(
            f"\nDelete only the document uploaded in this run "
            f"({DOCUMENT_ID}) and its indexed content? [y/N]: "
        ).strip().casefold()

        if choice in {"y", "yes"}:
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.delete(
                        f"{BASE_URL}/api/v1/documents/{DOCUMENT_ID}",
                        timeout=60.0,
                    )

                data = get_data(response)

                if (
                    response.status_code == 200
                    and data.get("deleted") is True
                ):
                    passed(
                        "Optional cleanup",
                        f"Deleted test document {DOCUMENT_ID}.",
                    )
                else:
                    failed(
                        "Optional cleanup",
                        f"HTTP {response.status_code}: "
                        f"{response.text[:800]}",
                    )

            except Exception as exc:
                failed("Optional cleanup", repr(exc))
        else:
            passed(
                "Cleanup decision",
                f"Retained test document {DOCUMENT_ID}; "
                "no document data was deleted.",
            )

    return finish(suite_results)


if __name__ == "__main__":
    raise SystemExit(main())
