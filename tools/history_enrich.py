"""Trusted CLI for approved historical player-data enrichment."""
from __future__ import annotations

import argparse
import asyncio
import json

from config import LEAGUE_ID
from services.history import enrich_player_history


def exit_code(result: dict[str, object]) -> int:
    return int(result["status"] not in {"complete", "completed_with_pending"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default=LEAGUE_ID)
    parser.add_argument("--season", action="append", type=int)
    args = parser.parse_args()
    result = asyncio.run(
        enrich_player_history(
            args.league,
            seasons=set(args.season) if args.season else None,
        ),
    )
    print(json.dumps(result, indent=2))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
