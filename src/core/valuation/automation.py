"""Automated, explainable model-level market calibration over the canonical universe."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any

from app_metadata import VERSION
from src.core.valuation.universe import ValuationUniverse


CALIBRATION_SCHEMA_VERSION = "1.0"
MINIMUM_CATEGORY_SAMPLE = 20
AUTO_APPLY_SAMPLE = 50
AUTO_APPLY_CONFIDENCE = 90
MAXIMUM_AUTOMATIC_ADJUSTMENT = 0.03
CATEGORY_ORDER = (
    "All Assets", "Quarterbacks", "Running Backs", "Wide Receivers", "Tight Ends",
    "Elite Players", "Veterans", "Rookies", "Future Picks", "Early Picks", "Late Picks",
    "Young Assets", "Contending Assets", "Rebuilding Assets",
)
IMPACT_SYSTEMS = (
    "Team Intelligence", "Trade Intelligence", "FOIS", "Championship Odds",
    "Playoff Odds", "Power Rankings", "Team Grades", "Trade Recommendations",
    "Contender Rankings", "Rebuilder Rankings",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _categories(asset: dict[str, Any]) -> tuple[str, ...]:
    identity = asset["identity"]
    if asset["asset_type"] == "pick":
        round_number = int(identity.get("round") or 0)
        return ("All Assets", "Future Picks", "Early Picks" if round_number <= 2 else "Late Picks")
    position = str(identity.get("position") or "").upper()
    mapping = {"QB": "Quarterbacks", "RB": "Running Backs", "WR": "Wide Receivers", "TE": "Tight Ends"}
    categories = ["All Assets"]
    if position in mapping:
        categories.append(mapping[position])
    market = asset["layers"]["market_value"]["value"]
    age = identity.get("age")
    if market is not None and market >= 750:
        categories.append("Elite Players")
    if identity.get("rookie_class"):
        categories.append("Rookies")
    if isinstance(age, (int, float)):
        categories.append("Young Assets" if age <= 24 else "Veterans" if age >= 28 else "Contending Assets")
        if age <= 26:
            categories.append("Rebuilding Assets")
    return tuple(dict.fromkeys(categories))


def _status(deviation: float | None, confidence: int, sample: int) -> str:
    if deviation is None or sample < MINIMUM_CATEGORY_SAMPLE:
        return "Review"
    magnitude = abs(deviation)
    if magnitude < 5:
        return "Confirm"
    if magnitude < 10 or confidence < 70:
        return "Review"
    if magnitude < 20 or confidence < AUTO_APPLY_CONFIDENCE:
        return "Significant Difference"
    return "Calibration Required"


def _impact(category: str, deviation: float | None, sample: int, total: int) -> tuple[int, tuple[str, ...]]:
    affected = {
        "Quarterbacks": ("Team Intelligence", "Trade Intelligence", "Championship Odds", "Trade Recommendations"),
        "Running Backs": ("Team Intelligence", "Championship Odds", "Team Grades", "Contender Rankings"),
        "Wide Receivers": ("Team Intelligence", "Trade Intelligence", "Team Grades", "Rebuilder Rankings"),
        "Tight Ends": ("Team Intelligence", "Trade Intelligence", "Championship Odds", "Power Rankings"),
        "Future Picks": ("Trade Intelligence", "FOIS", "Trade Recommendations", "Rebuilder Rankings"),
        "Early Picks": ("Trade Intelligence", "FOIS", "Trade Recommendations", "Rebuilder Rankings"),
        "Late Picks": ("Trade Intelligence", "FOIS", "Trade Recommendations"),
    }.get(category, IMPACT_SYSTEMS)
    coverage = sample / max(total, 1)
    score = round(min(100, (abs(deviation or 0) * 2.5) + (coverage * 50) + len(affected) * 2))
    return score, tuple(affected)


def _provider_summary(universe: ValuationUniverse) -> list[dict[str, Any]]:
    available: dict[str, int] = defaultdict(int)
    raw_status = {row["provider"]: row for row in universe.providers()["providers"]}
    for asset in universe.assets:
        for row in asset["providers"]:
            if row["raw_value"] is not None:
                available[row["provider"]] += 1
    return [
        {
            "provider": name,
            "status": (raw_status.get(name) or {}).get("status", "available" if available[name] else "unavailable"),
            "records": available[name],
            "last_refresh": (raw_status.get(name) or {}).get("last_refresh"),
            "confidence": round(mean(
                row["confidence"] for asset in universe.assets for row in asset["providers"]
                if row["provider"] == name and row["raw_value"] is not None
            )) if available[name] else 0,
            "reason": (raw_status.get(name) or {}).get("reason"),
        }
        for name in ("DTOS", "KTC", "FantasyCalc", "DynastyProcess")
    ]


def audit_market_calibration(data: dict[str, Any], state: dict[str, Any], *, apply: bool = True) -> dict[str, Any]:
    """Audit every canonical asset and safely apply category-level adjustments only."""
    generated_at = _now()
    universe = ValuationUniverse(data, state)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    largest: list[dict[str, Any]] = []
    for asset in universe.assets:
        intrinsic = asset["layers"]["intrinsic_dtos_value"]["value"]
        market = asset["layers"]["market_value"]["value"]
        difference = None if intrinsic is None or market is None else round((intrinsic - market) * 100 / max(abs(market), 1), 2)
        row = {
            "asset_id": asset["asset_id"], "asset_type": asset["asset_type"],
            "name": asset["identity"]["player_name"] or asset["identity"]["draft_pick_description"],
            "intrinsic_value": intrinsic, "market_value": market, "difference_percent": difference,
            "provider_count": asset["audit"]["provider_count"], "confidence": asset["audit"]["confidence"],
        }
        for category in _categories(asset):
            buckets[category].append(row)
        if difference is not None:
            largest.append(row)

    providers = _provider_summary(universe)
    integrity = universe.status()
    integrity_ok = integrity["duplicate_identities"] == 0 and integrity["counts"]["total"] == len(universe.assets)
    healthy_market_providers = [row for row in providers if row["provider"] != "DTOS" and row["status"] == "healthy" and row["records"]]
    provider_network = data.get("provider_network") or {}
    independent_families = int((provider_network.get("consensus") or {}).get("assets_with_multiple_independent_families") or 0)
    network_safe = bool((provider_network.get("safety") or {}).get("asset_integrity_score") == 100 and not (provider_network.get("evidence_summary") or {}).get("conflicting"))
    freshness_current = universe.freshness["current_status"] == "Current"
    category_health: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    prior_adjustments = dict((data.get("calibration_state") or {}).get("adjustments") or {})
    adjustments = dict(prior_adjustments)
    for category in CATEGORY_ORDER:
        rows = buckets.get(category, [])
        comparable = [row for row in rows if row["difference_percent"] is not None]
        deviations = [float(row["difference_percent"]) for row in comparable]
        confidence = round(mean(row["confidence"] for row in comparable)) if comparable else 0
        deviation = round(median(deviations), 2) if deviations else None
        status = _status(deviation, confidence, len(comparable))
        impact_score, affected_systems = _impact(category, deviation, len(comparable), len(universe.assets))
        category_row = {
            "category": category, "assets_audited": len(rows), "comparable_assets": len(comparable),
            "median_difference_percent": deviation,
            "mean_absolute_difference_percent": round(mean(abs(item) for item in deviations), 2) if deviations else None,
            "confidence": confidence, "status": status, "impact_score": impact_score,
            "provider_agreement": "supported" if len(healthy_market_providers) >= 2 else "insufficient",
        }
        category_health.append(category_row)
        if status == "Confirm":
            continue
        evidence = [
            f"Audited {len(rows)} assets; {len(comparable)} have both intrinsic and market evidence.",
            f"Median DTOS-versus-market difference is {deviation}%" if deviation is not None else "Comparable intrinsic evidence is insufficient.",
            f"{len(healthy_market_providers)} independent market providers are healthy.",
        ]
        safe = (
            status == "Calibration Required" and len(comparable) >= AUTO_APPLY_SAMPLE
            and confidence >= AUTO_APPLY_CONFIDENCE and len(healthy_market_providers) >= 2
            and freshness_current and integrity_ok and independent_families >= AUTO_APPLY_SAMPLE and network_safe
        )
        adjustment = round(max(-MAXIMUM_AUTOMATIC_ADJUSTMENT, min(MAXIMUM_AUTOMATIC_ADJUSTMENT, -(deviation or 0) / 100 * .25)), 4) if safe else 0.0
        applied = bool(apply and safe and adjustment)
        if applied:
            adjustments[category] = round(1 + adjustment, 4)
        recommendations.append({
            "recommendation_id": f"{generated_at}:{category.lower().replace(' ', '-')}",
            "category": category, "status": status,
            "title": f"{'Calibrate' if safe else 'Review'} {category}",
            "summary": "Apply a bounded category-level adjustment." if safe else "Monitor or improve model evidence; no automatic adjustment is safe.",
            "confidence": confidence, "impact_score": impact_score, "affected_systems": affected_systems,
            "evidence": evidence, "providers_considered": [row["provider"] for row in healthy_market_providers],
            "safety_checks": {
                "multiple_providers": len(healthy_market_providers) >= 2, "fresh_data": freshness_current,
                "minimum_sample": len(comparable) >= AUTO_APPLY_SAMPLE, "confidence_threshold": confidence >= AUTO_APPLY_CONFIDENCE,
                "asset_integrity": integrity_ok,
                "independent_evidence_families": independent_families >= AUTO_APPLY_SAMPLE,
                "provider_network_safe": network_safe,
                "bounded_adjustment": abs(adjustment) <= MAXIMUM_AUTOMATIC_ADJUSTMENT,
            },
            "proposed_adjustment": adjustment, "applied": applied,
            "explanation": "Consensus informs this model-level recommendation but never replaces DTOS intrinsic value.",
        })

    comparable_total = sum(row["comparable_assets"] for row in category_health if row["category"] == "All Assets")
    all_assets = next(row for row in category_health if row["category"] == "All Assets")
    calibration_score = max(0, round(100 - min(100, all_assets["mean_absolute_difference_percent"] or 0)))
    integrity_score = 100 if integrity_ok else 0
    report = {
        "schema_version": CALIBRATION_SCHEMA_VERSION, "generated_at": generated_at,
        "model_version": VERSION, "automatic": True,
        "summary": {
            "overall_calibration_score": calibration_score, "total_assets_audited": len(universe.assets),
            "providers_available": len(healthy_market_providers), "provider_freshness": universe.freshness["current_status"],
            "asset_integrity_score": integrity_score, "calibration_confidence": all_assets["confidence"],
            "high_priority_categories": sum(row["status"] in {"Significant Difference", "Calibration Required"} for row in category_health),
            "active_recommendations": len(recommendations), "last_calibration_timestamp": generated_at,
            "comparable_assets": comparable_total,
        },
        "providers": providers, "category_health": category_health,
        "largest_differences": sorted(largest, key=lambda row: abs(row["difference_percent"]), reverse=True)[:100],
        "recommendations": sorted(recommendations, key=lambda row: (-row["impact_score"], -row["confidence"], row["category"])),
        "adjustments": adjustments, "freshness": universe.freshness,
        "integrity": integrity,
        "principle": "Consensus is an input, not the answer. DTOS optimizes for explainable long-term correctness.",
    }
    previous = data.get("calibration_report") or {}
    applied_rows = [row for row in report["recommendations"] if row["applied"]]
    history = list(data.get("calibration_history") or [])
    if not history or previous.get("generated_at") != generated_at:
        history.append({
            "timestamp": generated_at, "model_version": report["model_version"],
            "calibration_categories": [row["category"] for row in applied_rows] or ["No calibration required"],
            "evidence_summary": f"Audited {len(universe.assets)} assets with {len(healthy_market_providers)} healthy market providers.",
            "confidence": all_assets["confidence"], "before_metrics": (previous.get("summary") or {}),
            "after_metrics": report["summary"], "affected_asset_count": sum(len(buckets[row["category"]]) for row in applied_rows),
            "predicted_impact": max((row["impact_score"] for row in applied_rows), default=0),
            "actual_observed_impact": None, "adjustments": {row["category"]: adjustments[row["category"]] for row in applied_rows},
        })
    data["calibration_state"] = {"adjustments": adjustments, "updated_at": generated_at, "schema_version": CALIBRATION_SCHEMA_VERSION}
    data["calibration_report"] = report
    data["calibration_history"] = history
    return report


def calibration_report(data: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    report = data.get("calibration_report")
    return report if isinstance(report, dict) and report else audit_market_calibration(data, state, apply=False)


__all__ = ["CALIBRATION_SCHEMA_VERSION", "audit_market_calibration", "calibration_report"]
