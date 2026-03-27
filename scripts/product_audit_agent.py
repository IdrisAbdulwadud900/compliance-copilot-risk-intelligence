from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
APP_DIR = ROOT / "app"
PYTHON_BIN = ROOT / ".venv" / "bin" / "python"
LOCAL_BACKEND = "http://127.0.0.1:8000"
LOCAL_FRONTEND = "http://127.0.0.1:3000"
PROD_BACKEND = "https://backend-eta-nine-57.vercel.app"
PROD_FRONTEND = "https://app-eight-sable-60.vercel.app"


@dataclass
class SectionResult:
    name: str
    passed: bool
    score: int
    max_score: int
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class AuditReport:
    score: int
    max_score: int
    grade: str
    verdict: str
    would_charge_1k_today: bool
    brutal_truth: str
    critical_blockers: List[str]
    sections: List[SectionResult]


def run_command(command: Sequence[str], cwd: Optional[Path] = None, timeout: int = 600) -> Tuple[int, str, str]:
    process = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return process.returncode, process.stdout, process.stderr


def fetch_json(url: str, timeout: int = 15) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "ComplianceCopilotAudit/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_status(url: str, timeout: int = 15) -> Tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "ComplianceCopilotAudit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def grade_for(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score else 0.0
    if ratio >= 0.9:
        return "A"
    if ratio >= 0.8:
        return "B"
    if ratio >= 0.65:
        return "C"
    if ratio >= 0.5:
        return "D"
    return "F"


def shorten_text(value: str, max_lines: int = 20, max_chars_per_line: int = 220) -> str:
    shortened_lines: List[str] = []
    for line in value.strip().splitlines()[:max_lines]:
        if len(line) > max_chars_per_line:
            shortened_lines.append(f"{line[:max_chars_per_line].rstrip()}...")
        else:
            shortened_lines.append(line)
    return "\n".join(shortened_lines)


def docs_section() -> SectionResult:
    required = {
        "README.md": ROOT / "README.md",
        "API.md": ROOT / "API.md",
        "ARCHITECTURE.md": ROOT / "ARCHITECTURE.md",
        "DEPLOY.md": ROOT / "DEPLOY.md",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    keywords = [
        "prototype",
        "What the product does",
        "Real-wallet testing",
        "If you want outside testers",
        "Important production note",
    ]
    missing_keywords = [keyword for keyword in keywords if keyword not in readme_text]
    passed = not missing and not missing_keywords
    score = 10 if passed else max(0, 10 - len(missing) * 3 - len(missing_keywords))
    recommendations: List[str] = []
    if missing:
        recommendations.append(f"Add missing docs: {', '.join(missing)}")
    if missing_keywords:
        recommendations.append(f"README is missing key onboarding sections: {', '.join(missing_keywords)}")
    summary = "GitHub docs clearly explain the product and tester flow." if passed else "Repository docs are incomplete or weak for tester onboarding."
    return SectionResult(
        name="docs",
        passed=passed,
        score=score,
        max_score=10,
        summary=summary,
        evidence={"missing_files": missing, "missing_readme_sections": missing_keywords},
        recommendations=recommendations,
    )


def local_stack_section() -> SectionResult:
    code, stdout, stderr = run_command(["bash", "scripts/status_local.sh"], cwd=ROOT, timeout=30)
    backend_ok = "backend.http=ok" in stdout
    frontend_ok = "frontend.http=ok" in stdout
    passed = code == 0 and backend_ok and frontend_ok
    score = 10 if passed else (5 if backend_ok or frontend_ok else 0)
    summary = "Local backend and frontend are both reachable." if passed else "Local stack is not fully healthy."
    recommendations: List[str] = []
    if not backend_ok:
        recommendations.append("Start or fix the local backend before relying on QA checks.")
    if not frontend_ok:
        recommendations.append("Start or fix the local frontend before running UI-based testing.")
    return SectionResult(
        name="local_stack",
        passed=passed,
        score=score,
        max_score=10,
        summary=summary,
        evidence={"status_output": shorten_text(stdout), "stderr": shorten_text(stderr, max_lines=10)},
        recommendations=recommendations,
    )


def backend_tests_section() -> SectionResult:
    code, stdout, stderr = run_command([str(PYTHON_BIN), "-m", "pytest", "tests", "-q"], cwd=BACKEND_DIR, timeout=1200)
    passed = code == 0
    score = 20 if passed else 0
    summary = "Backend test suite passes." if passed else "Backend tests are failing."
    return SectionResult(
        name="backend_tests",
        passed=passed,
        score=score,
        max_score=20,
        summary=summary,
        evidence={"stdout_tail": "\n".join(stdout.strip().splitlines()[-15:]), "stderr_tail": "\n".join(stderr.strip().splitlines()[-15:])},
        recommendations=[] if passed else ["Fix failing backend tests before trusting new product claims."],
    )


def frontend_build_section() -> SectionResult:
    code, stdout, stderr = run_command(["npm", "run", "build"], cwd=APP_DIR, timeout=1200)
    passed = code == 0
    score = 10 if passed else 0
    summary = "Frontend production build passes." if passed else "Frontend build fails."
    return SectionResult(
        name="frontend_build",
        passed=passed,
        score=score,
        max_score=10,
        summary=summary,
        evidence={"stdout_tail": "\n".join(stdout.strip().splitlines()[-20:]), "stderr_tail": "\n".join(stderr.strip().splitlines()[-20:])},
        recommendations=[] if passed else ["Fix the frontend build before sharing the product with testers."],
    )


def parse_json_from_output(output: str) -> Any:
    decoder = json.JSONDecoder()
    for index, char in enumerate(output):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(output[index:])
            return payload
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON payload found in command output")


def real_wallet_section() -> SectionResult:
    code, stdout, stderr = run_command([str(PYTHON_BIN), "scripts/real_wallet_qa.py"], cwd=ROOT, timeout=1200)
    payload: Dict[str, Any] = {}
    try:
        parsed = parse_json_from_output(stdout)
        if isinstance(parsed, dict):
            payload = parsed
        else:
            payload = {"parsed_payload": parsed, "raw_stdout": stdout, "raw_stderr": stderr}
    except Exception:
        payload = {"raw_stdout": stdout, "raw_stderr": stderr}
    failures = payload.get("failures", []) if isinstance(payload, dict) else []
    result_count = len(payload.get("results", [])) if isinstance(payload, dict) else 0
    passed = code == 0 and not failures and result_count > 0
    score = 20 if passed else (8 if result_count > 0 else 0)
    summary = "Real Ethereum wallet and workflow QA passed." if passed else "Real wallet workflow QA is failing or incomplete."
    recommendations: List[str] = []
    if not passed:
        recommendations.append("Fix real-wallet QA failures before claiming live workflow reliability.")
    return SectionResult(
        name="real_wallet_qa",
        passed=passed,
        score=score,
        max_score=20,
        summary=summary,
        evidence={"payload": payload},
        recommendations=recommendations,
    )


def cross_chain_section() -> SectionResult:
    code, stdout, stderr = run_command([str(PYTHON_BIN), "scripts/cross_chain_wallet_qa_tmp.py"], cwd=ROOT, timeout=1200)
    payload: List[Dict[str, Any]] = []
    try:
        parsed = parse_json_from_output(stdout)
        if isinstance(parsed, list):
            payload = parsed
    except Exception:
        payload = []
    passed_count = len([item for item in payload if item.get("passed")])
    passed = code == 0 and bool(payload) and passed_count == len(payload)
    score = 15 if passed else min(10, passed_count * 2)
    summary = "Cross-chain QA passes for the currently supported workflow paths." if passed else "Cross-chain coverage is still uneven or failing in QA."
    recommendations: List[str] = []
    if passed:
        recommendations.append("Be honest that non-Ethereum chains are still more analyst-driven than fully live.")
    else:
        recommendations.append("Tighten cross-chain behavior before using multi-chain coverage as a premium sales claim.")
    return SectionResult(
        name="cross_chain_qa",
        passed=passed,
        score=score,
        max_score=15,
        summary=summary,
        evidence={"payload": payload, "stderr_tail": "\n".join(stderr.strip().splitlines()[-10:])},
        recommendations=recommendations,
    )


def production_section() -> SectionResult:
    health = fetch_json(f"{PROD_BACKEND}/health")
    ready = fetch_json(f"{PROD_BACKEND}/ready")
    frontend_status, _ = fetch_status(PROD_FRONTEND)
    critical = []
    if ready.get("status") != "ok":
        critical.append("production_ready_not_ok")
    warnings = list(ready.get("warnings", []))
    if "ephemeral_sqlite_storage" in warnings:
        critical.append("ephemeral_storage")
    if health.get("database", {}).get("persistence") == "ephemeral":
        critical.append("ephemeral_persistence")
    passed = frontend_status == 200 and health.get("status") == "ok" and not critical
    score = 15
    if ready.get("status") != "ok":
        score -= 6
    if "ephemeral_sqlite_storage" in warnings:
        score -= 6
    if frontend_status != 200:
        score -= 3
    score = max(0, score)
    summary = "Production is live, but persistence is not enterprise-safe yet." if critical else "Production health and readiness look strong."
    recommendations: List[str] = []
    if "ephemeral_storage" in critical or "ephemeral_persistence" in critical:
        recommendations.append("Set COMPLIANCE_DATABASE_URL to managed Postgres before asking customers to trust persistence.")
    return SectionResult(
        name="production",
        passed=passed,
        score=score,
        max_score=15,
        summary=summary,
        evidence={"health": health, "ready": ready, "frontend_status": frontend_status, "critical": critical},
        recommendations=recommendations,
    )


def build_report(sections: List[SectionResult]) -> AuditReport:
    total = sum(section.score for section in sections)
    max_total = sum(section.max_score for section in sections)
    grade = grade_for(total, max_total)
    critical_blockers: List[str] = []
    for section in sections:
        if section.name == "production":
            critical_blockers.extend(section.evidence.get("critical", []))
    if any(section.name == "backend_tests" and not section.passed for section in sections):
        critical_blockers.append("failing_backend_tests")
    if any(section.name == "frontend_build" and not section.passed for section in sections):
        critical_blockers.append("failing_frontend_build")

    would_charge_1k = total >= 75 and not critical_blockers
    if "ephemeral_storage" in critical_blockers or "ephemeral_persistence" in critical_blockers:
        brutal_truth = (
            "This feels like a serious prototype, not a trustworthy paid compliance system yet. "
            "The biggest trust killer is still ephemeral production storage."
        )
    elif total >= 75:
        brutal_truth = (
            "This is getting close to a real pilot-grade product, but pricing power still depends on data depth and tester trust."
        )
    else:
        brutal_truth = (
            "The workflow is promising, but buyers will still see this as a prototype until reliability and chain-depth gaps are closed."
        )

    verdict = (
        "Promising pilot prototype with real workflow value, but not yet a fully trustworthy production compliance platform."
        if critical_blockers
        else "Strong prototype with few obvious blockers."
    )

    return AuditReport(
        score=total,
        max_score=max_total,
        grade=grade,
        verdict=verdict,
        would_charge_1k_today=would_charge_1k,
        brutal_truth=brutal_truth,
        critical_blockers=critical_blockers,
        sections=sections,
    )


def print_human_report(report: AuditReport) -> None:
    print(f"Overall score: {report.score}/{report.max_score} ({report.grade})")
    print(f"Verdict: {report.verdict}")
    print(f"Would I charge $1k/month today? {'yes' if report.would_charge_1k_today else 'no'}")
    print(f"Brutal truth: {report.brutal_truth}")
    if report.critical_blockers:
        print("Critical blockers:")
        for blocker in report.critical_blockers:
            print(f"- {blocker}")
    print("\nSections:")
    for section in report.sections:
        print(f"- {section.name}: {section.score}/{section.max_score} | {'PASS' if section.passed else 'FAIL'} | {section.summary}")
        for recommendation in section.recommendations:
            print(f"  recommendation: {recommendation}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a blunt product audit for Compliance Copilot.")
    parser.add_argument("--json", action="store_true", help="Print the final report as JSON only.")
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit non-zero when the overall audit grade is below C.",
    )
    args = parser.parse_args()

    sections = [
        docs_section(),
        local_stack_section(),
        backend_tests_section(),
        frontend_build_section(),
        real_wallet_section(),
        cross_chain_section(),
        production_section(),
    ]
    report = build_report(sections)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print_human_report(report)
        print("\nJSON report:")
        print(json.dumps(asdict(report), indent=2))

    if args.strict_exit and (report.grade not in {"A", "B", "C"} or report.critical_blockers):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
