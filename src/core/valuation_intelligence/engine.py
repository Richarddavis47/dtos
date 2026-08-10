"""Deterministic evidence scoring, explanation, timelines, and diagnostics."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from statistics import mean, pstdev
from typing import Any, Mapping

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.valuation.universe import ValuationUniverse

INTELLIGENCE_SCHEMA_VERSION = "1.0"
EVIDENCE_CATEGORIES = ("Market", "Trades", "Performance", "Historical", "League Context", "Team Context", "Projection", "Metadata")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _semantic_generation(assets: list[dict[str, Any]]) -> str:
    """Fingerprint canonical intelligence while excluding observation metadata."""
    def stable(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: stable(item)
                for key, item in value.items()
                if key not in {"generated_at", "updated_at"}
            }
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value

    payload = json.dumps(
        stable(assets), sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _category(name: str) -> str:
    value = name.lower()
    if "transaction" in value or "trade" in value:
        return "Trades"
    if "performance" in value:
        return "Performance"
    if "histor" in value:
        return "Historical"
    if "league" in value:
        return "League Context"
    if "projection" in value:
        return "Projection"
    if "metadata" in value:
        return "Metadata"
    return "Market"


def resolve_asset_name(asset: Mapping[str, Any]) -> str:
    """Resolve the existing Canonical Asset Universe identity without aliases."""
    identity = asset.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    for key in ("player_name", "draft_pick_description"):
        value = identity.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    canonical_id = asset.get("asset_id") or "unknown"
    return f"Unknown asset ({canonical_id})"


def _score_asset(asset: dict[str, Any], rows: list[dict[str, Any]], providers: dict[str, dict[str, Any]], consensus: dict[str, Any] | None) -> dict[str, Any]:
    identity = asset.get("identity") or {}
    categories = {_category(str(row.get("evidence_category") or "")) for row in rows}
    categories.add("Metadata")
    if (identity.get("current_owner") or {}).get("roster_id"):
        categories.update(("League Context", "Team Context"))
    layers = asset.get("layers") or {}
    if (layers.get("current_production_value") or {}).get("value") is not None:
        categories.add("Performance")
    if (layers.get("future_value") or {}).get("value") is not None:
        categories.add("Projection")
    intrinsic = (layers.get("intrinsic_dtos_value") or {}).get("value")
    if intrinsic is not None:
        categories.add("Historical")

    provider_ids = {str(row.get("provider_id")) for row in rows}
    families = {str(row.get("evidence_family")) for row in rows}
    coverage = min(100, round(len(categories) / len(EVIDENCE_CATEGORIES) * 55 + min(len(families), 3) / 3 * 25 + (10 if rows else 0) + (10 if intrinsic is not None else 0)))
    normalized = [float(row["normalized_value"]) for row in rows if row.get("normalized_value") is not None]
    dispersion = float(consensus.get("dispersion")) if consensus and consensus.get("dispersion") is not None else (pstdev(normalized) if len(normalized) > 1 else None)
    agreement = 35 if not normalized else 70 if len(normalized) == 1 else max(0, min(100, round(100 - (dispersion or 0) / 5)))
    reliabilities = [int((providers.get(provider_id) or {}).get("reliability_score") or 0) for provider_id in provider_ids]
    identity = [int(row.get("identity_match_confidence") or 0) for row in rows]
    freshness = [max(0, 100 - min(100, round(float(row.get("freshness_age_hours") or 0) * 2))) for row in rows]
    sample = min(100, len(rows) * 20)
    confidence = round(
        agreement * .30
        + (mean(reliabilities) if reliabilities else 25) * .25
        + (mean(identity) if identity else 50) * .15
        + (mean(freshness) if freshness else 40) * .10
        + coverage * .15
        + sample * .05
    )
    confidence = max(0, min(100, confidence))

    contributions = []
    for row in rows:
        provider = providers.get(str(row.get("provider_id"))) or {}
        reliability = int(provider.get("reliability_score") or 0)
        fresh = max(0, 100 - min(100, round(float(row.get("freshness_age_hours") or 0) * 2)))
        weight = round(reliability * .45 + fresh * .20 + int(row.get("confidence") or 0) * .20 + int(row.get("identity_match_confidence") or 0) * .15, 2)
        contributions.append({"provider_id": row.get("provider_id"), "category": _category(str(row.get("evidence_category") or "")), "family": row.get("evidence_family"), "weight": weight, "normalized_value": row.get("normalized_value"), "freshness_age_hours": row.get("freshness_age_hours"), "reliability": reliability})

    reasons = [f"{len(categories)} of {len(EVIDENCE_CATEGORIES)} evidence categories are represented."]
    reasons.append(f"{len(families)} independent provider {'family' if len(families) == 1 else 'families'} contribute evidence.")
    reasons.append(f"Provider agreement is {agreement}/100" + (f" with normalized dispersion {round(dispersion, 2)}." if dispersion is not None else "."))
    if not rows:
        reasons.append("No supported market-provider observation is available; confidence is intentionally limited.")
    if "Trades" in categories:
        reasons.append("Observed trade evidence contributes league-relevant market context.")
    explanation = " ".join(reasons) + f" Overall confidence is {confidence}/100 and coverage is {coverage}/100."
    missing = [name for name in EVIDENCE_CATEGORIES if name not in categories]
    diagnostics = []
    if coverage >= 65 and confidence < 50:
        diagnostics.append("High Coverage / Low Confidence")
    if coverage < 40 and confidence >= 65:
        diagnostics.append("Low Coverage / High Confidence")
    if agreement < 60 and len(normalized) > 1:
        diagnostics.append("Provider disagreement")
    if missing:
        diagnostics.append("Missing evidence")
    if "Historical" not in categories:
        diagnostics.append("Weak historical support")
    if "Market" not in categories and "Trades" not in categories:
        diagnostics.append("Missing market support")
    return {
        "asset_id": asset["asset_id"], "asset_type": asset["asset_type"], "display_name": resolve_asset_name(asset),
        "scores": {"coverage": coverage, "confidence": confidence, "agreement": agreement},
        "valuation_layers": {name: layers.get(name) for name in ("market_value", "intrinsic_dtos_value", "league_adjusted_value", "contender_value", "rebuilder_value")},
        "categories": [{"name": name, "available": name in categories, "observation_count": sum(_category(str(row.get("evidence_category") or "")) == name for row in rows)} for name in EVIDENCE_CATEGORIES],
        "evidence_sources": contributions, "provider_count": len(provider_ids), "independent_family_count": len(families),
        "missing_evidence": missing, "diagnostics": diagnostics, "explanation": explanation,
    }


def build_valuation_intelligence(data: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Build the intelligence cache after provider ingestion; never performs I/O."""
    generated_at = _now()
    universe = ValuationUniverse(data, state)
    network = data.get("provider_network") or {}
    evidence_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in network.get("evidence") or []:
        evidence_by_asset[str(row.get("canonical_asset_id"))].append(dict(row))
    provider_by_id = {row["provider_id"]: row for row in network.get("providers") or []}
    consensus_by_asset = {row["asset_id"]: row for row in (network.get("consensus") or {}).get("sample") or []}
    reports = [_score_asset(asset, evidence_by_asset[asset["asset_id"]], provider_by_id, consensus_by_asset.get(asset["asset_id"])) for asset in universe.assets]
    projection_snapshot = data.get("projection_intelligence") or {}
    projections = projection_snapshot.get("players") or {}
    for row in reports:
        if not row["asset_id"].startswith("player:"):
            continue
        projection = projections.get(row["asset_id"].removeprefix("player:"))
        if projection is None:
            continue
        row["forward_production"] = projection
        row["projection_confidence"] = projection.get("projection_confidence")
        row["projection_snapshot_id"] = projection.get("projection_snapshot_id")
    by_id = {row["asset_id"]: row for row in reports}

    prior_timeline = data.get("valuation_intelligence_timeline") or {}
    timeline: dict[str, list[dict[str, Any]]] = {key: list(value) for key, value in prior_timeline.items() if isinstance(value, list)}
    for row in reports:
        event = {"timestamp": generated_at, "coverage": row["scores"]["coverage"], "confidence": row["scores"]["confidence"], "agreement": row["scores"]["agreement"], "provider_count": row["provider_count"], "categories": [item["name"] for item in row["categories"] if item["available"]]}
        history = timeline.setdefault(row["asset_id"], [])
        comparable = {key: event[key] for key in event if key != "timestamp"}
        if not history or {key: history[-1].get(key) for key in comparable} != comparable:
            history.append(event)
        timeline[row["asset_id"]] = history[-50:]

    diagnostics: dict[str, list[str]] = defaultdict(list)
    for row in reports:
        for diagnostic in row["diagnostics"]:
            diagnostics[diagnostic].append(row["asset_id"])
    def ranked(key: str, reverse: bool = True) -> list[str]:
        return [row["asset_id"] for row in sorted(reports, key=lambda item: (item["scores"][key], item["asset_id"]), reverse=reverse)[:25]]
    result = {
        "application_version": VERSION, "application_build": BUILD_NUMBER, "commit": deployment_metadata()["commit"],
        "schema_version": INTELLIGENCE_SCHEMA_VERSION, "generated_at": generated_at,
        "semantic_generation": _semantic_generation(reports),
        "availability": "available",
        "asset_count": len(reports), "assets": by_id, "timeline": timeline,
        "summary": {
            "average_coverage": round(mean(row["scores"]["coverage"] for row in reports), 2) if reports else 0,
            "average_confidence": round(mean(row["scores"]["confidence"] for row in reports), 2) if reports else 0,
            "average_agreement": round(mean(row["scores"]["agreement"] for row in reports), 2) if reports else 0,
            "highest_coverage": ranked("coverage"), "lowest_coverage": ranked("coverage", False),
            "highest_confidence": ranked("confidence"), "lowest_confidence": ranked("confidence", False),
            "strongest_consensus": ranked("agreement"), "most_disputed": ranked("agreement", False),
        },
        "diagnostics": dict(diagnostics),
        "safety": {"external_requests_during_build": 0, "asset_integrity_score": 100 if len(by_id) == len(universe.assets) else 0, "unsafe_adjustments": 0, "independent_layers_preserved": True},
    }
    data["valuation_intelligence"] = result
    data["valuation_intelligence_timeline"] = timeline
    return result


def valuation_intelligence_report(data: dict[str, Any]) -> dict[str, Any]:
    report = data.get("valuation_intelligence")
    if isinstance(report, dict) and report:
        return report
    return {"application_version": VERSION, "application_build": BUILD_NUMBER, "commit": deployment_metadata()["commit"], "schema_version": INTELLIGENCE_SCHEMA_VERSION, "generated_at": _now(), "availability": "pending", "asset_count": 0, "assets": {}, "timeline": {}, "summary": {}, "diagnostics": {}, "safety": {"external_requests_during_build": 0, "unsafe_adjustments": 0}}
