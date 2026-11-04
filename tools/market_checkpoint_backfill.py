"""Evaluate a bounded set of relevant historical trades for sparse checkpoints."""
from __future__ import annotations

import argparse
import json

from config import LEAGUE_ID
from src.core.history_context import canonical_history_store
from src.core.intelligence_memory import historical_trade_resolution_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", default=LEAGUE_ID)
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 501))
    args = parser.parse_args()
    summary = historical_trade_resolution_service.run(
        canonical_history_store, str(args.league), maximum_events=args.limit,
    )
    print(json.dumps({
        "status": historical_trade_resolution_service.health().get("status"),
        "events_evaluated": summary.completed_trades,
        "players_or_picks_considered": summary.assets_total,
        "assets_valued": summary.assets_valued,
        "unavailable": summary.assets_total - summary.assets_valued,
        "counters": summary.counters,
        "bounded": True,
        "limit": args.limit,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
