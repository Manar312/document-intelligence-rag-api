from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIT_TEST = ROOT / "scripts" / "test_rag_service_unit.py"
API_TEST = ROOT / "scripts" / "run_remaining_checks.py"
API_REPORT = ROOT / "scripts" / "remaining_check_report.json"
OUTPUT_REPORT = ROOT / "scripts" / "rag_full_test_report.json"


def run_command(name: str, command: list[str]) -> dict:
    print(f"\n{'=' * 72}")
    print(f"RUNNING: {name}")
    print(f"{'=' * 72}")

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        errors="replace",
    )

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    return {
        "name": name,
        "return_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    checks = []
    unit_count = None
    api_counts = None

    if not UNIT_TEST.is_file():
        print(f"Missing unit test file: {UNIT_TEST}")
        return 2

    if not API_TEST.is_file():
        print(f"Missing API test file: {API_TEST}")
        return 2

    # 1. Unit tests: RAG service behavior and failure handling.
    unit = run_command(
        "RAG Service Unit Tests",
        [sys.executable, str(UNIT_TEST)],
    )
    unit_match = re.search(
        r"Ran\s+(\d+)\s+tests?",
        unit["stderr"] + "\n" + unit["stdout"],
    )
    if unit_match:
        unit_count = int(unit_match.group(1))

    unit["test_count"] = unit_count
    checks.append(unit)

    # 2. API integration tests: real running API, Qdrant and LLM.
    api = run_command(
        "RAG API Integration Tests",
        [sys.executable, str(API_TEST)],
    )

    api_text = api["stdout"] + "\n" + api["stderr"]
    api_match = re.search(
        r"PASS:\s*(\d+)\s*\|\s*FAIL:\s*(\d+)\s*\|\s*SKIP:\s*(\d+)",
        api_text,
    )

    if api_match:
        api_counts = {
            "passed": int(api_match.group(1)),
            "failed": int(api_match.group(2)),
            "skipped": int(api_match.group(3)),
        }

    api["counts"] = api_counts
    api["passed"] = (
        api["return_code"] == 0
        and api_counts is not None
        and api_counts["failed"] == 0
    )
    checks.append(api)

    # 3. Verify that the integration report exists and is readable.
    report_check = {
        "name": "Integration Report Validation",
        "passed": False,
        "details": None,
    }

    if API_REPORT.is_file():
        try:
            with API_REPORT.open("r", encoding="utf-8-sig") as file:
                saved_report = json.load(file)

            report_check["passed"] = isinstance(
                saved_report, (dict, list)
            )
            report_check["details"] = (
                "Report exists and contains valid JSON."
                if report_check["passed"]
                else "Unexpected report structure."
            )
        except (OSError, json.JSONDecodeError) as exc:
            report_check["details"] = (
                f"Could not read integration report: {exc}"
            )
    else:
        report_check["details"] = "Integration report was not created."

    checks.append(report_check)

    # Overall result: missing tests/reports or any failure means FAIL.
    overall_passed = all(check["passed"] for check in checks)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS" if overall_passed else "FAIL",
        "unit_test_count": unit_count,
        "api_test_counts": api_counts,
        "checks": [
            {
                "name": check["name"],
                "passed": check["passed"],
                "return_code": check.get("return_code"),
                "test_count": check.get("test_count"),
                "counts": check.get("counts"),
                "details": check.get("details"),
            }
            for check in checks
        ],
        "limitations": [
            "This runner aggregates existing unit and API integration tests.",
            "It does not independently prove semantic correctness or grounding.",
            "LLM output may vary between runs.",
        ],
    }

    with OUTPUT_REPORT.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 72}")
    print("FULL RAG TEST SUMMARY")
    print(f"{'=' * 72}")
    print(f"Overall status: {summary['overall_status']}")
    print(f"Unit tests: {unit_count if unit_count is not None else 'UNKNOWN'}")

    if api_counts:
        print(
            "API tests: "
            f"PASS={api_counts['passed']}, "
            f"FAIL={api_counts['failed']}, "
            f"SKIP={api_counts['skipped']}"
        )
    else:
        print("API test counts: UNKNOWN")

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']}")

    print(f"\nFull report saved to: {OUTPUT_REPORT}")

    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
