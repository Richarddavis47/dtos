"""Bounded Step 8 join over canonical Steps 4-7 intelligence products."""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterable

from src.core.intelligence_memory import intelligence_checkpoint_store
from src.core.intelligence.league_scope import scoped_evidence, scoped_market_trends
from src.core.market_trends import MarketTrendService


TRADE_HISTORY_SCHEMA_VERSION = "trade-historical-context-1"
TRADE_HISTORY_METHOD_VERSION = "step8-bilateral-evidence-1"


@dataclass(frozen=True)
class TradeEvidenceContext:
    league_id: str
    behavior_by_roster: dict[str, dict[str, Any]]
    front_office_by_roster: dict[str, dict[str, Any]]
    trends_by_asset: dict[str, dict[str, Any]]
    generation: str
    provider_requests: int = 0
    raw_history_scans: int = 0
    profile_rebuilds: int = 0
    trend_rebuilds: int = 0
    wrong_league_evidence_rejected: int = 0
    wrong_league_evidence_consumed: int = 0
    preparation_duration_ms: float = 0.0
    schema_version: str = TRADE_HISTORY_SCHEMA_VERSION
    method_version: str = TRADE_HISTORY_METHOD_VERSION


def _market_generation(data: dict[str, Any]) -> str:
    market = data.get("market_data") or {}
    return str(market.get("generation") or market.get("generated_at") or "current")


def build_trade_evidence_context(
    data: dict[str, Any], assets: Iterable[Any] = (),
) -> TradeEvidenceContext:
    """Read each already-derived evidence product once; never scan raw history."""
    started = perf_counter()
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or data.get("league_id") or "")
    rows_by_id: dict[str, dict[str, Any]] = {}
    for value in assets:
        asset_id = str(getattr(value, "asset_id", value) or "")
        if not asset_id:
            continue
        current = getattr(value, "trade_value", None)
        rows_by_id.setdefault(
            asset_id, {"asset_id": asset_id, "values": {"market_value": current}},
        )
    ids = tuple(sorted(rows_by_id))[:250]
    supplied = data.get("market_trend_summaries")
    trend_rejections = 0
    if isinstance(supplied, dict):
        trends, trend_rejections = scoped_market_trends(
            data, ids, league_id=league_id,
        )
    elif ids:
        trends = MarketTrendService(intelligence_checkpoint_store).summaries(
            [rows_by_id[asset_id] for asset_id in ids],
            league_id=league_id or None, as_of=None,
            generation=_market_generation(data),
            compact=False,
        )
    else:
        trends = {}
    behavior = scoped_evidence(
        data, "gm_behavioral_intelligence", expected_league_id=league_id,
    )
    front_office = scoped_evidence(
        data, "front_office_evidence", expected_league_id=league_id,
    )
    return TradeEvidenceContext(
        league_id=league_id,
        behavior_by_roster=behavior.rows,
        front_office_by_roster=front_office.rows,
        trends_by_asset=trends,
        generation=_market_generation(data),
        wrong_league_evidence_rejected=(
            behavior.rejected + front_office.rejected + trend_rejections
        ),
        preparation_duration_ms=round((perf_counter() - started) * 1000, 3),
    )


def _dimension(profile: dict[str, Any], key: str) -> dict[str, Any] | None:
    return next((row for row in profile.get("dimensions") or () if row.get("key") == key), None)


def assess_historical_fit(
    context: TradeEvidenceContext | None, *, partner_roster_id: int,
    active_roster_id: int, partner_receives: Iterable[Any], active_receives: Iterable[Any],
) -> dict[str, Any]:
    """Return qualitative, lineage-preserving soft evidence for one proposal."""
    if context is None:
        return {
            "assessment": "INSUFFICIENT EVIDENCE", "confidence": "LOW", "score": 0,
            "reasons": ["Canonical historical behavior evidence is unavailable; current trade quality is unchanged."],
            "evidence_references": [], "trend_signals": [],
            "reason_codes": ["INSUFFICIENT_HISTORY"],
            "behavioral_sample_count": 0, "evidence_completeness": None,
            "source_evidence_identity": None, "behavior_semantic_identity": None,
            "process_distribution": {}, "outcome_distribution": {},
            "liquidity_supported": False,
        }
    profile = context.behavior_by_roster.get(str(partner_roster_id), {})
    reasons: list[str] = []
    references: list[str] = []
    reason_codes: list[str] = []
    score = 0
    confidence = str(profile.get("overall_confidence") or "low").upper()
    incoming = tuple(partner_receives)
    asset_direction = _dimension(profile, "asset_direction")
    positional = _dimension(profile, "positional")
    package = _dimension(profile, "package_preference") or _dimension(profile, "package_style")
    for row, expected in (
        (asset_direction, {f"acquire_{asset.kind}" for asset in incoming}),
        (positional, {f"acquire_{asset.position}" for asset in incoming if asset.position}),
    ):
        if not row or str(row.get("confidence") or "low") == "low":
            continue
        tendency = str(row.get("tendency") or "")
        if tendency in expected:
            score += 1
            reasons.append(f"Supported manager history includes {tendency.replace('_', ' ')} behavior.")
            reason_codes.append("POSITIONAL_HISTORY_MATCH" if row is positional else "ASSET_BEHAVIOR_MATCH")
            references.extend(str(value) for value in row.get("evidence_references") or ())
    if package and str(package.get("confidence") or "low") != "low":
        tendency = str(package.get("tendency") or "")
        shape = "multi_asset" if len(incoming) > 1 else "one_for_one"
        if tendency in {shape, "mixed"}:
            score += 1
            reasons.append(f"The package is consistent with supported {tendency.replace('_', ' ')} evidence.")
            reason_codes.append("PACKAGE_STYLE_MATCH")
            references.extend(str(value) for value in package.get("evidence_references") or ())
    bilateral = context.front_office_by_roster.get(str(partner_roster_id), {})
    count = int((bilateral.get("partner_counts") or {}).get(str(active_roster_id)) or 0)
    if count:
        score += 1
        reasons.append(f"The two franchises have {count} supported prior trade interaction{'s' if count != 1 else ''}.")
        reason_codes.append("BILATERAL_HISTORY")
        references.extend(str(value) for value in bilateral.get("evidence_references") or ())

    trend_signals: list[dict[str, str]] = []
    for direction, assets in (("acquire", active_receives), ("send", partner_receives)):
        for asset in assets:
            trend = context.trends_by_asset.get(asset.asset_id) or {}
            trend_direction = str(trend.get("direction") or "insufficient_evidence")
            trend_confidence = str(trend.get("confidence") or "unavailable")
            if trend_direction in {"rising", "falling", "volatile"} and trend_confidence in {"medium", "high"}:
                trend_signals.append({
                    "asset_id": asset.asset_id, "direction": trend_direction,
                    "confidence": trend_confidence, "trade_direction": direction,
                })
    if trend_signals:
        reasons.append("Supported market movement informs timing, but does not alter canonical value.")
        reason_codes.append("MARKET_TIMING_CONTEXT")
    liquidity_rows = [
        trend.get("league_liquidity") for trend in context.trends_by_asset.values()
        if isinstance(trend.get("league_liquidity"), dict)
    ]
    liquid = any(
        int(row.get("recent_transaction_count") or 0) >= 3
        and str(row.get("confidence") or "low") in {"medium", "high"}
        for row in liquidity_rows
    )
    if liquid:
        reasons.append("Supported league transaction evidence indicates a liquid market for relevant assets.")
        reason_codes.append("LIQUID_MARKET")
    assessment = "HIGH" if score >= 3 and confidence == "HIGH" else "MEDIUM" if score >= 1 else "LOW"
    if not reasons:
        reasons.append("Canonical manager-history and market-timing evidence is unavailable or too limited to influence this proposal.")
        reason_codes.append("INSUFFICIENT_HISTORY")
    return {
        "assessment": assessment, "confidence": confidence, "score": score,
        "reasons": reasons[:4], "evidence_references": sorted(set(references))[:12],
        "trend_signals": trend_signals[:6],
        "reason_codes": sorted(set(reason_codes)),
        "behavioral_sample_count": int(profile.get("transaction_count") or 0),
        "evidence_completeness": profile.get("evidence_completeness"),
        "source_evidence_identity": profile.get("source_evidence_identity"),
        "behavior_semantic_identity": profile.get("semantic_identity"),
        "process_distribution": dict(profile.get("process_distribution") or {}),
        "outcome_distribution": dict(profile.get("outcome_distribution") or {}),
        "liquidity_supported": liquid,
    }
