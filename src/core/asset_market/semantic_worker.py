"""Minimal spawned worker for bounded Asset Market semantic hashing."""
from __future__ import annotations

import json
import sys
import time
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows worker portability
    resource = None

from src.core.asset_market.semantic_contract import (
    PROTOCOL_VERSION,
    SemanticAccumulator,
)


def _object(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Semantic worker input must contain JSON objects.")
    return value


def main() -> int:
    started = time.perf_counter()
    cpu_started = time.process_time()
    input_bytes = 0
    header_line = sys.stdin.buffer.readline()
    input_bytes += len(header_line)
    header = _object(header_line.decode("utf-8"))
    if header.get("protocol") != PROTOCOL_VERSION:
        raise ValueError("Unsupported semantic worker protocol.")
    accumulator = SemanticAccumulator()
    for line in sys.stdin.buffer:
        input_bytes += len(line)
        if not line.strip():
            continue
        accumulator.update(_object(line.decode("utf-8")))
    expected = header.get("expected_asset_count")
    if not isinstance(expected, int) or expected < 0:
        raise ValueError("Expected asset count is invalid.")
    if accumulator.asset_count != expected:
        raise ValueError("Semantic worker asset count does not match the header.")
    identities = accumulator.result(header.get("valuation_schema"))
    peak_rss = None
    if resource is not None:
        peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    output = {
        "protocol": PROTOCOL_VERSION,
        "request_generation": header.get("request_generation"),
        "status": "ok",
        "digests": {
            "asset_universe": identities["asset_universe_digest"],
            "brain_semantic_output": identities["brain_semantic_output_digest"],
            "ownership_dependency": identities["ownership_dependency_digest"],
            "provider_evidence": identities["provider_evidence_digest"],
        },
        "asset_count": identities["asset_count"],
        "valuation_schema_version": identities["valuation_schema"],
        "timing": {
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "records": identities["asset_count"],
            "input_bytes": input_bytes,
            "cpu_ms": round((time.process_time() - cpu_started) * 1000, 3),
            "peak_rss_bytes": peak_rss,
        },
    }
    sys.stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1) from None
