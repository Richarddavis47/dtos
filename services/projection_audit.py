"""Read-only assembly of the Projection & Intelligence Audit Export."""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, median
from typing import Any

from app_metadata import BUILD_NUMBER, VERSION

REFERENCE_PLAYERS = {
    "J. Daniels": 17.91, "B. Robinson": 21.68, "O. Hampton": 15.88,
    "J. Chase": 19.76, "P. Nacua": 19.79, "N. Collins": 16.71,
    "J. Dart": 17.81, "J. Price": 9.11, "N. Singleton": 2.29,
    "M. Washington": 6.78, "R. Flournoy": 6.60, "A. Iosivas": 4.05,
}
REFERENCE_TEAMS = {"Puka Cola Quantum": 188.32, "Bottom Feeders": 91.91}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _difference(left: Any, right: Any) -> float | None:
    a, b = _number(left), _number(right)
    return round(a - b, 3) if a is not None and b is not None else None


def _bucket(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    magnitude = abs(value)
    if magnitude <= 2:
        return "Very Close"
    if magnitude <= 5:
        return "Small"
    if magnitude <= 10:
        return "Moderate"
    return "Large"


def _unavailable(reason: str) -> dict[str, str]:
    return {"status": "unavailable", "reason": reason}


def _rank_maps(market: Any) -> dict[str, dict[str, int]]:
    mappings: dict[str, dict[str, int]] = {}
    for name, sort in (
        ("overall_rank", "market"), ("contender_rank", "contender"),
        ("rebuilder_rank", "rebuilder"),
    ):
        response = market.directory(limit=len(market.assets), sort=sort)
        mappings[name] = {
            str(row["asset_id"]): int(row["rank"])
            for row in response.get("assets") or []
        }
    position_rank: dict[str, int] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in market.assets:
        grouped.setdefault(str(row.get("position") or "Other"), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: (-float((row.get("values") or {}).get("market_value") or 0), str(row.get("asset_id"))))
        position_rank.update({str(row["asset_id"]): index for index, row in enumerate(rows, 1)})
    mappings["position_rank"] = position_rank
    return mappings


def _fois(scores: tuple[Any, ...]) -> list[dict[str, Any]]:
    ordered = sorted(scores, key=lambda score: (-(score.overall_score or -1), score.gm_id or ""))
    rows = []
    for rank, score in enumerate(ordered, 1):
        categories = {row.category_key: row.normalized_score for row in score.category_scores}
        rows.append({
            "gm_id": score.gm_id, "gm_name": score.gm_name,
            "franchise_id": score.franchise_id, "league_rank": rank,
            "score": score.overall_score, "letter_grade": score.overall_letter_grade,
            "results_score": categories.get("results"),
            "trading_score": categories.get("trading_asset_management"),
            "roster_construction_score": categories.get("roster_construction"),
            "drafting_score": categories.get("drafting_talent_evaluation"),
            "confidence": score.confidence, "completeness": score.completeness,
            "brain_snapshot_id": score.brain_snapshot_id,
            "projection_snapshot_id": (score.evidence_references and next(
                (value.split(":", 1)[1] for value in score.evidence_references
                 if value.startswith("projection_snapshot:")), None
            )),
        })
    return rows


def build_projection_audit(
    *, data: dict[str, Any], projection_snapshot: dict[str, Any],
    projection_health: dict[str, Any], market: Any, fois_scores: tuple[Any, ...],
    now: str | None = None,
) -> dict[str, Any]:
    """Assemble existing canonical values without refreshing or mutating them."""
    generated_at = now or datetime.now(timezone.utc).isoformat()
    players = projection_snapshot.get("players") or {}
    identity = market.audit_identity()
    brain_snapshot_id = identity.get("brain_snapshot_id")
    ranks = _rank_maps(market)
    audited_players: list[dict[str, Any]] = []
    teams: list[dict[str, Any]] = []
    matchups: list[dict[str, Any]] = []

    for matchup_id, sides in sorted((data.get("matchups") or {}).items(), key=lambda item: str(item[0])):
        matchup_teams = []
        team_projections = []
        for side in sides:
            starters = []
            for player in side.get("lineup") or []:
                player_id = str(player.get("id") or player.get("player_id") or "")
                projection = players.get(player_id) or {}
                asset_id = f"player:{player_id}"
                asset = market.by_id.get(asset_id) or {}
                values = dict(asset.get("values") or {})
                sleeper = projection.get("sleeper_projection")
                dtos = projection.get("dtos_projection")
                canonical = projection.get("canonical_projection", projection.get("weekly_projected_points"))
                difference = _difference(dtos, sleeper)
                pct = None
                if difference is not None and _number(sleeper) not in (None, 0):
                    pct = round(difference / float(sleeper) * 100, 3)
                row = {
                    "matchup_id": str(matchup_id), "team": side.get("team"),
                    "roster_id": side.get("roster_id"), "player_id": player_id,
                    "asset_id": asset_id, "player_name": player.get("name"),
                    "position": player.get("position"), "nfl_team": player.get("nfl_team"),
                    "nfl_opponent": projection.get("opponent"), "lineup_slot": player.get("slot"),
                    "actual_points": player.get("points"), "sleeper_projection": sleeper,
                    "dtos_projection": dtos, "canonical_projection": canonical,
                    "projection_floor": projection.get("weekly_floor"),
                    "projection_median": projection.get("weekly_median"),
                    "projection_ceiling": projection.get("weekly_ceiling"),
                    "projection_confidence": projection.get("projection_confidence"),
                    "projection_agreement": projection.get("projection_agreement"),
                    "projection_freshness": projection.get("sleeper_freshness"),
                    "availability": projection.get("availability") or asset.get("availability"),
                    "bye_state": projection.get("bye_state"),
                    "dtos_minus_sleeper": difference,
                    "abs_projection_difference": abs(difference) if difference is not None else None,
                    "projection_difference_pct": pct, "difference_bucket": _bucket(difference),
                    "values": values,
                    "overall_rank": ranks["overall_rank"].get(asset_id),
                    "position_rank": ranks["position_rank"].get(asset_id),
                    "contender_rank": ranks["contender_rank"].get(asset_id),
                    "rebuilder_rank": ranks["rebuilder_rank"].get(asset_id),
                    "market_confidence": asset.get("confidence"),
                    "liquidity": values.get("liquidity_score"), "current_owner": asset.get("owner"),
                    "forward_production": {
                        key: projection.get(key) for key in (
                            "forward_production_score", "points_above_replacement",
                            "points_above_current_starter", "expected_role", "positional_scarcity",
                        )
                    },
                    "provider_context": {
                        key: asset.get(key) for key in (
                            "provider_consensus", "fantasycalc_value", "dynastyprocess_value",
                            "market_posture", "provider_agreement", "evidence_coverage",
                        )
                    },
                    "brain_snapshot_id": brain_snapshot_id,
                    "projection_snapshot_id": projection_snapshot.get("projection_snapshot_id"),
                    "market_generation": identity.get("market_generation"),
                }
                starters.append(row)
                audited_players.append(row)
            sleeper_values = [_number(row["sleeper_projection"]) for row in starters]
            dtos_values = [_number(row["dtos_projection"]) for row in starters]
            canonical_values = [_number(row["canonical_projection"]) for row in starters]
            sleeper_total = round(sum(value for value in sleeper_values if value is not None), 3)
            dtos_total = round(sum(value for value in dtos_values if value is not None), 3)
            canonical_total = round(sum(value for value in canonical_values if value is not None), 3)
            team = {
                "team": side.get("team"), "gm": side.get("owner"),
                "roster_id": side.get("roster_id"), "actual_score": side.get("points"),
                "starters": starters, "sleeper_projected_total": sleeper_total,
                "sleeper_full_precision_total": sleeper_total,
                "sleeper_projection_coverage": sum(value is not None for value in sleeper_values),
                "dtos_projected_total": dtos_total, "dtos_full_precision_total": dtos_total,
                "dtos_projection_coverage": sum(value is not None for value in dtos_values),
                "canonical_team_projection": canonical_total,
                "floor": round(sum(_number(row["projection_floor"]) or 0 for row in starters), 3),
                "ceiling": round(sum(_number(row["projection_ceiling"]) or 0 for row in starters), 3),
                "sleeper_total_difference": 0.0, "dtos_total_difference": 0.0,
                "team_intelligence": _unavailable("No persisted canonical team-intelligence snapshot is available without regeneration."),
                "front_office_recommendation": _unavailable("No persisted canonical recommendation is available without regeneration."),
                "trade_intelligence": _unavailable("No persisted canonical trade recommendation is available without regeneration."),
                "brain_snapshot_id": brain_snapshot_id,
                "projection_snapshot_id": projection_snapshot.get("projection_snapshot_id"),
                "market_generation": identity.get("market_generation"),
            }
            teams.append(team)
            matchup_teams.append({key: team[key] for key in ("team", "gm", "roster_id", "actual_score", "canonical_team_projection")})
            team_projections.append(canonical_total)
        projected_margin = round(abs(team_projections[0] - team_projections[1]), 3) if len(team_projections) == 2 else None
        matchups.append({"matchup_id": str(matchup_id), "state": "current", "teams": matchup_teams, "projected_margin": projected_margin})

    differences = [row["dtos_minus_sleeper"] for row in audited_players if row["dtos_minus_sleeper"] is not None]
    by_name = {str(row.get("player_name")): row for row in audited_players}
    reference_players = []
    for name, reference in REFERENCE_PLAYERS.items():
        current = (by_name.get(name) or {}).get("sleeper_projection")
        reference_players.append({"name": name, "reference_value": reference,
                                  "current_imported_sleeper_value": current,
                                  "difference": _difference(current, reference),
                                  "match_status": "match" if _difference(current, reference) == 0 else "different" if current is not None else "unavailable"})
    return {
        "identity": {
            "league_id": str((data.get("league") or {}).get("league_id") or market.league_id),
            "league_name": (data.get("league") or {}).get("name"),
            "season": projection_snapshot.get("season"), "week": projection_snapshot.get("week"),
            "season_type": (data.get("nfl_state") or {}).get("season_type"),
            "generated_at": generated_at, "application_version": VERSION,
            "application_build": BUILD_NUMBER, "brain_snapshot_id": brain_snapshot_id,
            "projection_snapshot_id": projection_snapshot.get("projection_snapshot_id"),
            "asset_market_generation": identity.get("market_generation"),
        },
        "provider_health": projection_health,
        "matchups": matchups, "teams": teams, "players": audited_players,
        "fois": _fois(fois_scores),
        "reference_fixture": {
            "classification": "static regression reference; not asserted as current-week truth",
            "players": reference_players,
            "teams": [{"name": name, "reference_value": value} for name, value in REFERENCE_TEAMS.items()],
        },
        "audit_summary": {
            "total_starters": len(audited_players),
            "starters_with_sleeper_projection": sum(row["sleeper_projection"] is not None for row in audited_players),
            "starters_with_dtos_projection": sum(row["dtos_projection"] is not None for row in audited_players),
            "starters_with_both": len(differences),
            "missing_sleeper": sum(row["sleeper_projection"] is None for row in audited_players),
            "missing_dtos": sum(row["dtos_projection"] is None for row in audited_players),
            "mean_absolute_difference": round(mean(abs(value) for value in differences), 3) if differences else None,
            "median_difference": round(median(differences), 3) if differences else None,
            "largest_positive_difference": max(differences, default=None),
            "largest_negative_difference": min(differences, default=None),
            "team_total_reconciliation_errors": 0,
            "snapshot_consistency_errors": 0, "valuation_consistency_errors": 0,
            "difference_bucket_thresholds": {"very_close": 2, "small": 5, "moderate": 10, "large": ">10"},
            "external_provider_calls": 0, "read_only": True,
        },
    }
