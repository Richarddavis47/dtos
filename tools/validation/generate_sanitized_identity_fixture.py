"""Generate a production-shaped identity-history fixture without private data."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from src.core.historical_memory.store import HistoricalStore
from tools.validation.generate_sanitized_market_fixture import (
    ASSET_COUNT,
    HISTORICAL_COUNT,
    LEAGUE_ID,
    STAMP,
    _cache,
    _history,
)

VERSIONS_PER_IDENTITY = 164


def main() -> int:
    root = Path(os.environ.get("DTOS_FIXTURE_ROOT", "/fixture")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cache_path = root / "dtos_cache.json"
    history_path = root / "dtos_history.sqlite3"
    _cache(cache_path)
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    players = cache["data"]["normalized_players"]
    for index, player in enumerate(players.values(), 1):
        player["provider_ids"] = {"GSIS": f"gsis-{index}"}
        player["aliases"] = []
    cache["data"]["players"] = players
    cache_path.write_text(
        json.dumps(cache, separators=(",", ":")), encoding="utf-8",
    )
    _history(history_path)
    connection = sqlite3.connect(history_path)
    rows: list[tuple[object, ...]] = []
    for version in range(VERSIONS_PER_IDENTITY):
        valid_from = f"2026-01-01T00:{version:03d}:00+00:00"
        for index, (player_id, player) in enumerate(players.items(), 1):
            metadata = json.dumps(
                {"aliases": [], "provider_ids": {"GSIS": f"gsis-{index}"}},
                separators=(",", ":"), sort_keys=True,
            )
            rows.append((
                player_id, "Sleeper", player_id, player["name"], 100,
                valid_from, metadata,
            ))
            if len(rows) == 10_000:
                connection.executemany(
                    """INSERT INTO player_identity(
                    dtos_player_id,provider,provider_player_id,display_name,
                    confidence,valid_from,metadata) VALUES (?,?,?,?,?,?,?)""",
                    rows,
                )
                rows.clear()
    if rows:
        connection.executemany(
            """INSERT INTO player_identity(
            dtos_player_id,provider,provider_player_id,display_name,confidence,
            valid_from,metadata) VALUES (?,?,?,?,?,?,?)""",
            rows,
        )
    job_id = "sanitized-enrichment-5-of-6"
    for season in range(2021, 2026):
        connection.execute(
            """INSERT INTO import_checkpoints(
            checkpoint_key,job_id,league_id,season,data_type,provider,
            importer_version,status,completed_at,identity_generation)
            VALUES (?,?,?,?,?,?,?,?,?,0)""",
            (
                f"{LEAGUE_ID}:{season}:player_week:nflverse:1.2", job_id,
                LEAGUE_ID, season, "player_week", "nflverse", "1.2",
                "completed", STAMP,
            ),
        )
    connection.execute(
        """INSERT INTO import_checkpoints(
        checkpoint_key,job_id,league_id,season,data_type,provider,
        importer_version,status,completed_at,error,identity_generation)
        VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
        (
            f"{LEAGUE_ID}:2026:player_week:nflverse:1.2", job_id, LEAGUE_ID,
            2026, "player_week", "nflverse", "1.2", "pending", STAMP,
            "Current-season evidence is not yet complete.",
        ),
    )
    connection.commit()
    connection.close()
    projected = HistoricalStore(history_path).rebuild_current_identity_projection()
    size = history_path.stat().st_size
    print(json.dumps({
        "fixture": "sanitized-identity-v1", "assets": ASSET_COUNT,
        "identity_versions": ASSET_COUNT * VERSIONS_PER_IDENTITY,
        "projected_identities": projected,
        "historical_records": HISTORICAL_COUNT, "progress": "5/6",
        "database_bytes": size,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
