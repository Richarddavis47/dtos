"""Adapter from canonical Historical Memory records to FOIS Results facts."""
from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Any

from src.core.history_context.store import CanonicalHistoryStore as HistoricalStore


def _positive_int(value: Any) -> int | None:
    """Return a positive integer identity or explicit unavailability."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def load_results_history(
    store: HistoricalStore,
    league_id: str,
    *,
    metrics: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build provider-free FOIS histories from immutable cached evidence."""
    started = perf_counter()
    _, standings = store.records(league_id, "season_standing", limit=10_000)
    _, playoffs = store.records(league_id, "playoff_result", limit=1_000)
    _, matchups = store.records(league_id, "matchup", limit=100_000)
    _, identities = store.records(league_id, "franchise_identity", limit=10_000)
    _, league_seasons = store.records(league_id, "league_season", limit=1_000)
    playoff_by_season = {
        int(row["season"]): row["payload"]
        for row in playoffs
        if row.get("season") is not None
    }
    league_size = {
        int(row["season"]): int(row["payload"].get("total_rosters") or 0) or None
        for row in league_seasons
        if row.get("season") is not None
    }
    league_status = {
        int(row["season"]): str(row["payload"].get("status") or "").casefold()
        for row in league_seasons
        if row.get("season") is not None
    }
    completed_seasons = {
        season for season, status in league_status.items() if status == "complete"
    }
    base_history_ms = round((perf_counter() - started) * 1000, 3)
    numeric_placement_seasons: set[int] = set()
    owners: dict[str, set[str]] = defaultdict(set)
    owner_by_roster_season: dict[tuple[str, int], str] = {}
    for row in identities:
        roster_id = str(row["payload"].get("sleeper_roster_id") or "")
        owner_id = str(row["payload"].get("owner_id") or "")
        if roster_id and owner_id:
            owners[roster_id].add(owner_id)
            if row.get("season") is not None:
                owner_by_roster_season[(roster_id, int(row["season"]))] = owner_id
    records: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    for row in matchups:
        payload = row["payload"]
        if payload.get("postseason_context") or row.get("season") is None:
            continue
        season = int(row["season"])
        winner = payload.get("winner")
        loser = payload.get("loser")
        if winner is not None:
            records[(str(winner), season)][0] += 1
        if loser is not None:
            records[(str(loser), season)][1] += 1
    histories: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"seasons": [], "trades": [], "drafts": []}
    )
    expected = len(league_size)
    for row in standings:
        payload = row["payload"]
        season = int(row["season"])
        roster_id = str(payload.get("roster_id") or "")
        if not roster_id.isdigit() or int(roster_id) < 1:
            # Historical Memory can contain provider evidence that is valid for
            # other consumers but is not a usable franchise standing. FOIS must
            # not let that optional evidence block canonical application startup.
            continue
        playoff = playoff_by_season.get(season, {})
        placements = {}
        for raw_place, raw_roster in (playoff.get("placements") or {}).items():
            place = _positive_int(raw_place)
            roster = _positive_int(raw_roster)
            if place is not None and roster is not None:
                placements[place] = roster
                numeric_placement_seasons.add(season)
        finish_by_roster = {roster: place for place, roster in placements.items()}
        roster_number = int(roster_id)
        playoff_finish = finish_by_roster.get(roster_number)
        matchup_wins, matchup_losses = records[(roster_id, season)]
        histories[roster_id]["seasons"].append({
            "season": season,
            "wins": payload.get("wins"),
            "losses": payload.get("losses"),
            "finish": payload.get("rank"),
            "playoff_finish": (
                str(playoff_finish) if playoff_finish is not None else None
            ),
            "championship": playoff.get("champion_roster_id") == roster_number,
            "rebuilding": False,
            "league_size": league_size.get(season),
            "playoff": playoff_finish is not None,
            "final_four": roster_number in (playoff.get("final_four_roster_ids") or []),
            "championship_game": playoff_finish in {1, 2},
            "matchup_wins": matchup_wins if matchup_wins + matchup_losses else None,
            "matchup_losses": matchup_losses if matchup_wins + matchup_losses else None,
            "complete": (
                season in completed_seasons
                if league_status.get(season)
                else row.get("availability") not in {"incomplete", "unavailable"}
            ),
        })
        histories[roster_id].setdefault("owner_by_season", {})[str(season)] = (
            owner_by_roster_season.get((roster_id, season))
        )
    _, trades = store.records(league_id, "trade", limit=100_000)
    from src.core.intelligence_memory import intelligence_checkpoint_store
    from src.core.intelligence_memory.fois import fois_process_evidence
    trade_checkpoints: dict[str, list[Any]] = defaultdict(list)
    for checkpoint in intelligence_checkpoint_store.checkpoints(
        league_id=league_id, limit=10_000,
    ):
        if checkpoint.related_event_id:
            trade_checkpoints[str(checkpoint.related_event_id)].append(checkpoint)
    # Step 4 is the canonical no-hindsight decision-evidence boundary.  Build it
    # once in this background history adapter and pass only its bounded results
    # forward; request-time consumers never replay or scan raw history.
    from src.core.historical_franchise_state import HistoricalFranchiseStateService
    from src.core.historical_intelligence import (
        HistoricalEventType, HistoricalIntelligenceService,
    )
    from src.core.historical_transaction_intelligence import (
        HistoricalTransactionIntelligenceService,
    )
    history_intelligence = HistoricalIntelligenceService(
        store, checkpoint_reader=intelligence_checkpoint_store,
    )
    transaction_intelligence = HistoricalTransactionIntelligenceService(
        history_intelligence, HistoricalFranchiseStateService(history_intelligence),
    )
    step4 = {}
    step4_started = perf_counter()
    try:
        step4_events = history_intelligence.events_for_league(
            league_id, event_type=HistoricalEventType.TRADE,
        )[:1000]
    except ValueError:
        step4_events = ()
    for event in step4_events:
        try:
            step4[event.source_record_id] = transaction_intelligence.evaluate_trade(
                league_id, event.event_id,
            )
        except (KeyError, ValueError):
            # Invalid canonical history stays explicit through the legacy
            # unavailable evidence below; it is never fabricated or zero-filled.
            continue
    step4_ms = round((perf_counter() - step4_started) * 1000, 3)
    process_scores = {
        "strong_process": 90.0, "sound_process": 80.0,
        "defensible_optional": 65.0, "questionable_process": 40.0,
        "poor_process": 20.0,
    }
    outcome_scores = {
        "strong_positive_outcome": 90.0, "positive_outcome": 75.0,
        "mixed_neutral": 50.0, "negative_outcome": 25.0,
        "strong_negative_outcome": 10.0,
    }
    for row in trades:
        payload = row["payload"]
        season = int(row.get("season") or 0)
        transaction_id = str(row["source_record_id"])
        process = fois_process_evidence(trade_checkpoints.get(transaction_id, ()))
        checkpoints = tuple(trade_checkpoints.get(transaction_id, ()))
        roster_values: dict[str, float] = defaultdict(float)
        definitive = tuple(
            checkpoint for checkpoint in checkpoints
            if checkpoint.provenance_type.definitive_process_evidence
            and checkpoint.market_value is not None
        )
        for checkpoint in definitive:
            if checkpoint.roster_id is not None:
                roster_values[str(checkpoint.roster_id)] += float(checkpoint.market_value)
        fully_gradable = bool(checkpoints) and len(definitive) == len(checkpoints)
        for roster_id in payload.get("roster_ids") or ():
            partners = [
                str(value) for value in payload.get("roster_ids") or ()
                if str(value) != str(roster_id)
            ]
            evaluation = step4.get(transaction_id)
            franchise_id = f"{league_id}:franchise:{roster_id}"
            side = next((
                item for item in evaluation.sides
                if item.franchise_id == franchise_id
                or item.franchise_id.rsplit(":", 1)[-1] == str(roster_id)
            ), None) if evaluation is not None else None
            process_classification = (
                side.process.classification.value if side is not None else None
            )
            outcome_classification = (
                side.outcome.classification.value if side is not None else None
            )
            histories[str(roster_id)]["trades"].append({
                "transaction_id": transaction_id,
                "season": season,
                "occurred_at": row.get("occurred_at"),
                "strategically_productive": None,
                "market_overpay_percent": None,
                "championship_outlook_delta": None,
                "partner_id": partners[0] if len(partners) == 1 else None,
                "owner_id": owner_by_roster_season.get((str(roster_id), season)),
                "process_evidence": process,
                "process_score": (
                    process_scores.get(process_classification)
                    if side is not None else round(
                        50 + 50 * (
                            roster_values.get(str(roster_id), 0.0)
                            - sum(value for key, value in roster_values.items() if key != str(roster_id))
                        ) / max(1.0, sum(roster_values.values())),
                        2,
                    )
                    if fully_gradable and roster_values else None
                ),
                "outcome_score": outcome_scores.get(outcome_classification),
                "process_classification": process_classification,
                "process_confidence": side.process.confidence.value if side is not None else None,
                "outcome_classification": outcome_classification,
                "outcome_confidence": side.outcome.confidence.value if side is not None else None,
                "outcome_maturity": side.outcome.maturity if side is not None else None,
                "history_generation": evaluation.history_generation if evaluation is not None else None,
                "market_generation": evaluation.market_generation if evaluation is not None else None,
                "evidence_references": evaluation.evidence_references if evaluation is not None else (),
            })
    _, draft_picks = store.records(league_id, "draft_pick", limit=100_000)
    for row in draft_picks:
        payload = row["payload"]
        roster_id = str(payload.get("roster_id") or "")
        if not roster_id:
            continue
        histories[roster_id]["drafts"].append({
            "draft_id": str(payload.get("draft_id") or row["source_record_id"]),
            "season": int(row.get("season") or 0),
            "pick_number": payload.get("pick_no"),
            "value_over_expected": None,
        })
    _, transactions = store.records(league_id, "transaction", limit=100_000)
    for row in transactions:
        payload = row["payload"]
        season = int(row.get("season") or 0)
        transaction_id = str(row["source_record_id"])
        roster_ids = {
            str(value) for value in payload.get("roster_ids") or () if value is not None
        }
        roster_ids.update(str(value) for value in (payload.get("adds") or {}).values())
        roster_ids.update(str(value) for value in (payload.get("drops") or {}).values())
        waiver_budget = payload.get("waiver_budget") or ()
        for roster_id in roster_ids:
            histories[roster_id].setdefault("waivers", []).append({
                "transaction_id": transaction_id,
                "season": season,
                "value_created": None,
                "faab_efficiency": None,
                "meaningful": bool(payload.get("adds") or payload.get("drops") or waiver_budget),
            })
    for roster_id, history in histories.items():
        history["seasons"].sort(key=lambda row: row["season"])
        history["ownership_changes"] = max(0, len(owners[roster_id]) - 1)
        history["expected_seasons"] = expected
        placement_seasons = completed_seasons if league_status else set(league_size)
        placement_expected = len(placement_seasons)
        placement_available = len(
            numeric_placement_seasons & placement_seasons
        )
        history["placement_seasons_available"] = placement_available
        history["placement_seasons_expected"] = placement_expected
        history["placement_completeness"] = round(
            placement_available / placement_expected * 100, 2,
        ) if placement_expected else 0.0
    if metrics is not None:
        transaction_metrics = transaction_intelligence.health()
        state_metrics = transaction_intelligence.states.metrics()
        total_ms = round((perf_counter() - started) * 1000, 3)
        metrics.update({
            "base_history_ms": base_history_ms,
            "step4_evaluation_ms": step4_ms,
            "front_office_history_aggregation_ms": round(
                total_ms - base_history_ms - step4_ms, 3,
            ),
            "total_history_ms": total_ms,
            "step4_evaluations_loaded": len(step4),
            "step4_evaluations_recomputed": int(
                transaction_metrics.get("evaluations") or 0
            ),
            "step4_evaluations_reused": int(
                transaction_metrics.get("cache_hits") or 0
            ),
            "step3_reconstructions": int(
                state_metrics.get("reconstructions") or 0
            ),
            "derived_cache_hits": int(state_metrics.get("cache_hits") or 0),
            "source_record_queries": int(
                state_metrics.get("source_record_queries") or 0
            ),
            "provider_calls": 0,
            "raw_history_scans": 0,
        })
    return dict(histories)
