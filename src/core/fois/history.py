"""Adapter from canonical Historical Memory records to FOIS Results facts."""
from __future__ import annotations

from collections import defaultdict
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
) -> dict[str, dict[str, Any]]:
    """Build provider-free FOIS histories from immutable cached evidence."""
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
    for row in trades:
        payload = row["payload"]
        season = int(row.get("season") or 0)
        for roster_id in payload.get("roster_ids") or ():
            histories[str(roster_id)]["trades"].append({
                "transaction_id": str(row["source_record_id"]),
                "season": season,
                "strategically_productive": None,
                "market_overpay_percent": None,
                "championship_outlook_delta": None,
                "partner_id": None,
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
    return dict(histories)
