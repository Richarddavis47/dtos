"""Deterministic canonical player identity resolution."""
from __future__ import annotations

import re
from typing import Any

from src.core.data_platform.normalization.models import NormalizedPlayer


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold().replace("jr", "").replace("sr", ""))


class PlayerIdentityResolver:
    PROVIDER_FIELDS = {"Sleeper": "player_id", "FantasyCalc": "fantasycalc_id", "KeepTradeCut": "ktc_id", "FantasyPros": "fantasypros_id", "Underdog": "underdog_id", "Dynasty Daddy": "dynasty_daddy_id"}

    def __init__(self, players: dict[str, dict[str, Any]] | None = None) -> None:
        self._players: dict[str, NormalizedPlayer] = {}
        self._aliases: dict[tuple[str, str], str] = {}
        for key, row in (players or {}).items():
            self.register(str(key), row)

    def register(self, key: str, row: dict[str, Any]) -> NormalizedPlayer:
        metadata_payload = row.get("metadata") or {}
        metadata = {str(name): str(value) for name, value in metadata_payload.items() if value is not None} if isinstance(metadata_payload, dict) else {}
        dtos_id = str(row.get("player_id") or key).strip()
        name = str(row.get("full_name") or " ".join(filter(None, (row.get("first_name"), row.get("last_name")))) or dtos_id).strip()
        provider_ids = {provider: str(row[field]) for provider, field in self.PROVIDER_FIELDS.items() if row.get(field) is not None}
        provider_ids.setdefault("Sleeper", dtos_id)
        aliases = tuple(sorted({name, str(row.get("search_full_name") or ""), metadata.get("previous_name", "")} - {""}))
        player = NormalizedPlayer(dtos_id, name, normalize_position(row.get("position")), normalize_team(row.get("team")), _float(row.get("age")), _integer(row.get("years_exp")), str(row.get("status") or "Unknown"), provider_ids, aliases, metadata)
        self._players[dtos_id] = player
        self._aliases[("name", normalize_name(name))] = dtos_id
        for provider, provider_id in provider_ids.items():
            self._aliases[(provider.casefold(), provider_id.casefold())] = dtos_id
        return player

    def resolve(self, identifier: str, provider: str | None = None, name: str | None = None) -> NormalizedPlayer | None:
        if identifier in self._players:
            return self._players[identifier]
        dtos_id = self._aliases.get(((provider or "name").casefold(), identifier.casefold()))
        if not dtos_id and name:
            dtos_id = self._aliases.get(("name", normalize_name(name)))
        return self._players.get(dtos_id or "")


def normalize_team(value: Any) -> str:
    team = str(value or "FA").upper().strip()
    return {"JAC": "JAX", "LA": "LAR", "WSH": "WAS", "OAK": "LV"}.get(team, team)


def normalize_position(value: Any) -> str:
    position = str(value or "UNKNOWN").upper().strip()
    if position in {"DEF", "D/ST"}:
        return "DST"
    return position.split("/")[0].strip()


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
