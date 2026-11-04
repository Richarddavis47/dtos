"""Player views expose independent evidence concepts, never a blended dynasty scalar."""
from __future__ import annotations

from typing import Any

from src.core.player_value_projection.models import DataStatus, LineupValue, PlayerValueProfile, PositionalContext, ValueMetric
from src.core.player_value_projection.providers import PlayerDataRegistry, SleeperCanonicalProjectionProvider, player_data_registry
from src.core.player_value_projection.canonical_production import prepared_production_context
from src.core.valuation import CalibrationStatus, PlayerIntelligenceCard
from src.core.valuation.models import ConsensusProvider
from src.core.valuation.ranking import current_global_player_ranks, rank_players


def evaluate_player_values(context: Any, decision: Any, reports: dict[str, Any], market: Any,
                           registry: PlayerDataRegistry = player_data_registry) -> dict[str, PlayerValueProfile]:
    snapshot = context.projection_snapshot or {}
    if snapshot and str(snapshot.get("league_id") or "") != context.league_id:
        raise ValueError("Player projection league mismatch")
    week = snapshot.get("week")
    raw_by_id = {str(p.get("id") or p.get("player_id")): p for p in decision.profile.players}
    provider = registry.projection()
    # A legacy redraft score is not a projection-provider input.
    if not isinstance(provider, SleeperCanonicalProjectionProvider):
        raise ValueError("Canonical pinned projection provider required")
    projections = {key: provider.from_canonical((snapshot.get("players") or {}).get(key), week)
                   for key in reports}
    positions = {key: report.profile.position for key, report in reports.items()}
    weekly_ranks = rank_players({key: row.projected_points for key, row in projections.items()},
        positions, scope="roster", value_basis="weekly_projection", methodology="sleeper-canonical-weekly")
    intrinsic_ranks = rank_players(dict.fromkeys(reports), positions, scope="roster",
        value_basis="intrinsic_dtos_value", methodology="intrinsic-unavailable-v1")
    unavailable = ValueMetric(None, "Unsupported scalar; see separate evidence", DataStatus.UNAVAILABLE, 0,
        None, ("No validated long-term intrinsic scalar or numeric substitute is published.",))
    profiles = {}
    global_ranks = current_global_player_ranks(context.cached_data)
    for key, report in reports.items():
        raw, projection = raw_by_id[key], projections[key]
        market_report = market.assets.get(key)
        consensus = market_report.consensus.value if market_report else None
        confidence = market_report.consensus.confidence if market_report and consensus is not None else 0
        weights = dict(market_report.consensus.provider_weights) if market_report else {}
        quotes = [q for q in market_report.consensus.quotes if q.available and q.normalized_value is not None
                  and weights.get(q.provider, 0) > 0] if market_report else []
        status = DataStatus.CACHED if consensus is not None else DataStatus.UNAVAILABLE
        market_metric = ValueMetric(consensus, "Canonical external Market price", status, confidence,
            market_report.consensus.updated_at if market_report and hasattr(market_report.consensus, "updated_at") else None)
        same_position = [p.projected_points for pid, p in projections.items() if positions[pid] == positions[key]]
        # This is a roster-local comparison, NOT legal-lineup optimization or dynasty utility.
        replacement = (sorted(same_position)[max(0, len(same_position) // 3 - 1)]
                       if same_position and all(v is not None for v in same_position) else None)
        starters = [projections[pid].projected_points for pid in reports
                    if positions[pid] == positions[key] and raw_by_id[pid].get("roster_slot") == "Starter"]
        starter = min(starters) if starters and all(v is not None for v in starters) else None
        above = round(projection.projected_points - replacement, 2) if projection.projected_points is not None and replacement is not None else None
        above_starter = round(projection.projected_points - starter, 2) if projection.projected_points is not None and starter is not None else None
        actual = raw.get("roster_slot") == "Starter"
        lineup = LineupValue("Actual starter" if actual else "Reserve", actual,
            positions[key] in {"RB", "WR", "TE"},
            positions[key] == "QB" and "SUPER_FLEX" in context.settings.get("roster_positions", ()),
            replacement, above, above_starter, None, None)
        prepared = context.cached_data.get("canonical_player_production")
        production = prepared_production_context(
            prepared if prepared is not None else {"league_id": context.league_id},
            league_id=context.league_id, player_id=key)
        positional = PositionalContext(None, None, weekly_ranks[key]["position"].rank,
            "Intrinsic tier unavailable", None, above,
            sum(pos == positions[key] for pos in positions.values()), None,
            scoped_ranks={"global_market": (global_ranks.get(f"player:{key}") or {}).get("global_market", {}), "roster_dynasty": intrinsic_ranks[key],
                          "roster_weekly": weekly_ranks[key]})
        evidence = (
            "Market price is external acquisition evidence, not DTOS intrinsic value.",
            "Long-term intrinsic value, fit and liquidity scalars are unavailable.",
            f"Weekly expectation uses the published week {week} horizon only; it is not annualized.",
            f"League {context.league_id}; evidence generation {context.evidence_generation}.",
            "Actual starter status is distinct from the team's optimal legal projected lineup.",
        )
        limits = tuple(dict.fromkeys((*projection.limitations, *production.limitations, *unavailable.limitations)))
        provider_evidence = tuple(ConsensusProvider(q.provider, float(q.value), int(q.normalized_value),
            weights[q.provider], q.freshness) for q in quotes if q.value is not None)
        calibration = CalibrationStatus(market_report.consensus.calibration_status) if market_report else CalibrationStatus.INSUFFICIENT_DATA
        card = PlayerIntelligenceCard(key, consensus, None, None, None, None, consensus,
            None, None, None, None, None, confidence, calibration, provider_evidence,
            "Review evidence", evidence, limits)
        normalized = sorted(q.normalized_value for q in quotes)
        profiles[key] = PlayerValueProfile(key, report.profile.name, positions[key], report.profile.nfl_team,
            report.profile.age, raw.get("portrait_url") or raw.get("headshot_url"),
            "available" if raw.get("portrait_url") or raw.get("headshot_url") else "fallback",
            "".join(p[:1] for p in report.profile.name.split()[:2]).upper() or "DT",
            unavailable, market_metric, (normalized[0], normalized[-1]) if normalized else None,
            unavailable, unavailable, unavailable, unavailable, unavailable, unavailable,
            market_report.trend.direction if market_report else "Unavailable", None, "Review evidence",
            projection, production, lineup, positional, "Review evidence", evidence, limits, card)
    return profiles
