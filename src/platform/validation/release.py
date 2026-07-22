"""Canonical, deterministic DTOS release validation pipeline."""
from __future__ import annotations

import subprocess
import sys
import json
import os
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from src.platform.validation.process_detection import processes_for_run, windows_process_inventory


@dataclass(frozen=True)
class ValidationStep:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    name: str
    duration_seconds: float


REQUIRED_DOCUMENTS = (
    "README.md", "CHANGELOG.md", "RELEASE_NOTES.md", "CONTRIBUTING.md",
    "docs/INSTALLATION.md", "docs/ARCHITECTURE.md", "docs/DEVELOPER_GUIDE.md",
    "docs/DEPLOYMENT.md", "docs/CONFIGURATION.md", "docs/VALIDATION.md",
    "docs/API_REFERENCE.md", "docs/MARKET_PROVIDER_GUIDE.md",
    "docs/INTELLIGENCE_PLATFORM.md", "docs/CACHING.md", "docs/RELEASE_PROCESS.md",
    "docs/TROUBLESHOOTING.md", "docs/VERSIONING.md", "docs/PRODUCTION_READINESS.md",
    "docs/VALIDATION_REPORT.md",
)

TRACE_FILE = Path(__file__).resolve().parents[3] / ".validation" / "validator_trace.jsonl"


def trace_event(event: str, **details: object) -> None:
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        **details,
    }
    with TRACE_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")


def validate_documentation(root: Path) -> None:
    missing = [path for path in REQUIRED_DOCUMENTS if not (root / path).is_file()]
    empty = [path for path in REQUIRED_DOCUMENTS if (root / path).is_file() and not (root / path).read_text(encoding="utf-8").strip()]
    if missing or empty:
        raise RuntimeError(f"Documentation validation failed; missing={missing}, empty={empty}")


def architecture_violations(root: Path) -> tuple[str, ...]:
    implementations = (
        "src.core.decision_engine", "src.core.asset_intelligence", "src.core.trade_intelligence",
        "src.core.front_office_intelligence", "src.core.market_intelligence",
    )
    violations = []
    for folder in ("services", "routes"):
        for path in (root / folder).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for package in implementations:
                if f"from {package}" in source or f"import {package}" in source:
                    violations.append(f"{path.relative_to(root)} imports {package}")
    return tuple(violations)


def default_steps() -> tuple[ValidationStep, ...]:
    python = sys.executable
    return (
        ValidationStep("Committed whitespace", ("git", "show", "--check", "--oneline", "--no-patch", "HEAD")),
        ValidationStep("Working-tree whitespace", ("git", "diff", "--check")),
        ValidationStep("Staged whitespace", ("git", "diff", "--cached", "--check")),
        ValidationStep("Python compilation", (python, "-m", "compileall", "-q", ".")),
        ValidationStep("Ruff", (python, "-m", "ruff", "check", ".")),
        ValidationStep("Dependency integrity", (python, "-m", "pip", "check")),
        ValidationStep("Unit and regression tests", (python, "-m", "unittest", "discover", "-s", "tests")),
        ValidationStep("Route and OpenAPI validation", (python, "-m", "tools.validation.validate_routes")),
        ValidationStep("Tracked HTTP smoke validation", (python, "-m", "tools.validation.run_http_validation")),
        ValidationStep("Process cleanup", (python, "-m", "tools.validation.process_check")),
    )


def startup_hygiene(root: Path, run_id: str) -> None:
    results = root / ".validation" / "results"
    stale_artifacts = list(results.glob("*.json")) if results.exists() else []
    stale_processes = [
        item for item in windows_process_inventory()
        if "--validation-run-id" in item.arguments and item not in processes_for_run(windows_process_inventory(), run_id)
    ]
    if stale_artifacts or stale_processes:
        raise RuntimeError(
            "Stale validation state detected before startup; "
            f"artifacts={[str(item) for item in stale_artifacts]}, processes={[item.pid for item in stale_processes]}"
        )


def run_release_validation(root: Path, run_id: str | None = None) -> tuple[ValidationResult, ...]:
    run_id = run_id or uuid4().hex
    trace_event("release_validation_start", root=str(root), run_id=run_id)
    startup_hygiene(root, run_id)
    validate_documentation(root)
    trace_event("documentation_validation_complete")
    violations = architecture_violations(root)
    if violations:
        raise RuntimeError("Architecture validation failed: " + "; ".join(violations))
    results = []
    for step in default_steps():
        started = perf_counter()
        trace_event("validation_step_launch", step=step.name, command=step.command, run_id=run_id)
        environment = os.environ.copy()
        environment["DTOS_VALIDATION_RUN_ID"] = run_id
        command = step.command
        if step.name == "Process cleanup":
            command = (*command, "--validation-run-id", run_id)
        child = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
        trace_event("validation_child_started", step=step.name, child_pid=child.pid)
        stdout, stderr = child.communicate()
        trace_event("validation_child_completed", step=step.name, child_pid=child.pid, return_code=child.returncode)
        completed = subprocess.CompletedProcess(step.command, child.returncode, stdout, stderr)
        if completed.returncode:
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            raise subprocess.CalledProcessError(completed.returncode, step.command)
        duration = round(perf_counter() - started, 3)
        results.append(ValidationResult(step.name, duration))
        detail = next((line for line in reversed(completed.stdout.splitlines()) if line.strip()), "")
        suffix = f" - {detail}" if detail else ""
        print(f"PASS {step.name}: {duration:.3f}s{suffix}", flush=True)
    trace_event("release_validation_complete", gates=len(results), run_id=run_id)
    return tuple(results)
