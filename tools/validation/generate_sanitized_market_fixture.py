"""Generate deterministic production-scale, non-production validation state."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.historical_memory.store import HistoricalStore

ASSET_COUNT = 12_322
HISTORICAL_COUNT = 30_726
LEAGUE_ID = "validation-league-1804"
STAMP = "2026-08-07T00:00:00+00:00"


def material_market_fixture_change(
    current: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Change one attached value consumed by the canonical valuation universe."""
    normalized = current.get("normalized_players")
    if not isinstance(normalized, dict):
        raise ValueError("Canonical normalized-player map is unavailable.")
    target = normalized.get("10213")
    if not isinstance(target, dict):
        raise ValueError("Canonical fixture asset player:10213 is unavailable.")
    if "dtos_value" not in target or not isinstance(target["dtos_value"], (int, float)):
        raise ValueError("Canonical fixture dtos_value is unavailable.")
    data = json.loads(json.dumps(current))
    attached = data["normalized_players"]["10213"]
    before = attached["dtos_value"]
    after = before + 1 if before < 100 else before - 1
    attached["dtos_value"] = after
    if data["normalized_players"]["10213"]["dtos_value"] != after:
        raise ValueError("Canonical fixture mutation was not attached.")
    return data, {
        "asset_id": "player:10213",
        "field": "normalized_players.10213.dtos_value",
        "before": before, "after": after, "attached": True,
        "changed_canonical_fields": 1,
    }


def _player(index: int) -> dict:
    positions = ("QB", "RB", "WR", "TE")
    player_id = "10213" if index == 1 else f"v{index:05d}"
    return player_id, {
        "player_id": player_id,
        "full_name": "Validation Player 10213" if index == 1 else f"Validation Player {index}",
        "name": "Validation Player 10213" if index == 1 else f"Validation Player {index}",
        "position": positions[index % len(positions)],
        "team": f"V{index % 32:02d}",
        "age": 21 + index % 17,
        "status": "Active",
        "years_exp": index % 14,
        "dtos_value": 1 + index % 100,
    }


def _cache(path: Path) -> None:
    players = dict(_player(index) for index in range(1, ASSET_COUNT + 1))
    roster_ids = list(players)[:250]
    teams = []
    for roster_id in range(1, 11):
        owned = roster_ids[(roster_id - 1) * 25:roster_id * 25]
        teams.append({
            "roster_id": roster_id,
            "owner_id": f"owner-{roster_id}",
            "owner": f"Validation Owner {roster_id}",
            "team_name": f"Validation Team {roster_id}",
            "wins": roster_id % 8,
            "losses": 14 - roster_id % 8,
            "ties": 0,
            "players": [
                {**players[player_id], "id": player_id, "roster_slot": "Starter"}
                for player_id in owned
            ],
            "picks_owned": [],
            "picks_traded_away": [],
        })
    picks = []
    for season in range(2027, 2030):
        for round_number in range(1, 5):
            for original_roster_id in range(1, 11):
                owner = (original_roster_id + round_number + season) % 10 + 1
                picks.append({
                    "season": season,
                    "round": round_number,
                    "original_roster_id": original_roster_id,
                    "original_team": f"Validation Team {original_roster_id}",
                    "current_owner_id": owner,
                    "current_owner": f"Validation Team {owner}",
                    "is_traded": owner != original_roster_id,
                })
    data = {
        "league": {
            "league_id": LEAGUE_ID,
            "name": "Sanitized Production-Scale Validation League",
            "season": "2026",
            "status": "in_season",
            "total_rosters": 10,
            "settings": {"num_teams": 10, "type": 2, "draft_rounds": 4},
            "scoring_settings": {"rec": 1.0, "pass_td": 4.0},
            "roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "BN"],
        },
        "scoring_settings": {"rec": 1.0, "pass_td": 4.0},
        "league_settings": {"num_teams": 10, "type": 2, "draft_rounds": 4},
        "roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "BN"],
        "owners": {f"owner-{index}": {"display_name": f"Validation Owner {index}"} for index in range(1, 11)},
        "teams": teams,
        "traded_picks": [],
        "pick_ledger": picks,
        "drafts": [],
        "transactions": [],
        "matchups": [],
        "nfl_state": {"season": "2026", "week": 1, "season_type": "regular"},
        "week": 1,
        "players": players,
        "normalized_players": players,
        "trending_players": [],
        "players_fetched_at": STAMP,
        "market_data": {"providers": {}, "provider_status": {}},
    }
    payload = {
        "data": data,
        "last_sync": STAMP,
        "last_error": None,
        "transactions_last_sync": STAMP,
        "transactions_last_error": None,
    }
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def _history(path: Path) -> None:
    HistoricalStore(path)
    connection = sqlite3.connect(path)
    identities = [
        ("sleeper", player_id, player_id, 100, None, 0)
        for player_id in dict(_player(index) for index in range(1, ASSET_COUNT + 1))
    ]
    connection.executemany(
        "INSERT INTO current_player_identity "
        "(provider,provider_player_id,dtos_player_id,confidence,gsis_id,"
        "identity_generation) VALUES (?,?,?,?,?,?)",
        identities,
    )
    rows = []
    for index in range(HISTORICAL_COUNT):
        season = 2021 + index % 5
        player_index = index % ASSET_COUNT + 1
        player_id = (
            "10213" if index % 500 == 0 or player_index == 1
            else f"v{player_index:05d}"
        )
        rows.append((
            f"validation:{index}", "player_week", LEAGUE_ID, season,
            index % 18 + 1, f"franchise:{index % 10 + 1}", player_id,
            f"validation-{index}", STAMP, STAMP, "nflverse", "available",
            100, "deterministic_fixture", 0, "1.0",
            json.dumps({"fantasy_points": float(index % 50), "fixture": True}, separators=(",", ":")),
        ))
        if len(rows) == 1000:
            connection.executemany(
                "INSERT INTO historical_records "
                "(record_key,entity_type,league_id,season,week,franchise_id,player_id,"
                "source_record_id,observed_at,retrieved_at,provider,availability,confidence,"
                "calculation_method,derived,schema_version,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            rows.clear()
    if rows:
        connection.executemany(
            "INSERT INTO historical_records "
            "(record_key,entity_type,league_id,season,week,franchise_id,player_id,"
            "source_record_id,observed_at,retrieved_at,provider,availability,confidence,"
            "calculation_method,derived,schema_version,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    job_id = "sanitized-enrichment-5-of-6"
    connection.execute(
        "INSERT INTO import_jobs "
        "(job_id,league_id,requested_seasons,requested_data_types,status,created_at,started_at,"
        "last_progress_at,completed_at,current_season,current_data_type,total_steps,completed_steps,"
        "inserted_records,requested_by,schema_version,importer_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            job_id, LEAGUE_ID, "[2021,2022,2023,2024,2025,2026]", '["player_week"]',
            "completed_with_pending", STAMP, STAMP, STAMP, STAMP, 2026, "player_week",
            6, 5, HISTORICAL_COUNT, "sanitized_fixture", "1.0", "1.2",
        ),
    )
    for season in range(2021, 2026):
        connection.execute(
            "INSERT INTO import_checkpoints "
            "(checkpoint_key,job_id,league_id,season,data_type,provider,importer_version,status,"
            "completed_at,records_written,records_unchanged) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"{LEAGUE_ID}:{season}:player_week:nflverse:1.2", job_id,
                LEAGUE_ID, season, "player_week", "nflverse", "1.2", "completed",
                STAMP, HISTORICAL_COUNT // 5, 0,
            ),
        )
    connection.execute(
        "INSERT INTO import_checkpoints "
        "(checkpoint_key,job_id,league_id,season,data_type,provider,importer_version,status,"
        "completed_at,records_written,records_unchanged) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            f"{LEAGUE_ID}:2026:player_week:nflverse:1.2", job_id,
            LEAGUE_ID, 2026, "player_week", "nflverse", "1.2", "pending",
            None, 0, 0,
        ),
    )
    connection.commit()
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    store = HistoricalStore(path)
    progress = store.canonical_enrichment_progress(
        LEAGUE_ID, tuple(range(2021, 2027)),
        provider="nflverse", importer_version="1.2",
    )
    with store.connection() as verification:
        record_count = int(verification.execute(
            "SELECT count(*) FROM historical_records WHERE league_id=?",
            (LEAGUE_ID,),
        ).fetchone()[0])
    if record_count != HISTORICAL_COUNT:
        raise RuntimeError("sanitized historical record count is inconsistent")
    if progress["completed_seasons"] != list(range(2021, 2026)) or progress[
        "pending_seasons"
    ] != [2026]:
        raise RuntimeError("sanitized historical progress is inconsistent")


def main() -> int:
    root = Path(os.environ.get("DTOS_FIXTURE_ROOT", "/fixture")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cache = root / "dtos_cache.json"
    history = root / "dtos_history.sqlite3"
    _cache(cache)
    _history(history)
    summary = {
        "fixture": "sanitized-generated-v1",
        "assets": ASSET_COUNT,
        "historical_records": HISTORICAL_COUNT,
        "historical_progress": "5/6",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
