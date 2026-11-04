"""Bounded, explainable eligibility for sparse global market checkpoints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .market_memory import MarketObservationMaterialityPolicy


MILESTONE_REASON_PREFIXES = (
    "current_", "historical_", "top_free_agent", "rookie", "prospect",
)
PASS_CATCHER_POSITIONS = frozenset({"RB", "WR", "TE"})


@dataclass(frozen=True)
class RelatedPlayerCandidate:
    asset_id: str
    relationship: str


def milestone_asset_ids(data: Mapping[str, Any]) -> tuple[str, ...]:
    """Select only explicit Relevant Player Universe members with useful reasons."""
    universe = data.get("relevant_player_universe") or {}
    valuation = (data.get("valuation_intelligence") or {}).get("assets") or {}
    rows = universe.get("members") or ()
    selected = set()
    for row in rows:
        player_id = str(row.get("player_id") or "")
        reasons = tuple(str(value) for value in row.get("reason_codes") or ())
        asset_id = player_id if player_id.startswith("player:") else f"player:{player_id}"
        if (
            player_id
            and asset_id in valuation
            and any(reason.startswith(MILESTONE_REASON_PREFIXES) for reason in reasons)
        ):
            selected.add(asset_id)
    return tuple(sorted(selected))


def related_player_candidates(
    data: Mapping[str, Any], primary_asset_ids: Iterable[str], *, maximum: int = 12,
) -> tuple[RelatedPlayerCandidate, ...]:
    """Return a small authoritative team/role neighborhood, never a universe scan."""
    players = data.get("normalized_players") or data.get("players") or {}
    primary_ids = {
        str(value).removeprefix("player:") for value in primary_asset_ids
        if str(value).startswith("player:")
    }
    candidates: dict[str, RelatedPlayerCandidate] = {}
    priority = {"qb_pass_catcher": 0, "depth_chart_competition": 1, "same_nfl_offense": 2}
    for primary_id in sorted(primary_ids):
        primary = players.get(primary_id) or {}
        team = str(primary.get("team") or "")
        position = str(primary.get("position") or "").upper()
        if not team:
            continue
        for player_id, row in players.items():
            player_id = str(player_id)
            if player_id in primary_ids or str(row.get("team") or "") != team:
                continue
            other_position = str(row.get("position") or "").upper()
            if (
                (position == "QB" and other_position in PASS_CATCHER_POSITIONS)
                or (other_position == "QB" and position in PASS_CATCHER_POSITIONS)
            ):
                relationship = "qb_pass_catcher"
            elif position and position == other_position:
                relationship = "depth_chart_competition"
            else:
                relationship = "same_nfl_offense"
            asset_id = f"player:{player_id}"
            existing = candidates.get(asset_id)
            if existing is None or priority[relationship] < priority[existing.relationship]:
                candidates[asset_id] = RelatedPlayerCandidate(asset_id, relationship)
    return tuple(sorted(
        candidates.values(), key=lambda row: (priority[row.relationship], row.asset_id),
    )[:max(0, int(maximum))])


def material_related_candidates(
    candidates: Iterable[RelatedPlayerCandidate], *,
    before: Mapping[str, float | int | None],
    after: Mapping[str, float | int | None],
    policy: MarketObservationMaterialityPolicy | None = None,
) -> tuple[RelatedPlayerCandidate, ...]:
    selected_policy = policy or MarketObservationMaterialityPolicy()
    return tuple(
        candidate for candidate in candidates
        if selected_policy.value_changed(
            before.get(candidate.asset_id), after.get(candidate.asset_id),
        )
    )
