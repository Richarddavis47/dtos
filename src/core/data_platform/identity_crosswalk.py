"""Exact-ID crosswalk enrichment; ambiguity fails closed in both directions."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx

from .normalization.identity import PlayerIdentityResolver
from .source_snapshot import download_snapshot


CROSSWALK_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"


def _id(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in {"", "na", "nan", "none", "null"} else text


def crosswalk_resolver(players: Mapping[str, dict], rows: Iterable[Mapping[str, Any]]) -> tuple[PlayerIdentityResolver, dict]:
    canonical = {str(row.get("player_id") or key): row for key, row in players.items()}
    by_player: dict[str, set[str]] = defaultdict(set)
    by_gsis: dict[str, set[str]] = defaultdict(set)
    missing = unknown = count = 0

    def add(sleeper: str, gsis: str):
        by_player[sleeper].add(gsis)
        by_gsis[gsis].add(sleeper)

    for sleeper, row in canonical.items():
        if gsis := _id(row.get("gsis_id")):
            add(sleeper, gsis)
    for count, row in enumerate(rows, 1):
        if count > 100000:
            raise ValueError("Identity crosswalk exceeds bounded record count.")
        sleeper, gsis = _id(row.get("sleeper_id")), _id(row.get("gsis_id"))
        if not sleeper or not gsis:
            missing += 1
        elif sleeper not in canonical:
            unknown += 1
        else:
            add(sleeper, gsis)
    ambiguous_players = {key for key, values in by_player.items() if len(values) != 1}
    ambiguous_gsis = {key for key, values in by_gsis.items() if len(values) != 1}
    resolver = PlayerIdentityResolver()
    matched = 0
    for sleeper, row in canonical.items():
        candidates = by_player.get(sleeper, set())
        gsis = next(iter(candidates)) if len(candidates) == 1 else None
        if sleeper in ambiguous_players or gsis in ambiguous_gsis:
            gsis = None
        matched += gsis is not None
        resolver.register(sleeper, {**row, "gsis_id": gsis})
    return resolver, {"source_rows": count, "missing_ids": missing, "unknown_sleeper_rows": unknown,
                      "resolved_players": matched, "ambiguous_players": len(ambiguous_players),
                      "ambiguous_gsis_ids": len(ambiguous_gsis)}


def load_crosswalk(client: httpx.Client, players: Mapping[str, dict], *, temporary_directory: Path):
    with download_snapshot(client, CROSSWALK_URL, directory=temporary_directory) as snapshot:
        with snapshot.path.open(encoding="utf-8-sig", newline="") as source:
            rows = csv.DictReader(source)
            if not {"sleeper_id", "gsis_id"}.issubset(rows.fieldnames or []):
                raise ValueError("Identity crosswalk source schema is incomplete.")
            resolver, report = crosswalk_resolver(players, rows)
        return resolver, {**report, "source_sha256": snapshot.sha256, "source_bytes": snapshot.bytes_downloaded}
