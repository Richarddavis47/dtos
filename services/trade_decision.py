"""Decision presentation over completed shared evidence; no scoring or discovery."""

from hashlib import sha256
import json
from math import isfinite


def decision_context(result, *, incoming=(), outgoing=()):
    dimensions = result.get("dimensions") or {}
    strategy = (dimensions.get("strategic_fit") or {}).get("active") or {}
    intent = strategy.get("manager_strategy") or {}
    capital = strategy.get("future_capital") or {}
    needs_strategy = bool(
        capital.get("sent") or capital.get("received")
    ) and not intent.get("strategy")
    diagnostic = ((dimensions.get("roster_diagnostics") or {}).get("sides") or {}).get(
        "active"
    ) or {}
    current = (strategy.get("horizons") or {}).get("current_week") or {}
    delta = current.get("delta")
    numeric_state = diagnostic.get("numeric_impact_state") or "unavailable"
    if numeric_state == "unsupported":
        delta = None
    blockers = []
    if result.get("legal") is False:
        blockers.append(
            "Resolve the stated ownership, identity or roster blocker before pursuing this offer."
        )
    market = result.get("market_evidence") or {}
    if market.get("availability") != "full":
        blockers.append(
            "Some current Market prices are unavailable or incompatible; package comparison is incomplete."
        )
    if needs_strategy:
        blockers.append(
            "Choose WIN NOW, RETOOL or REBUILD to resolve the future-capital strategy trade-off; the supported competitive window has not established a direction."
        )
    if strategy.get("projection_coverage_complete") is False:
        blockers.append(
            "Projection or legal-lineup coverage is incomplete for one or more requested periods."
        )
    if (strategy.get("roster_capacity") or {}).get("additional_spots_to_resolve"):
        blockers.append(
            "The full package requires roster-space decisions; cut cost is unresolved."
        )
    qualifier = "Conditional " if numeric_state != "supported" else ""
    if delta is None:
        lineup = "Starting-lineup improvement is unavailable from compatible current-week evidence."
    elif delta > 0:
        lineup = f"{qualifier}current-week optimal legal-lineup gain: {delta:.2f} projected points."
    elif delta < 0:
        lineup = f"{qualifier}current-week optimal legal-lineup cost: {abs(delta):.2f} projected points."
    else:
        gain = any(
            value > 0 for value in (strategy.get("reserve_slot_changes") or {}).values()
        )
        lineup = "Current-week optimal starters are unchanged" + (
            "; supported reserve coverage improves in some weeks."
            if gain
            else "; do not treat added depth as a starter upgrade."
        )
    cost = (
        result.get("major_drawback")
        or "The available assessment does not establish a main cost; inspect evidence before deciding."
    )
    gained = [asset for asset in incoming if asset.kind == "player"]
    lost = [asset for asset in outgoing if asset.kind == "player"]
    if len(gained) == len(lost) == 1:
        older, younger = gained[0], lost[0]
        if (
            all(
                isinstance(a.age, (int, float))
                and not isinstance(a.age, bool)
                and isfinite(a.age)
                for a in (older, younger)
            )
            and older.age > younger.age
        ):
            cost += f" You give up {younger.label} (age {younger.age:g}) for {older.label} (age {older.age:g}); age does not guarantee future value or health."
    resolved = intent.get("strategy")
    fit = (strategy.get("capital_strategy_fit") or {}).get("explanation")
    context = (
        fit
        if resolved and fit
        else "Competitive direction remains unresolved."
        if needs_strategy
        else result.get("why_you_would_do_it")
        or "No supported positive roster-specific case is established."
    )
    conditional = []
    if needs_strategy:
        conditional = [
            "For a contender, weigh supported starter and usable-depth effects against future capital spent.",
            "For a rebuilding team, weigh future flexibility and asset quality against production surrendered. These are conditional considerations, not DTOS verdicts.",
        ]
    limitations = (diagnostic.get("evidence") or {}).get("limitations") or []
    incoming_ids = {asset.asset_id for asset in incoming if asset.kind == "player"}
    uncertain = [
        row
        for row in diagnostic.get("post_eligibility") or []
        if row.get("player_id") in incoming_ids
        and (row.get("excluded") or row.get("status") != "active")
    ]
    availability = (
        "Incoming availability: "
        + "; ".join(
            row["name"] + " · " + (row.get("reason") or row.get("status") or "Unknown")
            for row in uncertain[:3]
        )
        if uncertain
        else ""
    )
    if len(uncertain) > 3:
        availability += f"; {len(uncertain) - 3} more in roster evidence."
    limitation = (
        " ".join(
            t for t in (availability, limitations[0] if limitations else None) if t
        )
        or None
    )
    return {
        "verdict": result.get("recommendation"),
        "summary": context,
        "blocker": " ".join(blockers) if not result.get("recommendation") else None,
        "strategy": {
            "resolved": resolved,
            "source": intent.get("source") or "unavailable",
            "state": "resolved" if resolved else "unresolved",
            "selection_required": needs_strategy,
        },
        "lineup": {"delta": delta, "state": numeric_state, "explanation": lineup},
        "main_cost": cost,
        "limitation": limitation,
        "conditional": conditional,
        "next_action": "Choose strategy and reevaluate"
        if needs_strategy
        else "Inspect the main drawback, edit or reevaluate this trade.",
    }


def selected_player_facts(data, assets, projections):
    """Only selected assets; one pinned prepared week, no provider or SQL calls."""
    from services.player_projection_view import player_projection_views
    from src.core.player_value_projection.canonical_production import (
        prepared_production_context,
    )
    from src.core.projection_intelligence.sleeper_provider import freshness_state

    ids = [a.asset_id for a in assets if a.kind == "player"]
    views = player_projection_views(data, ids, projections)
    league = data.get("league") or {}
    league_id = str(league.get("league_id") or "")
    scoring = data.get("scoring_settings") or league.get("scoring_settings") or {}
    valid_scoring = (
        isinstance(scoring, dict)
        and scoring
        and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v)
            for v in scoring.values()
        )
    )
    fingerprint = (
        sha256(
            json.dumps(
                scoring, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        if valid_scoring
        else None
    )
    prepared = data.get("canonical_player_production") or {}
    compatible = (
        bool(scoring)
        and str(prepared.get("league_id")) == league_id
        and str(prepared.get("season")) == str(league.get("season"))
        and prepared.get("scoring_fingerprint") == fingerprint
        and bool(prepared.get("generation"))
    )
    pinned = projections.snapshot() or {}
    reader = getattr(projections, "service", projections)
    refresh = (
        reader.refresh_evidence(pinned) if hasattr(reader, "refresh_evidence") else {}
    )
    week = int(data.get("week") or 1)
    snapshot = (
        projections.week_snapshot(week, generation_snapshot=pinned)
        if ids and str(week) in (pinned.get("horizon_snapshot_ids") or {})
        else {}
    )
    result = {}
    for asset in assets:
        if asset.kind != "player":
            continue
        pid = asset.asset_id
        player = (data.get("players") or {}).get(pid) or {}
        projection = dict(views[pid])
        source = ((snapshot or {}).get("players") or {}).get(pid) or {}
        projection.update(
            source_observed_at=source.get("source_timestamp"),
            freshness=freshness_state(source.get("source_timestamp")),
            retained_qualification=source.get("source_freshness")
            or source.get("sleeper_freshness"),
            refresh_evidence=refresh,
        )
        production = {
            "points_per_game": None,
            "sample_games": None,
            "season": league.get("season"),
            "league_id": league_id,
            "scoring_fingerprint": fingerprint,
            "source": None,
            "generation": None,
            "observed_at": None,
            "limitations": [
                "Compatible prepared actual production is unavailable; no zero or season rank is inferred."
            ],
        }
        if compatible:
            context = prepared_production_context(
                prepared, league_id=league_id, player_id=pid
            )
            average = next(
                (
                    w.fantasy_points
                    for w in context.windows
                    if w.label == "Season Average"
                ),
                None,
            )
            sample = (prepared.get("players") or {}).get(pid) or {}
            production.update(
                points_per_game=average,
                sample_games=sample.get("current_sample_count"),
                source=context.source,
                generation=prepared["generation"],
                observed_at=context.updated_at,
                limitations=list(context.limitations),
            )
        age = asset.age
        if (
            not isinstance(age, (int, float))
            or isinstance(age, bool)
            or not isfinite(age)
        ):
            age = None
        result[pid] = {
            "player_id": pid,
            "name": asset.label,
            "nfl_team": player.get("team"),
            "age": age,
            "status": player.get("status") or "Unknown",
            "position": asset.position,
            "eligible_positions": player.get("fantasy_positions")
            or ([asset.position] if asset.position else []),
            "current_market": asset.trade_value,
            "market_evidence": asset.market_fact,
            "market_rank": {
                "label": "Market positional rank",
                "rank": asset.positional_rank,
                "cohort": "Priced rostered players in the selected league",
            },
            "season_fantasy_points_rank": None,
            "points_per_game_rank": None,
            "rank_limitation": "No compatible complete production-rank cohort is prepared.",
            "projection": projection,
            "production": production,
        }
    return result
