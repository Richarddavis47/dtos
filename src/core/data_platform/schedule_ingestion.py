"""Source-backed global NFL game identity and kickoff evidence.

nflverse documents gametime as Eastern regardless of venue. Use the IANA zone
for daylight-saving conversion; never infer a kickoff for missing source times.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from .global_evidence import GlobalEvidenceStore, GlobalFact
from .ingestion import ingest
from .source_snapshot import download_snapshot


SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
METHOD_VERSION = "nflverse-schedule-v1"


def kickoff(row: dict[str, str]) -> str | None:
    date, time = row.get("gameday"), row.get("gametime")
    if not date or not time or date == "NA" or time == "NA":
        return None
    local = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    return local.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc).isoformat()


def ingest_schedule(client: httpx.Client, store: GlobalEvidenceStore, *, season: int,
                    retrieved_at: str, temporary_directory: Path) -> tuple[dict, dict[str, str]]:
    if isinstance(season, bool) or not isinstance(season, int) or season < 1999:
        raise ValueError("Unsupported schedule season.")
    with download_snapshot(client, SCHEDULE_URL, directory=temporary_directory) as snapshot:
        games: dict[str, GlobalFact] = {}
        unavailable = 0
        with snapshot.path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"game_id", "season", "week", "gameday", "gametime", "home_team", "away_team"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Schedule source schema is incomplete.")
            for row in reader:
                if row["season"] != str(season):
                    continue
                when = kickoff(row)
                if not when:
                    unavailable += 1
                    continue
                game_id = row["game_id"]
                if not game_id or not row["home_team"] or not row["away_team"]:
                    raise ValueError("Schedule game identity is incomplete.")
                fact = GlobalFact("schedule", f"nfl-game:{game_id}", "nflverse", game_id,
                    when, None, {"game_id": game_id, "game_date": row["gameday"], "kickoff": when,
                                 "home_team": row["home_team"], "away_team": row["away_team"],
                                 "game_type": row.get("game_type")}, season=season, week=int(row["week"]))
                if game_id in games and games[game_id] != fact:
                    raise ValueError("Conflicting schedule game identity.")
                games[game_id] = fact
                if len(games) > 1000:
                    raise ValueError("Schedule season exceeds bounded game count.")
        if not games:
            raise ValueError("No timed schedule games available for requested season.")
        result = ingest(store, key=f"nflverse/schedule/{season}",
                        source_identity=f"{METHOD_VERSION}:{snapshot.sha256}",
                        facts=lambda: (games[key] for key in sorted(games)), retrieved_at=retrieved_at)
        return ({**result, "source_sha256": snapshot.sha256, "source_bytes": snapshot.bytes_downloaded,
                 "games": len(games), "kickoff_unavailable": unavailable},
                {key: fact.effective_at for key, fact in games.items()})
