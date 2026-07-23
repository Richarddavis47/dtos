"""Report historical record coverage and indexed query performance."""
from __future__ import annotations

import json
import os
import sqlite3
from time import perf_counter

from config import HISTORY_DATABASE_FILE, LEAGUE_ID


def main() -> int:
    connection = sqlite3.connect(HISTORY_DATABASE_FILE)
    entity_counts = dict(
        connection.execute(
            "SELECT entity_type, count(*) FROM historical_records GROUP BY entity_type ORDER BY entity_type",
        ),
    )
    season_counts = list(
        connection.execute(
            "SELECT season, count(*) FROM historical_records GROUP BY season ORDER BY season",
        ),
    )
    started = perf_counter()
    player_rows = list(
        connection.execute(
            """SELECT payload FROM historical_records
            WHERE league_id=? AND entity_type='player_week' AND player_id=?
            ORDER BY season, week LIMIT 100""",
            (LEAGUE_ID, "9509"),
        ),
    )
    elapsed = (perf_counter() - started) * 1000
    print(json.dumps({
        "database": str(HISTORY_DATABASE_FILE),
        "database_bytes": os.path.getsize(HISTORY_DATABASE_FILE),
        "entity_counts": entity_counts,
        "season_counts": season_counts,
        "bijan_weekly_records": len(player_rows),
        "indexed_player_query_ms": round(elapsed, 3),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
