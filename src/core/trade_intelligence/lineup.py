"""Canonical league-configured optimal legal lineup construction."""
from __future__ import annotations

from dataclasses import dataclass
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


def _projection(player: dict[str, Any]) -> float | None:
    for key in ("projected_points", "projection", "pregame_projection", "dtos_projection"):
        value = player.get(key)
        if isinstance(value, dict):
            value = value.get("projected_points") or value.get("value")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _eligible(position: str, slot: str) -> bool:
    slot = slot.upper()
    position = position.upper()
    return position == slot or position in FLEX_ELIGIBILITY.get(slot, set())


def optimal_legal_lineup(players: Iterable[dict[str, Any]], roster_positions: Iterable[str]) -> OptimalLineup:
    """Return the highest-projected legal lineup without mutating submitted slots."""
    pool = []
    for player in players:
        projection = _projection(player)
        position = str(player.get("position") or "").upper()
        asset_id = str(player.get("id") or player.get("player_id") or "")
        if projection is not None and position and asset_id:
            pool.append((projection, asset_id, position, str(player.get("name") or player.get("full_name") or asset_id)))
    slots = [str(slot).upper() for slot in roster_positions if str(slot).upper() not in BENCH_SLOTS]
    if not slots:
        return OptimalLineup((), None, False, "League starting-lineup configuration is unavailable.")
    if not pool:
        return OptimalLineup((), None, False, "Trustworthy player projections are unavailable.")

    # Exact bounded assignment: process each player once across at most 2^starting_slots states.
    # Equal-score ties use the canonical (slot, asset) assignment for deterministic output.
    slots.sort(key=lambda slot: (len(FLEX_ELIGIBILITY.get(slot, {slot})), slot))
    states: dict[int, tuple[float, tuple[LineupEntry, ...]]] = {0: (0.0, ())}
    for projection, asset_id, position, label in sorted(pool, key=lambda row: (-row[0], row[1])):
        updated = dict(states)
        for mask, (score, selected) in states.items():
            for index, slot in enumerate(slots):
                bit = 1 << index
                if mask & bit or not _eligible(position, slot):
                    continue
                candidate = (score + projection, selected + (LineupEntry(slot, asset_id, label, position, projection),))
                current = updated.get(mask | bit)
                candidate_key = tuple((entry.slot, entry.asset_id) for entry in candidate[1])
                current_key = tuple((entry.slot, entry.asset_id) for entry in current[1]) if current else ()
                if current is None or candidate[0] > current[0] or (candidate[0] == current[0] and candidate_key < current_key):
                    updated[mask | bit] = candidate
        states = updated
    _, entries = max(states.values(), key=lambda row: (len(row[1]), row[0], tuple((entry.slot, entry.asset_id) for entry in row[1])))
    if not entries:
        return OptimalLineup((), None, False, "No projected players are eligible for configured starting slots.")
    return OptimalLineup(tuple(entries), round(sum(row.projected_points for row in entries), 2), True)


def apply_trade_players(
    players: Iterable[dict[str, Any]], sent_ids: set[str], received_players: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    retained = [player for player in players if str(player.get("id") or player.get("player_id")) not in sent_ids]
    return tuple(retained + list(received_players))
