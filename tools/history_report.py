"""Reject the retired legacy HistoricalStore reporting path."""
from __future__ import annotations

import json


def main() -> int:
    print(json.dumps({
        "status": "retired",
        "error": "Legacy HistoricalStore reporting is physically retired.",
        "replacement": "/api/history/coverage",
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
