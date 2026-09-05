"""Explicit, authenticated, bounded restart capture. Run inside production.

The inspection credential stays in the environment and is never serialized.
No provider synchronization, artifact loading, restart or publication is triggered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from time import monotonic
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener

from tools.validation.restart_evidence import differences, fingerprint, persist, snapshot
from tools.validation.smoke_http import _NoRedirect, inspection_fixture

MAX_ROWS = 10_000
MAX_RESPONSE = 4 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
DEADLINE_SECONDS = 600


def provider_digest(assets: list[dict[str, Any]]) -> str:
    """Use the production canonical implementation, never a diagnostic hash variant."""
    from src.core.asset_market.semantic_contract import canonical_semantic_value, digest
    result = hashlib.sha256()
    for asset in assets:
        result.update(digest(canonical_semantic_value({
            "asset_id": asset["asset_id"], "providers": asset.get("providers") or [],
        })).encode())
    return result.hexdigest()


def validate_origin(value: str, configured: str) -> None:
    """Never send the production inspection credential to a caller-chosen host."""
    origin, expected = urlsplit(value), urlsplit(configured)
    if (origin.scheme != "https" or origin.username or origin.password
            or origin.query or origin.fragment or origin.path not in ("", "/")
            or (origin.scheme, origin.netloc) != (expected.scheme, expected.netloc)):
        raise ValueError("The configured verified HTTPS public origin is required")


def capture(read: Callable[[str], dict[str, Any]], output: Path) -> dict[str, Any]:
    """Preserve bounded safe progress if transport or contract checks abort."""
    progress: list[dict[str, Any]] = []

    def observed(path: str) -> dict[str, Any]:
        entry = {"request": fingerprint(path), "completed": False}
        progress.append(entry)
        try:
            result = read(path)
        except HTTPError as exc:
            if exc.code != 404 or not path.startswith("/api/brain/assets/"):
                raise
            body = exc.read(MAX_RESPONSE + 1)
            if len(body) > MAX_RESPONSE or json.loads(body).get("detail") != (
                "The asset is not available in the synchronized Brain snapshot."
            ):
                raise
            result = {"asset": None, "availability": "absent_from_synchronized_brain"}
        entry.update(completed=True, response=fingerprint(result))
        return result

    try:
        return _capture(observed, output)
    except Exception as exc:
        # Never retain exception text: transports may include URLs or headers.
        persist(output.with_suffix(".failure.json"), {
            "capture": {"complete": False}, "exception_type": type(exc).__name__,
            "requests": progress,
        })
        raise


def _capture(read: Callable[[str], dict[str, Any]], output: Path) -> dict[str, Any]:
    """Retain evidence even on a moving boundary, then fail closed."""
    started = monotonic()
    count = 0

    def get(path: str) -> dict[str, Any]:
        nonlocal count
        if monotonic() - started > DEADLINE_SECONDS:
            raise ValueError("Restart capture deadline exceeded")
        result = read(path)
        count += len(json.dumps(result).encode())
        if count > MAX_TOTAL:
            raise ValueError("Restart capture input byte budget exceeded")
        return result

    def boundary() -> dict[str, Any]:
        account = get("/api/account")
        market = get("/api/market/health")
        brain = get("/api/brain/health")
        source = get("/api/valuation/normalization-inputs?limit=1")
        projection = get("/api/projections/health")
        if account.get("status") != "authenticated" or not account.get("active_league"):
            raise ValueError("Authenticated selected account context required")
        if str(account["active_league"]["league_id"]) != str(source.get("league_id")):
            raise ValueError("Restart capture crossed league context")
        if (market.get("status") != "ready"
                or market.get("cache", {}).get("build_active")
                or market.get("cache", {}).get("build_queued")):
            raise ValueError("Ready Market required for exact restart capture")
        semantic = market.get("semantic_identity") or {}
        for name in ("brain_semantic_output_digest", "provider_evidence_digest",
                     "asset_universe_digest", "ownership_dependency_digest"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(semantic.get(name) or "")):
                raise ValueError("Complete canonical semantic identities required")
        if any(not value for value in (
            market.get("market_generation"), source.get("synchronization_generation"),
            brain.get("generated_at"), market.get("cache", {}).get("requested_generation"),
        )):
            raise ValueError("Complete publication and synchronization boundary required")
        return {"account": account, "market": market, "brain": brain,
                "source": source, "projection": projection}

    def fence(value: dict[str, Any]) -> dict[str, Any]:
        market = value["market"]
        return {"account": value["account"],
                "sync": value["source"].get("synchronization_generation"),
                "market": market.get("market_generation"),
                "semantic": market.get("semantic_identity"),
                "requested": market.get("cache", {}).get("requested_generation"),
                "brain": value["brain"].get("generated_at"),
                "projection": value["projection"].get("active_snapshot_id")}

    def pages(path: str, key: str) -> list[Any]:
        rows: list[Any] = []
        total = None
        while total is None or len(rows) < total:
            page = get(f"{path}?offset={len(rows)}&limit=250")
            expected = page.get("total")
            if not isinstance(expected, int) or not 0 <= expected <= MAX_ROWS:
                raise ValueError("Invalid bounded pagination total")
            if total is not None and total != expected:
                raise ValueError("Pagination changed during restart capture")
            total = expected
            batch = page.get(key)
            if not isinstance(batch, list) or (not batch and len(rows) < total):
                raise ValueError("Incomplete restart pagination")
            rows.extend(batch)
            if len(rows) > total:
                raise ValueError("Excess restart pagination rows")
        return rows

    before = boundary()
    inputs = pages("/api/valuation/normalization-inputs", "records")
    valuation = pages("/api/valuation/assets", "assets")
    market_rows = pages("/api/market/assets", "assets")
    records = []
    for asset in valuation:
        asset_id = asset["asset_id"]
        brain = get("/api/brain/assets/" + quote(asset_id, safe=""))
        records.append({"asset_id": asset_id, "valuation": asset, "brain": brain})
    calibration = get("/api/valuation/calibration")
    providers = get("/api/valuation/providers")
    projection = get("/api/projections?offset=0&limit=500")
    projection_data = projection.get("projection")
    if projection_data is not None:
        if str(projection_data.get("league_id")) != str(before["source"].get("league_id")):
            raise ValueError("Projection belongs to another league")
        total = projection.get("pagination", {}).get("total")
        if not isinstance(total, int) or not 0 <= total <= MAX_ROWS:
            raise ValueError("Invalid projection pagination")
        players = list(projection_data.get("players") or [])
        while len(players) < total:
            page = get(f"/api/projections?offset={len(players)}&limit=500")
            batch = (page.get("projection") or {}).get("players") or []
            if not batch or page.get("pagination", {}).get("total") != total:
                raise ValueError("Incomplete projection pagination")
            players.extend(batch)
        if len(players) != total:
            raise ValueError("Excess projection records")
        projection_data = {**projection_data, "players": players}
    after = boundary()
    health = before["market"]
    semantic = health.get("semantic_identity") or {}
    evidence = snapshot({
        "account_identity": before["account"]["account"],
        "league_identity": before["account"]["active_league"],
        "synchronization_generation": before["source"].get("synchronization_generation"),
        "market_generation": health.get("market_generation"),
        "brain_generation": before["brain"],
        "brain_semantic_digest": semantic.get("brain_semantic_output_digest"),
        "provider_evidence_digest": semantic.get("provider_evidence_digest"),
        "projection_snapshot_id": before["projection"].get("active_snapshot_id"),
        "projection_digest": {"health": before["projection"], "canonical_snapshot": projection_data},
        "asset_universe_digest": semantic.get("asset_universe_digest"),
        "ownership_digest": semantic.get("ownership_dependency_digest"),
        "calibration": calibration,
        "artifact_compatibility": health,
        "provider_confidence": inputs + [p for a in valuation for p in a.get("providers", [])],
        "source_timestamps": [{k: p.get(k) for k in (
            "provider_id", "last_successful_refresh", "freshness_assessment",
            "confidence_contribution", "reliability_dimensions", "effective_calibration_weight",
        )} for p in providers.get("providers", [])],
        "semantic_records": records,
        "market_rows": market_rows,
    })
    observed_provider_digest = provider_digest(valuation)
    provider_matches = observed_provider_digest == semantic.get("provider_evidence_digest")
    evidence["capture"] = {"complete": fence(before) == fence(after) and provider_matches,
                           "observed_provider_digest": observed_provider_digest,
                           "published_provider_digest": semantic.get("provider_evidence_digest"),
                           "provider_inputs_match_publication": provider_matches,
                           "before_fence": fingerprint(fence(before)),
                           "after_fence": fingerprint(fence(after)),
                           "input_bytes": count, "asset_count": len(valuation)}
    persist(output, evidence)
    if not provider_matches:
        raise ValueError("Retained provider inputs differ from published Market; evidence retained")
    if not evidence["capture"]["complete"]:
        raise ValueError("Semantic boundary moved; incomplete evidence retained, restart prohibited")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://dtos.onrender.com")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    validate_origin(args.base_url, os.environ.get("DTOS_PUBLIC_URL", "https://dtos.onrender.com"))
    fixture = inspection_fixture()
    if fixture is None:
        raise ValueError("Existing complete production inspection context required")
    token, _league, _roster = fixture
    opener = build_opener(_NoRedirect)

    def read(path: str) -> dict[str, Any]:
        request = Request(args.base_url.rstrip("/") + path, headers={
            "X-DTOS-Inspection-Auth": token,
        })
        with opener.open(request, timeout=60) as response:
            body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ValueError("Restart response exceeds byte budget")
        return json.loads(body)

    evidence = capture(read, args.output)
    if args.compare:
        previous = json.loads(args.compare.read_text(encoding="utf-8"))
        if not previous.get("capture", {}).get("complete"):
            raise ValueError("Cannot compare an incomplete pre-restart capture")
        result = differences(previous, evidence)
        persist(args.output.with_suffix(".diff.json"), {"changes": result})
        print(json.dumps({"capture_complete": True, "changed_paths": len(result)}))
    else:
        print(json.dumps({"capture_complete": True, "asset_count": evidence["capture"]["asset_count"]}))


if __name__ == "__main__":
    main()
