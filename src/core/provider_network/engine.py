"""Cached provider-network read model, reliability, and lineage-aware consensus."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev
from time import perf_counter
from typing import Any

from app_metadata import BUILD_NUMBER, VERSION, deployment_metadata
from src.core.freshness import assess_freshness, freshness_policy_manifest
from src.core.provider_network.contracts import EvidenceObservation
from src.core.provider_network.registry import EVIDENCE_CONTRACT_VERSION, PROVIDER_REGISTRY_VERSION, provider_registry
from src.core.provider_network.trades import observed_trades
from src.core.valuation.universe import ValuationUniverse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_hours(
    value: str | None, evaluation_time: datetime | None = None,
) -> float | None:
    if not value:
        return None
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
    now = evaluation_time or datetime.now(timezone.utc)
    return round(max(0.0, (now - observed).total_seconds() / 3600), 3)


def _reliability(provider: dict[str, Any], *, coverage: float, identity_rate: float, confidence: float, freshness_hours: float | None) -> dict[str, int]:
    prior = int(provider["default_reliability_prior"])
    freshness = assess_freshness(
        freshness_hours, provider.get("evidence_family"),
    ).semantic_weight
    availability = 100 if provider["current_availability"] == "healthy" else 55 if provider["current_availability"] in {"cached_fallback", "waiting"} else 0
    overall = round(prior * .25 + freshness * .2 + min(100, coverage) * .2 + identity_rate * .2 + confidence * .1 + availability * .05)
    overall = max(0, min(100, overall))
    return {key: max(0, min(100, overall + adjustment)) for key, adjustment in {
        "overall": 0, "QB": 0, "RB": 0, "WR": 0, "TE": 0, "rookie": -3,
        "veteran": 0, "pick": -8 if "pick" not in provider["asset_types"] else 0,
        "contender_utility": -5, "rebuilder_utility": -5, "market_movement_prediction": -8,
    }.items()}


def _consensus(observations: list[EvidenceObservation], reliability: dict[str, dict[str, int]]) -> dict[str, Any]:
    by_asset: dict[str, list[EvidenceObservation]] = defaultdict(list)
    for row in observations:
        if row.normalized_value is not None and row.identity_match_status in {"exact", "strong"}:
            by_asset[row.canonical_asset_id].append(row)
    results: list[dict[str, Any]] = []
    family_counts: list[int] = []
    for asset_id, rows in sorted(by_asset.items()):
        families: dict[str, list[EvidenceObservation]] = defaultdict(list)
        for row in rows:
            families[row.evidence_family].append(row)
        family_values: list[tuple[str, float, float]] = []
        for family, members in families.items():
            weighted = [(float(item.normalized_value), max(1, reliability[item.provider_id]["overall"]) * max(1, item.confidence) / 100) for item in members if item.normalized_value is not None]
            total_weight = sum(weight for _, weight in weighted)
            family_values.append((family, sum(value * weight for value, weight in weighted) / total_weight, min(100.0, total_weight / max(len(weighted), 1))))
        values = [row[1] for row in family_values]
        weights = [row[2] for row in family_values]
        consensus = round(sum(value * weight for value, weight in zip(values, weights)) / sum(weights)) if weights else None
        dispersion = round(pstdev(values), 2) if len(values) > 1 else None
        confidence = min(100, round(mean(weights) * min(1, len(families) / 2) * (1 if dispersion is None else max(.25, 1 - dispersion / 500)))) if weights else 0
        family_counts.append(len(families))
        results.append({"asset_id": asset_id, "raw_provider_count": len(rows), "independent_evidence_family_count": len(families), "effective_provider_count": round(sum(weights) / 100, 2), "weighted_consensus_value": consensus, "weighted_consensus_rank": None, "dispersion": dispersion, "confidence_interval": None if consensus is None or dispersion is None else [max(0, round(consensus - dispersion)), min(1000, round(consensus + dispersion))], "disagreement_score": min(100, round((dispersion or 0) / 5)), "market_evidence_confidence": confidence, "families": [row[0] for row in family_values]})
    return {"assets_with_evidence": len(results), "assets_with_multiple_independent_families": sum(row >= 2 for row in family_counts), "average_confidence": round(mean(row["market_evidence_confidence"] for row in results), 2) if results else 0, "average_disagreement": round(mean(row["disagreement_score"] for row in results), 2) if results else 0, "sample": results[:100]}


def build_provider_network(data: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """Build once during background synchronization; request handlers read this cache only."""
    started = perf_counter()
    evaluation_time = datetime.now(timezone.utc)
    generated_at = evaluation_time.isoformat()
    universe_started = perf_counter()
    universe = ValuationUniverse(data, state)
    universe_ms = round((perf_counter() - universe_started) * 1000, 3)
    market_data = data.get("market_data") or {}
    statuses = market_data.get("provider_status") or {}
    registry = provider_registry(statuses)
    prior_network = data.get("provider_network") or {}
    prior_providers = {
        row.get("provider_id"): row for row in prior_network.get("providers") or []
        if isinstance(row, dict)
    }
    provider_by_id = {row["provider_id"]: row for row in registry}
    observations: list[EvidenceObservation] = []
    unmatched: dict[str, int] = defaultdict(int)
    provider_records: dict[str, int] = defaultdict(int)
    provider_exact: dict[str, int] = defaultdict(int)
    confidence_values: dict[str, list[int]] = defaultdict(list)
    provider_stamp: dict[str, str | None] = {}
    name_to_id = {"FantasyCalc": "fantasycalc", "DynastyProcess": "dynastyprocess"}
    canonical_ids = set(universe.by_id)
    normalization_started = perf_counter()
    for provider_name, rows in (market_data.get("providers") or {}).items():
        provider_id = name_to_id.get(provider_name)
        if not provider_id or not isinstance(rows, dict):
            continue
        definition = provider_by_id[provider_id]
        for sleeper_id, value_row in rows.items():
            asset_id = f"player:{sleeper_id}"
            if asset_id not in canonical_ids:
                unmatched[provider_id] += 1
                continue
            row = value_row if isinstance(value_row, dict) else {"value": value_row}
            raw = row.get("value")
            asset = universe.by_id[asset_id]
            provider_value = next((item for item in asset["providers"] if item["provider"] == provider_name), {})
            observed_at = row.get("updated_at") or statuses.get(provider_name, {}).get("last_refresh")
            provider_stamp[provider_id] = observed_at
            observation = EvidenceObservation(asset_id, provider_id, definition["evidence_category"], float(raw) if raw is not None else None, provider_value.get("normalized_value"), int(row["position_rank"]) if str(row.get("position_rank") or "").isdigit() else None, int(row["rank"]) if str(row.get("rank") or "").isdigit() else None, str(row.get("tier")) if row.get("tier") is not None else None, "PPR", "superflex", 12, False, observed_at, observed_at, generated_at, _age_hours(observed_at, evaluation_time), 1, int(row.get("confidence") or 65), "available", 100, "exact", str(row.get("source_version") or "current"), definition["official_source_url"], definition["evidence_family"], definition["redistribution"] in {"open_data_attributed", "derived_and_attributed", "derived"})
            observations.append(observation)
            provider_records[provider_id] += 1
            provider_exact[provider_id] += 1
            confidence_values[provider_id].append(observation.confidence)
    normalization_ms = round((perf_counter() - normalization_started) * 1000, 3)
    trade_started = perf_counter()
    trades, trade_exclusions = observed_trades(data)
    trade_inference_ms = round((perf_counter() - trade_started) * 1000, 3)
    provider_records["sleeper_trades"] = len(trades)
    provider_records["league_local"] = len(trades)
    provider_exact["sleeper_trades"] = len(trades)
    provider_exact["league_local"] = len(trades)

    reliability_started = perf_counter()
    reliability: dict[str, dict[str, int]] = {}
    freshness_metrics: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "freshness_tier_changes": 0,
            "freshness_same_tier_evaluations": 0,
            "freshness_semantic_changes": 0,
        },
    )
    for definition in registry:
        provider_id = definition["provider_id"]
        records = provider_records[provider_id]
        if records and definition["compliance_status"] == "approved_enabled":
            definition["current_availability"] = "healthy"
        elif provider_id == "nflverse":
            definition["current_availability"] = "configured"
            definition["status_explanation"] = "Approved nflverse releases are ingested by Historical Memory; ordinary provider APIs use retained evidence and never fetch them."
        coverage = round(records * 100 / max(len(universe.assets), 1), 2)
        identity_rate = round(provider_exact[provider_id] * 100 / max(records + unmatched[provider_id], 1), 2) if records or unmatched[provider_id] else 0
        avg_confidence = mean(confidence_values[provider_id]) if confidence_values[provider_id] else definition["default_reliability_prior"]
        provider_age = _age_hours(provider_stamp.get(provider_id), evaluation_time)
        assessment = assess_freshness(provider_age, definition["evidence_family"])
        reliability[provider_id] = _reliability(definition, coverage=coverage, identity_rate=identity_rate, confidence=avg_confidence, freshness_hours=provider_age)
        definition["freshness_assessment"] = assessment.public_dict()
        prior_assessment = (
            prior_providers.get(provider_id, {}).get("freshness_assessment") or {}
        )
        if prior_assessment:
            family_metrics = freshness_metrics[definition["evidence_family"]]
            if prior_assessment.get("tier") == assessment.tier:
                family_metrics["freshness_same_tier_evaluations"] += 1
            else:
                family_metrics["freshness_tier_changes"] += 1
                family_metrics["freshness_semantic_changes"] += 1
        definition.update({"record_count": records, "coverage_percentage": coverage, "identity_match_rate": identity_rate, "unmatched_records": unmatched[provider_id], "reliability_score": reliability[provider_id]["overall"], "reliability_dimensions": reliability[provider_id], "effective_calibration_weight": round(reliability[provider_id]["overall"] / 100, 3) if definition["current_availability"] == "healthy" else 0.0, "confidence_contribution": round(avg_confidence, 1), "last_successful_refresh": provider_stamp.get(provider_id) or definition.get("last_successful_refresh")})
    reliability_ms = round((perf_counter() - reliability_started) * 1000, 3)
    consensus_started = perf_counter()
    consensus = _consensus(observations, reliability)
    consensus_ms = round((perf_counter() - consensus_started) * 1000, 3)
    deployment = deployment_metadata()
    result = {
        "application_version": VERSION, "application_build": BUILD_NUMBER, "commit": deployment["commit"],
        "provider_registry_version": PROVIDER_REGISTRY_VERSION, "evidence_contract_version": EVIDENCE_CONTRACT_VERSION,
        "generation_timestamp": generated_at, "freshness": universe.freshness, "availability": "available",
        "freshness_policy": freshness_policy_manifest(),
        "freshness_metrics": dict(freshness_metrics),
        "providers": registry,
        "provider_dependencies": [{"provider_id": row["provider_id"], "evidence_family": row["evidence_family"], "depends_on": row.get("depends_on") or []} for row in registry],
        "evidence": [row.public_dict() for row in observations],
        "evidence_summary": {"observations": len(observations), "unmatched": sum(unmatched.values()), "conflicting": 0, "ambiguous": 0, "exact": sum(row.identity_match_status == "exact" for row in observations)},
        "consensus": consensus,
        "observed_market": {"provider_id": "sleeper_trades", "league_isolated": True, "included_trades": len(trades), "excluded": trade_exclusions, "average_quality": round(mean(row.transaction_quality for row in trades), 2) if trades else 0, "outlier_review_count": sum(row.outlier_status != "normal" for row in trades)},
        "league_market": {"provider_id": "league_local", "league_isolated": True, "trade_count": len(trades), "public_raw_records": False, "purpose": "Post-baseline liquidity, demand, and acceptance context only."},
        "reliability_history": [{"timestamp": generated_at, "provider_id": provider_id, "dimensions": dimensions} for provider_id, dimensions in reliability.items()],
        "performance": {"total_ms": round((perf_counter() - started) * 1000, 3), "universe_ms": universe_ms, "normalization_ms": normalization_ms, "identity_resolution_ms": normalization_ms, "trade_inference_ms": trade_inference_ms, "reliability_ms": reliability_ms, "consensus_ms": consensus_ms, "normalization_records": len(observations), "identity_resolution_records": len(observations) + sum(unmatched.values()), "consensus_assets": consensus["assets_with_evidence"]},
        "safety": {"asset_integrity_score": 100 if universe.status()["duplicate_identities"] == 0 else 0, "restricted_raw_data_exposed": False, "single_family_calibration_allowed": False, "unsafe_adjustments": 0},
    }
    data["provider_network"] = result
    history = list(data.get("provider_reliability_history") or [])
    history.extend(result["reliability_history"])
    data["provider_reliability_history"] = history
    return result


def provider_network_report(data: dict[str, Any]) -> dict[str, Any]:
    report = data.get("provider_network")
    if isinstance(report, dict) and report:
        return report
    return {"application_version": VERSION, "application_build": BUILD_NUMBER, "commit": deployment_metadata()["commit"], "provider_registry_version": PROVIDER_REGISTRY_VERSION, "evidence_contract_version": EVIDENCE_CONTRACT_VERSION, "generation_timestamp": _now(), "freshness": {}, "availability": "pending", "providers": provider_registry(), "provider_dependencies": [], "evidence": [], "evidence_summary": {"observations": 0, "unmatched": 0, "conflicting": 0, "ambiguous": 0, "exact": 0}, "consensus": {"assets_with_evidence": 0, "assets_with_multiple_independent_families": 0, "average_confidence": 0, "average_disagreement": 0, "sample": []}, "observed_market": {"included_trades": 0, "excluded": {}, "league_isolated": True}, "league_market": {"league_isolated": True}, "reliability_history": [], "performance": {}, "safety": {"unsafe_adjustments": 0}}
