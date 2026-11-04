"""One-shot public-source worker. No FastAPI/application state is imported."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psutil

from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.identity_crosswalk import load_crosswalk
from src.core.data_platform.production_ingestion import ingest_production
from src.core.data_platform.schedule_ingestion import ingest_schedule
from src.core.data_platform.source_snapshot import download_snapshot


PROTOCOL = 1


def run_job(request: dict, client: httpx.Client) -> dict:
    if set(request) != {"protocol", "season", "database", "temporary_directory"} or request["protocol"] != PROTOCOL:
        raise ValueError("Unsupported global ingestion request.")
    season = request["season"]
    if isinstance(season, bool) or not isinstance(season, int) or season < 1999:
        raise ValueError("Invalid season.")
    path = Path(request["database"])
    if not path.is_absolute():
        raise ValueError("Global evidence database must be an explicit absolute path.")
    started = time.monotonic()
    stamp = datetime.now(timezone.utc).isoformat()
    store = GlobalEvidenceStore(path)
    workspace = Path(request["temporary_directory"])
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError("Worker temporary directory must already exist.")
    with tempfile.TemporaryDirectory(prefix="global-ingestion-", dir=workspace) as temporary:
        work = Path(temporary)
        with download_snapshot(client, "https://api.sleeper.app/v1/players/nfl", directory=work,
                               maximum_bytes=64 * 1048576) as snapshot:
            players = json.loads(snapshot.path.read_text(encoding="utf-8"))
        if not isinstance(players, dict) or len(players) > 100000:
            raise ValueError("Invalid public player catalog.")
        identities, crosswalk = load_crosswalk(client, players, temporary_directory=work)
        del players
        schedule, games = ingest_schedule(client, store, season=season,
                                         retrieved_at=stamp, temporary_directory=work)
        store.record_source_check(f'nflverse/schedule/{season}', source_identity=schedule.get('source_sha256'),
            checked_at=stamp, status='complete', details={'records': schedule['games'],
                'source_bytes': schedule.get('source_bytes')})
        try:
            production = ingest_production(client, store, season=season, identities=identities,
                                           game_dates=games, retrieved_at=stamp, temporary_directory=work)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            production = {"status": "unavailable", "reason": "provider_season_file_missing", "complete": False}
        coverage = production.get('coverage') or {}
        prior = store.source_check(f'nflverse/production/{season}')
        details = ((prior or {}).get('details') or {}) if production.get('unchanged_revision') else {
            'source_rows': production.get('source_rows_examined'),
            'unresolved_rows': coverage.get('identity_unresolved'),
            'missing_game_times': coverage.get('game_time_unavailable'),
            'source_bytes': production.get('source_bytes'), 'reason': production.get('reason')}
        store.record_source_check(f'nflverse/production/{season}',
            source_identity=production.get('source_identity'), checked_at=stamp,
            status='complete' if production.get('complete') else 'unavailable', details=details)
    return {"protocol": PROTOCOL, "status": "complete" if production.get("complete") else "partial", "season": season,
            "crosswalk": crosswalk, "schedule": schedule, "production": production,
            "database_bytes": path.stat().st_size,
            "duration_seconds": round(time.monotonic() - started, 3),
            "final_worker_rss": psutil.Process().memory_info().rss,
            "temporary_cleanup": True}


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(8193)
        if len(raw) > 8192:
            raise ValueError("Oversize worker request.")
        request = json.loads(raw)
        with httpx.Client(timeout=45, follow_redirects=True) as client:
            result = run_job(request, client)
    except Exception as exc:
        # Never print a provider body, URL parameters, environment, or traceback.
        result = {"protocol": PROTOCOL, "status": "failed", "reason": type(exc).__name__}
    sys.stdout.write(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"complete", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
