"""Exact source asset joins. No selecting-owner or user-ID substitution."""

from __future__ import annotations

from typing import Any


class PlayerWeekIndexLimit(ValueError):
    """League-wide comparison exceeds the temporary index preparation bound."""


def draft_selection_id(league: str, draft: str, selection: Any) -> str | None:
    if not league or not draft or not str(selection).isdigit() or int(selection) < 1:
        return None
    return f"SELECTION-{league}-{draft}-{int(selection)}"


def draft_pick(pick: dict, draft: dict, league: str, season: int) -> dict:
    """Project a selection and independently admitted original-slot evidence."""
    from .timestamps import canonical_draft_bounds, canonical_utc_timestamp

    if draft.get("league_id") is not None and str(draft["league_id"]) != str(league):
        raise ValueError("Foreign draft/league identity cannot establish a selection")
    row = dict(pick)
    row["source_league_id"] = league
    row["selection_id"] = draft_selection_id(
        league, str(row.get("draft_id") or ""), row.get("pick_no")
    )
    row["selecting_roster_id"] = row.get("roster_id")
    # Auction purchases/startup selections do not exercise dynasty franchise picks.
    slots = draft.get("slot_to_roster_id") or {}
    original = row.get("original_roster_id")
    if original is None and str(draft.get("type")).casefold() == "linear":
        original = slots.get(str(row.get("draft_slot")))
    if original is not None and str(original).isdigit() and int(original) > 0:
        row["original_roster_id"] = int(original)
        row["original_identity_provenance"] = (
            "explicit_source_original_or_draft_slot_mapping"
        )
    else:
        row["original_roster_id"] = None
    row["season"] = season
    row["draft_type"] = draft.get("type")
    row["selected_at"] = canonical_utc_timestamp(
        row.get("picked_at") or row.get("created")
    )
    row.update(canonical_draft_bounds(draft))
    return row


def future_pick_id(
    payload: dict, season: int, *, selection: bool = False
) -> str | None:
    original = (
        payload.get("original_roster_id")
        if selection
        else payload.get("roster_id")
        or payload.get("original_roster_id")
        or payload.get("original_franchise")
    )
    year, round_number = payload.get("season") or season, payload.get("round")
    if not all(str(v).isdigit() and int(v) > 0 for v in (year, round_number, original)):
        return None
    return f"PICK-{year}-R{round_number}-ORIG{original}"


def reconcile_player_weeks(rows: list[dict]) -> list[dict]:
    """One player/week score, retaining membership, nullable starts and conflicts."""
    from .results import number

    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        grouped.setdefault(
            (
                row.get("league_id"),
                row.get("season"),
                row.get("week"),
                row.get("player_id"),
            ),
            [],
        ).append(row)
    result = []
    for values in grouped.values():
        scores = {
            number(v["payload"].get("fantasy_points", v["payload"].get("points")))
            for v in values
        }
        known = scores - {None}
        franchises = {v.get("franchise_id") for v in values}
        row = dict(values[0])
        payload = dict(row["payload"])
        score = next(iter(known)) if len(known) == 1 and len(franchises) == 1 else None
        payload.update(
            fantasy_points=score,
            points=score,
            starter=any(v["payload"].get("starter") for v in values),
            scoring_conflict=len(known) > 1 or len(franchises) > 1,
        )
        row["payload"] = payload
        result.append(row)
    return result
