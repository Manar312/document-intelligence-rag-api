import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = f"{BASE_URL}/api/v1/query"
REPORT = Path("scripts/rag_grounding_quality_report.json")

# Question with an expected factual answer.
QUESTION = "What is Retrieval-Augmented Generation (RAG)?"
EXPECTED_TERMS = {
    "retrieval", "document", "language", "model",
}
STOP_WORDS = {
    "this", "that", "with", "from", "have", "has", "are",
    "was", "were", "what", "when", "where", "which", "will",
    "would", "could", "should", "about", "into", "their",
    "them", "they", "then", "than", "your", "you", "the",
    "and", "for", "but", "not", "can", "its", "our", "use",
    "using", "used", "how", "why", "who", "does", "such",
}

def tokens(text):
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", text)
        if word.lower() not in STOP_WORDS
    }

def request_api():
    body = json.dumps({
        "question": QUESTION,
        "top_k": 5,
        "generate": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        return response.status, json.loads(response.read().decode("utf-8"))

def main():
    checks = []
    answer = ""
    sources = []
    error = None
    http_status = None

    def check(name, passed, details):
        checks.append({
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        })
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {details}")

    try:
        http_status, payload = request_api()
        data = payload.get("data", payload)
        answer = data.get("answer") or ""
        sources = data.get("sources") or []

        check(
            "API HTTP status",
            http_status == 200,
            f"HTTP {http_status}",
        )
        check(
            "Answer generated",
            isinstance(answer, str) and bool(answer.strip()),
            f"answer_length={len(answer)}",
        )
        check(
            "Sources retrieved",
            isinstance(sources, list) and len(sources) > 0,
            f"source_count={len(sources)}",
        )

        source_texts = [
            item.get("text", "")
            for item in sources
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        combined_context = " ".join(source_texts)
        answer_tokens = tokens(answer)
        context_tokens = tokens(combined_context)

        overlap = answer_tokens & context_tokens
        overlap_ratio = (
            len(overlap) / len(answer_tokens)
            if answer_tokens else 0.0
        )

        check(
            "Sources contain readable text",
            bool(context_tokens),
            f"context_tokens={len(context_tokens)}",
        )
        check(
            "Answer overlaps retrieved context",
            overlap_ratio >= 0.20,
            f"token_overlap={overlap_ratio:.1%}",
        )

        expected_found = sorted(
            term for term in EXPECTED_TERMS
            if term in answer.lower()
        )
        check(
            "Expected answer concepts present",
            len(expected_found) >= 2,
            f"matched={expected_found}",
        )

        valid_metadata = all(
            isinstance(item, dict)
            and item.get("document_id")
            and isinstance(item.get("text"), str)
            and item.get("text").strip()
            for item in sources
        )
        check(
            "Source metadata is present",
            valid_metadata,
            f"valid_sources={sum(1 for item in sources if isinstance(item, dict) and item.get('document_id') and isinstance(item.get('text'), str) and item.get('text').strip())}/{len(sources)}",
        )

    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
        check("API request", False, error)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        check("API request", False, error)

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "question": QUESTION,
        "endpoint": ENDPOINT,
        "http_status": http_status,
        "overall_status": (
            "PASS" if checks and all(c["status"] == "PASS" for c in checks)
            else "FAIL"
        ),
        "checks": checks,
        "answer": answer,
        "sources": sources,
        "error": error,
        "quality_note": (
            "Token overlap and expected terms are heuristic checks, not proof "
            "of semantic correctness or factual entailment. Review the answer "
            "against the source text for a true grounding judgment."
        ),
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    passed = sum(c["status"] == "PASS" for c in checks)
    failed = sum(c["status"] == "FAIL" for c in checks)

    print("\n" + "=" * 60)
    print(f"GROUNDING QUALITY: {report['overall_status']}")
    print(f"PASS: {passed} | FAIL: {failed}")
    print(f"Report: {REPORT.resolve()}")
    print("=" * 60)

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
