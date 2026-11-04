"""Explicit, sequential canonical NFL backfill; dry-run admission by default.

Production use requires the established quiet maintenance boundary. This is not
an HTTP handler and cannot authenticate, restart or reconfigure the service.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from config import GLOBAL_EVIDENCE_FILE
from services.global_evidence_ingestion import run_ingestion


def admission(database: Path, seasons: list[int]) -> dict:
    """Conservative per-season budget based on the measured 19.43 MiB source proof."""
    selected = sorted(set(seasons))
    if not selected or len(selected) > 10 or any(year < 1999 for year in selected):
        raise ValueError('Choose one to ten explicit supported source seasons per bounded invocation.')
    parent = database.resolve().parent
    if not parent.is_dir():
        raise ValueError('The explicit storage parent must already exist.')
    retained = database.stat().st_size if database.exists() else 0
    estimated_growth = len(selected) * 24 * 1048576
    free = shutil.disk_usage(parent).free
    # Worker source staging and SQLite rollback allowance, not the distinct
    # runtime cgroup reserve, which run_ingestion independently enforces.
    temporary_allowance = 128 * 1048576
    disk_reserve = 128 * 1048576
    admitted = (retained + estimated_growth <= 256 * 1048576 and
                free >= estimated_growth + temporary_allowance + disk_reserve)
    return {'admitted': admitted, 'seasons': selected, 'retained_bytes': retained,
            'estimated_growth_bytes': estimated_growth, 'free_bytes': free,
            'temporary_allowance_bytes': temporary_allowance, 'disk_reserve_bytes': disk_reserve,
            'estimate_is_not_guaranteed': True, 'writes': 0}


def execute(database: Path, seasons: list[int], *, apply: bool = False) -> dict:
    plan = admission(database, seasons)
    if not apply or not plan['admitted']:
        return {'status': 'dry_run' if plan['admitted'] else 'not_admitted', 'admission': plan}
    results = []
    for season in plan['seasons']:
        result = run_ingestion(season, database)
        results.append(result)
        if result.get('status') != 'complete':
            return {'status': 'incomplete', 'admission': plan, 'results': results}
    return {'status': 'complete', 'admission': plan, 'results': results,
            'final_bytes': database.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, action='append', required=True)
    parser.add_argument('--database', type=Path, default=GLOBAL_EVIDENCE_FILE)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    report = execute(args.database, args.season, apply=args.apply)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] in {'dry_run', 'complete'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
