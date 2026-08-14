"""One deterministic player-membership contract for every DTOS consumer."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Protocol

from src.core.valuation.calibration import cached_market_consensus


class RelevantPlayerStore(Protocol):
    def relevant_player_reasons(self, league_id: str) -> dict[str, set[str]]: ...
    def persist_relevant_player_universe(self, league_id: str, rows: list[dict[str, Any]], generation: str, updated_at: str) -> None: ...

RELEVANT_PLAYER_SCHEMA_VERSION = "1.0"
FREE_AGENT_LIMIT = 150


def apply_relevant_player_filter(
    data: dict[str, Any], contract: dict[str, Any],
) -> None:
    """Release excluded full player/provider objects after membership selection."""
    allowed = {str(player_id) for player_id in contract.get("member_ids") or []}
    for key in ("players", "normalized_players"):
        values = data.get(key)
        if isinstance(values, dict):
            data[key] = {
                player_id: row for player_id, row in values.items()
                if str(player_id) in allowed
            }
    providers = ((data.get("market_data") or {}).get("providers") or {})
    for provider, values in tuple(providers.items()):
        if isinstance(values, dict):
            providers[provider] = {
                asset_id: row for asset_id, row in values.items()
                if str(asset_id).removeprefix("player:") in allowed
                or str(asset_id).startswith("pick:")
            }


def _owned_reasons(data: dict[str, Any]) -> dict[str, set[str]]:
    reasons: dict[str, set[str]] = {}
    for team in data.get("teams") or []:
        for player in team.get("players") or []:
            player_id = str(player.get("id") or "")
            if not player_id:
                continue
            slot = str(player.get("roster_slot") or "").lower()
            code = "current_reserve" if any(
                item in slot for item in ("taxi", "reserve", "injured", "ir")
            ) else "current_roster"
            reasons.setdefault(player_id, set()).add(code)
    return reasons


def build_relevant_player_universe(
    data: dict[str, Any], store: RelevantPlayerStore, league_id: str,
    *, free_agent_limit: int = FREE_AGENT_LIMIT,
) -> dict[str, Any]:
    """Build and persist deterministic membership from cached and durable state."""
    players = data.get("normalized_players") or data.get("players") or {}
    reasons = store.relevant_player_reasons(league_id)
    for player_id, codes in _owned_reasons(data).items():
        reasons.setdefault(player_id, set()).update(codes)

    consensus = cached_market_consensus(
        data.get("market_data") or {}, (str(player_id) for player_id in players),
    )
    candidates: list[tuple[int, str]] = []
    for player_id in players:
        key = str(player_id)
        if key in reasons:
            continue
        value = (consensus.get(key) or (None, 0, None))[0]
        if value is not None:
            candidates.append((int(value), key))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[:max(0, int(free_agent_limit))]
    ranking_payload = [[player_id, value] for value, player_id in candidates]
    ranking_snapshot_id = hashlib.sha256(
        json.dumps(ranking_payload, separators=(",", ":")).encode()
    ).hexdigest()
    selected_metadata = {
        player_id: {"selection_rank": rank, "selection_value": value}
        for rank, (value, player_id) in enumerate(selected, 1)
    }
    for _, player_id in selected:
        reasons.setdefault(player_id, set()).add("top_free_agent")

    rows = []
    for player_id in sorted(reasons):
        metadata = selected_metadata.get(player_id, {})
        rows.append({
            "player_id": player_id,
            "reason_codes": sorted(reasons[player_id]),
            **metadata,
            "ranking_snapshot_id": (
                ranking_snapshot_id if "top_free_agent" in reasons[player_id] else None
            ),
        })
    generation_payload = [
        [row["player_id"], row["reason_codes"]] for row in rows
    ]
    generation = hashlib.sha256(
        json.dumps(generation_payload, separators=(",", ":")).encode()
    ).hexdigest()
    generated_at = datetime.now(timezone.utc).isoformat()
    store.persist_relevant_player_universe(
        league_id, rows, generation, generated_at,
    )
    positions: dict[str, int] = {}
    missing_market = 0
    for row in rows:
        player = players.get(row["player_id"]) or {}
        position = str(player.get("position") or "Unknown")
        positions[position] = positions.get(position, 0) + 1
        if (consensus.get(row["player_id"]) or (None,))[0] is None:
            missing_market += 1
    historical = sum(any(code.startswith("historical_") for code in row["reason_codes"]) for row in rows)
    owned = sum(any(code.startswith("current_") for code in row["reason_codes"]) for row in rows)
    return {
        "schema_version": RELEVANT_PLAYER_SCHEMA_VERSION,
        "generation": generation,
        "generated_at": generated_at,
        "league_id": league_id,
        "free_agent_limit": int(free_agent_limit),
        "ranking_snapshot_id": ranking_snapshot_id,
        "members": rows,
        "member_ids": [row["player_id"] for row in rows],
        "counts": {
            "provider_players": len(players), "historically_relevant": historical,
            "currently_owned": owned, "additional_free_agents": len(selected),
            "final_unique_players": len(rows),
            "excluded_players": max(0, len(players) - len(rows)),
            "missing_market_data": missing_market,
        },
        "coverage": {
            "positions": dict(sorted(positions.items())),
            "free_agent_boundary": ({
                "rank": len(selected), "value": selected[-1][0],
                "player_id": selected[-1][1],
            } if selected else None),
            "free_agent_shortfall": max(0, int(free_agent_limit) - len(selected)),
        },
    }
