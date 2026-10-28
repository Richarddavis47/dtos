"""Canonical league-configured optimal legal lineup construction."""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from math import isfinite
from typing import Any, Iterable


BENCH_SLOTS = {"BN", "BENCH", "IR", "TAXI", "RESERVE"}
FLEX_ELIGIBILITY = {
    "FLEX": {"RB", "WR", "TE"},
    "REC_FLEX": {"WR", "TE"},
    "WRRB_FLEX": {"WR", "RB"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "SF": {"QB", "RB", "WR", "TE"},
}


@dataclass(frozen=True)
class LineupEntry:
    slot: str
    asset_id: str
    label: str
    position: str
    projected_points: float


@dataclass(frozen=True)
class OptimalLineup:
    entries: tuple[LineupEntry, ...]
    projected_points: float | None
    available: bool
    reason: str | None = None
    unsupported_slots: tuple[str, ...] = ()
    known_starters_subtotal: float | None = None
    missing_player_ids: tuple[str, ...] = ()


def _projection(player: dict[str, Any]) -> float | None:
    for key in ("projected_points", "projection", "pregame_projection", "dtos_projection"):
        value = player.get(key)
        if isinstance(value, dict):
            value = value.get("projected_points") if "projected_points" in value else value.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
            return float(value)
        if key in player:
            return None
    return None


def _eligible(position: str, slot: str) -> bool:
    slot = slot.upper()
    position = position.upper()
    return position == slot or position in FLEX_ELIGIBILITY.get(slot, set())


def eligible_positions(player: dict[str, Any]) -> tuple[str, ...]:
    """Explicit fantasy eligibility is separate from the player's NFL position.

    Legacy inputs retain their single position. Malformed or explicitly empty
    fantasy eligibility cannot manufacture another eligible position.
    """
    values = player.get('fantasy_positions')
    if values is None:
        position = str(player.get('position') or '').upper()
        return (position,) if position else ()
    if not isinstance(values, (list, tuple)) or any(
            not isinstance(value, str) or not value.strip() for value in values):
        return ()
    return tuple(sorted({value.strip().upper() for value in values}))


def optimal_legal_lineup(players: Iterable[dict[str, Any]], roster_positions: Iterable[str], *, week: int | None = None) -> OptimalLineup:
    """Return the highest-projected legal lineup without mutating submitted slots."""
    pool = []
    seen = set()
    missing = []
    for player in players:
        projection = _projection(player)
        position = str(player.get("position") or "").upper()
        fantasy_positions = eligible_positions(player)
        asset_id = str(player.get("id") or player.get("player_id") or "")
        if asset_id in seen:
            raise ValueError("Duplicate player identity in lineup evidence")
        seen.add(asset_id)
        if (str(player.get("roster_slot") or "").upper() in {"IR", "TAXI", "RESERVE"}
                or player.get("lineup_eligible") is False
                or (week is not None and player.get("bye_week") == week)):
            continue
        if projection is None and asset_id:
            missing.append(asset_id)
        if projection is not None and fantasy_positions and asset_id:
            pool.append((projection, asset_id, position, str(player.get("name") or player.get("full_name") or asset_id), fantasy_positions))
    slots = [str(slot).upper() for slot in roster_positions if str(slot).upper() not in BENCH_SLOTS]
    if not slots:
        return OptimalLineup((), None, False, "League starting-lineup configuration is unavailable.")
    if not pool:
        return OptimalLineup((), None, False, "Trustworthy player projections are unavailable.", tuple(slots), None, tuple(sorted(missing)))

    # Exact bounded assignment: process each player once across at most 2^starting_slots states.
    # Equal-score ties use the canonical (slot, asset) assignment for deterministic output.
    slots.sort(key=lambda slot: (len(FLEX_ELIGIBILITY.get(slot, {slot})), slot))
    states: dict[int, tuple[float, tuple[LineupEntry, ...]]] = {0: (0.0, ())}
    for projection, asset_id, position, label, fantasy_positions in sorted(pool, key=lambda row: (-row[0], row[1])):
        # Eligibility depends on the player and configured slot, never on a
        # partial assignment. Evaluate it once rather than once per DP state.
        eligible_slots = []
        for index, slot in enumerate(slots):
            eligible = tuple(pos for pos in fantasy_positions if _eligible(pos, slot))
            if eligible:
                assigned_position = position if position in eligible else eligible[0]
                eligible_slots.append((index, slot, 1 << index, assigned_position))
        updated = dict(states)
        for mask, (score, selected) in states.items():
            for index, slot, bit, assigned_position in eligible_slots:
                if mask & bit:
                    continue
                # Identical slots are interchangeable. Keep only their prefix-filled
                # state, preserving every legal assignment and canonical tie-break.
                if index and slots[index - 1] == slot and not mask & (1 << (index - 1)):
                    continue
                candidate_score = score + projection
                current = updated.get(mask | bit)
                if current is not None and candidate_score < current[0]:
                    continue
                # Tie keys matter only on equal scores. Building them for every
                # losing/winning assignment added substantial profiled overhead.
                if current is None or candidate_score > current[0] or (
                        tuple((entry.slot, entry.asset_id) for entry in selected) + ((slot, asset_id),) <
                        tuple((entry.slot, entry.asset_id) for entry in current[1])):
                    updated[mask | bit] = (candidate_score,
                        selected + (LineupEntry(slot, asset_id, label, assigned_position, projection),))
        states = updated
    _, entries = max(states.values(), key=lambda row: (len(row[1]), row[0], tuple((entry.slot, entry.asset_id) for entry in row[1])))
    if not entries:
        return OptimalLineup((), None, False, "No projected players are eligible for configured starting slots.")
    subtotal = sum(row.projected_points for row in entries)
    unsupported = tuple((Counter(slots) - Counter(row.slot for row in entries)).elements())
    complete = not unsupported
    reason = ("Required starting slots lack supported eligible projections." if unsupported else
              "Optimal among supported projections; other player projections are unavailable." if missing else None)
    return OptimalLineup(tuple(entries), subtotal if complete else None, complete,
                         reason, unsupported, subtotal, tuple(sorted(missing)))


def apply_trade_players(
    players: Iterable[dict[str, Any]], sent_ids: set[str], received_players: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    retained = [player for player in players if str(player.get("id") or player.get("player_id")) not in sent_ids]
    return tuple(retained + list(received_players))
