"""Deterministic scoped ranks over an explicit, already-prepared universe."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping

RANK_METHODOLOGY = "batch3-evidence-scopes-v2"


def market_rank_generation(data: Mapping[str, Any]) -> str | None:
    market = data.get('market_data') or {}
    value = market.get('generation') or market.get('generated_at')
    return str(value) if value is not None else None


def current_global_player_ranks(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Admit prepared ranks only at their matching Market/method boundary."""
    reference = data.get('global_player_ranks') or {}
    generation = market_rank_generation(data)
    if (generation is None or reference.get('methodology') != RANK_METHODOLOGY
            or reference.get('market_source_generation') != generation):
        return {}
    return reference.get('players') or {}


@dataclass(frozen=True)
class ScopedRank:
    rank: int | None
    scope: str
    value_basis: str
    position: str | None
    universe_size: int
    ranked_count: int
    generation: str
    tie_breaker: str = "canonical_player_id"


def rank_players(values: Mapping[str, float | None], positions: Mapping[str, str], *,
                 scope: str, value_basis: str, methodology: str) -> dict[str, dict[str, ScopedRank]]:
    """Missing values remain in the universe but receive no fabricated rank.

    This function performs no reads and cannot discover a universe from a roster.
    Callers explicitly supply the authoritative universe for the declared scope.
    Equal values receive stable ordinal ranks using canonical identity.
    """
    if scope not in {"global", "league_universe", "league_adjusted", "roster", "weekly"}:
        raise ValueError("Explicit supported rank scope required.")
    if not value_basis or not methodology or set(values) != set(positions):
        raise ValueError("Rank identity, methodology and comparison universe must agree.")
    for value in values.values():
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError("Rank values must be finite canonical numbers or unavailable.")
    generation = hashlib.sha256(json.dumps(
        [scope, value_basis, methodology, [(key, positions[key], values[key]) for key in sorted(values)]],
        separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    ordered = sorted((key for key, value in values.items() if value is not None), key=lambda key: (-values[key], key))
    overall = {key: index for index, key in enumerate(ordered, 1)}
    counts: dict[str, int] = {}
    positional: dict[str, int] = {}
    population: dict[str, int] = {}
    for position in positions.values():
        population[position] = population.get(position, 0) + 1
    for key in ordered:
        position = positions[key]
        counts[position] = counts.get(position, 0) + 1
        positional[key] = counts[position]
    return {key: {
        "overall": ScopedRank(overall.get(key), scope, value_basis, None, len(values), len(ordered), generation),
        "position": ScopedRank(positional.get(key), scope, value_basis, positions[key], population[positions[key]], counts.get(positions[key], 0), generation),
    } for key in sorted(values)}


def prepare_global_player_ranks(data: dict[str, Any]) -> dict[str, Any]:
    """Background-only global comparison before league relevance filtering.

    Stream existing canonical evaluations and retain only rank inputs/results.
    Never derive global rank from the owner's roster or a filtered catalog.
    The caller may discard non-member results AFTER ranking the complete catalog.
    """
    from src.core.valuation.universe import ValuationUniverse

    if isinstance((data.get("relevant_player_universe") or {}).get("member_ids"), list):
        raise ValueError("Global ranks require the pre-filter canonical catalog.")
    reference = {**data, "teams": [], "calibration_state": {}}
    positions: dict[str, str] = {}
    values: dict[str, dict[str, float | None]] = {"global_intrinsic": {}, "global_market": {}}
    for asset in ValuationUniverse.streaming(reference, {}).iter_assets():
        if asset["asset_type"] != "player":
            continue
        key = asset["asset_id"]
        positions[key] = str(asset["identity"].get("position") or "Unknown")
        values["global_intrinsic"][key] = asset["layers"]["intrinsic_dtos_value"]["value"]
        values["global_market"][key] = asset["layers"]["market_value"]["value"]
    rows: dict[str, dict[str, Any]] = {key: {} for key in positions}
    generations = []
    for label, inputs in values.items():
        ranks = rank_players(inputs, positions, scope="global", value_basis={"global_intrinsic": "intrinsic_dtos_value", "global_market": "market_value"}[label],
            methodology=RANK_METHODOLOGY)
        for key, pair in ranks.items():
            rows[key][label] = {axis: asdict(rank) for axis, rank in pair.items()}
        generations.append(next(iter(ranks.values()))["overall"].generation if ranks else "empty")
    return {"generation": hashlib.sha256(json.dumps(generations).encode()).hexdigest(),
            "universe_size": len(positions), "methodology": RANK_METHODOLOGY,
            "market_source_generation": market_rank_generation(data), "players": rows}
