"""Run a resumable historical Sleeper backfill from the repository root."""
from __future__ import annotations

import argparse
import asyncio
import json

from config import HISTORY_DATABASE_FILE, LEAGUE_ID
from services.history import backfill_history, data_quality, direct_fetch


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--league", default=LEAGUE_ID)
    value.add_argument("--season", type=int, action="append", dest="seasons")
    return value


async def run() -> int:
    arguments = parser().parse_args()
    result = await backfill_history(
        direct_fetch, league_id=arguments.league,
        seasons=set(arguments.seasons) if arguments.seasons else None,
    )
    quality = data_quality(arguments.league)
    report = {
        "database": str(HISTORY_DATABASE_FILE),
        "import": result,
        "data_quality": quality,
    }
    print(json.dumps(report, indent=2))
    return 0 if result["status"] == "complete" and quality["blocking_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
