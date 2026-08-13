"""Generate deterministic production-scale, non-production validation state."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.core.historical_memory.store import HistoricalStore
from src.core.valuation_intelligence.engine import (
    _semantic_generation,
    asset_market_input_revision,
)

ASSET_COUNT = 12_322
HISTORICAL_COUNT = 30_726
PRODUCTION_HISTORICAL_RECORDS = 461_166
PRODUCTION_IDENTITY_ROWS = 2_050_532
PRODUCTION_CURRENT_IDENTITIES = 12_218
PRODUCTION_ENTITY_COUNTS = {
    "draft": 7, "draft_pick": 410, "franchise_identity": 60,
    "league_season": 6, "league_season_snapshot": 424,
    "league_week": 90, "matchup": 420, "matchup_team": 900,
    "pick_snapshot": 387, "player_fantasy_week": 36_864,
    "player_raw_week": 36_864, "player_week": 25_308,
    "playoff_bracket": 12, "playoff_result": 6, "prediction": 3_150,
    "season_standing": 60, "team_intelligence_snapshot": 3_150,
    "trade": 231, "transaction": 1_641, "valuation_snapshot": 347_122,
    "weekly_roster": 900, "weekly_roster_snapshot": 3_154,
}
LEAGUE_ID = "1804000000000000000"
STAMP = "2026-08-07T00:00:00+00:00"


def fixture_valuation_intelligence() -> dict[str, Any]:
    """Return the attached canonical Brain snapshot consumed by Asset Market."""
    def layer(value: int | None, source: str) -> dict[str, Any]:
        return {
            "value": value, "source": source, "version": "1.0",
            "generated_at": STAMP, "confidence": 80,
            "availability": "available" if value is not None else "unavailable",
            "reason": None if value is not None else "No provider market evidence.",
            "limitations": [] if value is not None else ["No provider market evidence."],
        }

    asset_id = "player:10213"
    return {
        "application_version": "validation",
        "application_build": 0,
        "commit": "sanitized-validation",
        "schema_version": "1.0",
        "generated_at": STAMP,
        "availability": "available",
        "asset_count": 1,
        "assets": {asset_id: {
            "asset_id": asset_id,
            "asset_type": "player",
            "display_name": "Validation Player 10213",
            "scores": {"coverage": 75, "confidence": 80, "agreement": 70},
            "valuation_layers": {
                "market_value": layer(None, "Provider consensus"),
                "intrinsic_dtos_value": layer(20, "DTOS intrinsic"),
                "league_adjusted_value": layer(20, "DTOS league adjustment"),
                "contender_value": layer(450, "DTOS contender model"),
                "rebuilder_value": layer(600, "DTOS rebuilder model"),
            },
            "categories": [{"name": "Metadata", "available": True}],
            "evidence_sources": [],
            "provider_count": 0,
            "independent_family_count": 0,
            "missing_evidence": ["Market"],
            "diagnostics": ["Missing market support"],
            "explanation": "Sanitized canonical Brain fixture evidence.",
        }},
        "timeline": {},
        "summary": {
            "average_coverage": 75, "average_confidence": 80,
            "average_agreement": 70,
        },
        "diagnostics": {},
        "safety": {"external_requests_during_build": 0, "unsafe_adjustments": 0},
    }


def publish_fixture_market_revision(data: dict[str, Any]) -> dict[str, str]:
    """Publish fixture identity through the production semantic-revision contract."""
    intelligence = data.get("valuation_intelligence")
    assets = intelligence.get("assets") if isinstance(intelligence, dict) else None
    if not isinstance(assets, dict) or not assets:
        raise ValueError("Canonical fixture Brain assets are unavailable.")
    semantic_generation = _semantic_generation(list(assets.values()))
    intelligence["semantic_generation"] = semantic_generation
    revision = asset_market_input_revision(
        semantic_generation, intelligence.get("input_manifest") or {},
    )
    data["asset_market_semantic_revision"] = revision
    return {
        "brain_semantic_digest": semantic_generation,
        "asset_market_semantic_revision": revision,
    }


def material_market_fixture_change(
    current: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Change one attached Brain layer consumed by the compact market contract."""
    intelligence = current.get("valuation_intelligence")
    assets = intelligence.get("assets") if isinstance(intelligence, dict) else None
    target = assets.get("player:10213") if isinstance(assets, dict) else None
    layers = target.get("valuation_layers") if isinstance(target, dict) else None
    contender = layers.get("contender_value") if isinstance(layers, dict) else None
    if not isinstance(contender, dict) or not isinstance(
        contender.get("value"), (int, float),
    ):
        raise ValueError(
            "Canonical fixture Brain contender value for player:10213 is unavailable."
        )
    baseline = json.loads(json.dumps(current))
    before_identity = publish_fixture_market_revision(baseline)
    data = json.loads(json.dumps(baseline))
    attached = data["valuation_intelligence"]["assets"]["player:10213"][
        "valuation_layers"
    ]["contender_value"]
    before = attached["value"]
    after = before + 100 if before <= 900 else before - 100
    attached["value"] = after
    if attached["value"] != after:
        raise ValueError("Canonical fixture mutation was not attached.")
    after_identity = publish_fixture_market_revision(data)
    if (
        after_identity["brain_semantic_digest"]
        == before_identity["brain_semantic_digest"]
        or after_identity["asset_market_semantic_revision"]
        == before_identity["asset_market_semantic_revision"]
    ):
        raise ValueError("Canonical fixture publication did not advance semantics.")
    return data, {
        "asset_id": "player:10213",
        "field": (
            "valuation_intelligence.assets.player:10213.valuation_layers."
            "contender_value.value"
        ),
        "before": before, "after": after, "attached": True,
        "changed_canonical_fields": 1,
        "brain_semantic_digest_before": before_identity[
            "brain_semantic_digest"
        ],
        "brain_semantic_digest_after": after_identity[
            "brain_semantic_digest"
        ],
        "asset_market_semantic_revision_before": before_identity[
            "asset_market_semantic_revision"
        ],
        "asset_market_semantic_revision_after": after_identity[
            "asset_market_semantic_revision"
        ],
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
        "valuation_intelligence": fixture_valuation_intelligence(),
    }
    publish_fixture_market_revision(data)
    payload = {
        "data": data,
        "last_sync": STAMP,
        "last_error": None,
        "transactions_last_sync": STAMP,
        "transactions_last_error": None,
    }
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def _record_payload(entity_type: str, index: int) -> tuple[str | None, str]:
    """Return deterministic production-shaped identity and valid graph payload."""
    player_id = f"v{index % PRODUCTION_CURRENT_IDENTITIES + 1:05d}"
    if index % PRODUCTION_CURRENT_IDENTITIES == 0:
        player_id = "10213"
    if entity_type == "weekly_roster":
        players = [
            f"v{(index * 30 + offset) % PRODUCTION_CURRENT_IDENTITIES + 1:05d}"
            for offset in range(30)
        ]
        return None, json.dumps({"starters": players[:10], "bench": players[10:]}, separators=(",", ":"))
    if entity_type == "draft_pick":
        return player_id, json.dumps({
            "player_id": player_id, "round": index % 4 + 1,
            "roster_id": index % 10 + 1, "picked_by": index % 10 + 1,
            "draft_id": f"fixture-draft-{index // 40}",
        }, separators=(",", ":"))
    if entity_type == "pick_snapshot":
        return None, json.dumps({
            "season": 2027 + index % 3, "round": index % 4 + 1,
            "roster_id": index % 10 + 1, "owner_id": (index + 1) % 10 + 1,
        }, separators=(",", ":"))
    if entity_type in {"transaction", "trade"}:
        # Across 1,872 rows this yields exactly 2,519 graph event legs.
        global_index = index if entity_type == "transaction" else 1_641 + index
        adds = {player_id: index % 10 + 1}
        if global_index < 647:
            adds[
                f"v{(index + 7000) % PRODUCTION_CURRENT_IDENTITIES + 1:05d}"
            ] = (index + 1) % 10 + 1
        return None, json.dumps({
            "type": entity_type, "status": "complete", "adds": adds,
            "drops": {}, "draft_picks": [], "roster_ids": [1, 2],
        }, separators=(",", ":"))
    payload = {"fixture": True, "value": index % 10_000}
    if entity_type == "player_week":
        payload["fantasy_points"] = float(index % 50)
    if entity_type == "valuation_snapshot":
        # Valid evidence pages reproduce the production database/cache footprint.
        payload["evidence"] = "v" * 1_650
    return (player_id if entity_type in {"player_week", "player_raw_week", "player_fantasy_week"} else None), json.dumps(payload, separators=(",", ":"))


def _record_provider(entity_type: str) -> str:
    """Match completed player-week checkpoint provenance in sanitized evidence."""
    return "nflverse" if entity_type == "player_week" else "sanitized"


def _production_history(path: Path) -> None:
    """Create the complete sanitized production database shape used by CI."""
    HistoricalStore(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    identity_batch = []
    for index in range(PRODUCTION_IDENTITY_ROWS):
        player_index = index % PRODUCTION_CURRENT_IDENTITIES + 1
        observation = index // PRODUCTION_CURRENT_IDENTITIES
        player_id = "10213" if player_index == 1 else f"v{player_index:05d}"
        identity_batch.append((
            player_id, "sleeper", player_id, f"Validation Player {player_index}",
            100, f"2026-01-{1 + observation // 24:02d}T{observation % 24:02d}:00:00+00:00",
            None, "{}",
        ))
        if len(identity_batch) == 10_000:
            connection.executemany(
                "INSERT INTO player_identity (dtos_player_id,provider,provider_player_id,"
                "display_name,confidence,valid_from,valid_to,metadata) VALUES (?,?,?,?,?,?,?,?)",
                identity_batch,
            )
            identity_batch.clear()
    if identity_batch:
        connection.executemany(
            "INSERT INTO player_identity (dtos_player_id,provider,provider_player_id,"
            "display_name,confidence,valid_from,valid_to,metadata) VALUES (?,?,?,?,?,?,?,?)",
            identity_batch,
        )
    connection.executemany(
        "INSERT INTO current_player_identity "
        "(provider,provider_player_id,dtos_player_id,confidence,gsis_id,identity_generation) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("sleeper", "10213" if index == 1 else f"v{index:05d}",
             "10213" if index == 1 else f"v{index:05d}", 100, None, 6)
            for index in range(1, PRODUCTION_CURRENT_IDENTITIES + 1)
        ],
    )
    rows = []
    for entity_type, count in PRODUCTION_ENTITY_COUNTS.items():
        for index in range(count):
            season = 2026 if entity_type in {"league_season_snapshot", "prediction", "team_intelligence_snapshot", "valuation_snapshot", "weekly_roster_snapshot"} else 2021 + index % 5
            player_id, payload = _record_payload(entity_type, index)
            provider = _record_provider(entity_type)
            rows.append((
                f"production-fixture:{entity_type}:{index}", entity_type,
                LEAGUE_ID, season, index % 18 + 1,
                f"franchise:{index % 10 + 1}", player_id,
                f"production-{entity_type}-{index}", STAMP, STAMP,
                provider, "available", 100, "deterministic_fixture", 0,
                "1.0", payload,
            ))
            if len(rows) == 2_000:
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
    _insert_progress(connection, sum(PRODUCTION_ENTITY_COUNTS.values()))
    connection.commit()
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    store = HistoricalStore(path)
    statistics = store.compact_event_statistics(LEAGUE_ID)
    if statistics["asset_event_count"] != HISTORICAL_COUNT:
        raise RuntimeError("sanitized asset-event count is inconsistent")
    with store.connection() as verification:
        record_count = int(verification.execute("SELECT count(*) FROM historical_records").fetchone()[0])
        identity_count = int(verification.execute("SELECT count(*) FROM player_identity").fetchone()[0])
    if record_count != PRODUCTION_HISTORICAL_RECORDS or identity_count != PRODUCTION_IDENTITY_ROWS:
        raise RuntimeError("sanitized production database shape is inconsistent")


def _insert_progress(connection: sqlite3.Connection, inserted_records: int) -> None:
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
            6, 5, inserted_records, "sanitized_fixture", "1.0", "1.2",
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
                STAMP, max(1, inserted_records // 5), 0,
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


def _history(path: Path) -> None:
    HistoricalStore(path)
    connection = sqlite3.connect(path)
    identities = [
        ("sleeper", player_id, player_id, 100, None, 0)
        for player_id in dict(_player(index) for index in range(1, ASSET_COUNT + 1))
    ]
    connection.executemany(
        "INSERT INTO current_player_identity "
        "(provider,provider_player_id,dtos_player_id,confidence,gsis_id,identity_generation) "
        "VALUES (?,?,?,?,?,?)", identities,
    )
    rows = []
    for index in range(HISTORICAL_COUNT):
        season = 2021 + index % 5
        player_index = index % ASSET_COUNT + 1
        player_id = "10213" if index % 500 == 0 or player_index == 1 else f"v{player_index:05d}"
        rows.append((f"validation:{index}", "player_week", LEAGUE_ID, season,
            index % 18 + 1, f"franchise:{index % 10 + 1}", player_id,
            f"validation-{index}", STAMP, STAMP, "nflverse", "available",
            100, "deterministic_fixture", 0, "1.0",
            json.dumps({"fantasy_points": float(index % 50), "fixture": True}, separators=(",", ":"))))
    connection.executemany(
        "INSERT INTO historical_records "
        "(record_key,entity_type,league_id,season,week,franchise_id,player_id,source_record_id,"
        "observed_at,retrieved_at,provider,availability,confidence,calculation_method,derived,schema_version,payload) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows,
    )
    _insert_progress(connection, HISTORICAL_COUNT)
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
    production_shaped = os.environ.get("DTOS_PRODUCTION_SHAPED_FIXTURE") == "1"
    (_production_history if production_shaped else _history)(history)
    summary = {
        "fixture": "sanitized-generated-v1",
        "assets": ASSET_COUNT,
        "historical_records": (
            PRODUCTION_HISTORICAL_RECORDS if production_shaped
            else HISTORICAL_COUNT
        ),
        "database_shape": "production" if production_shaped else "compact",
        "historical_progress": "5/6",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
