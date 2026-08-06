from __future__ import annotations

import tempfile
import time
import tracemalloc
from datetime import timedelta
from pathlib import Path

from src.core.historical_memory.jobs import ImportJob, utcnow
from src.core.historical_memory.store import HistoricalStore

EVENTS = 5_000
BATCH_SIZE = 250
PERSISTENT_COMMIT_LATENCY_SECONDS = 0.020


def record(index: int, derived: bool) -> dict[str, object]:
    kind = "player_fantasy_week" if derived else "player_raw_week"
    return {
        "record_key": f"L:{kind}:2022:{index}:1.2",
        "entity_type": kind,
        "league_id": "L",
        "season": 2022,
        "week": index % 18 + 1,
        "player_id": f"player-{index}",
        "source_record_id": f"source-{index}",
        "observed_at": "2022-09-01T00:00:00+00:00",
        "retrieved_at": "2026-08-06T00:00:00+00:00",
        "provider": "DTOS" if derived else "nflverse",
        "availability": "observed",
        "confidence": 95,
        "calculation_method": (
            "league_scoring_engine:1.1" if derived else "provider_record"
        ),
        "derived": derived,
        "schema_version": "1.0",
        "payload": {"value": index},
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = HistoricalStore(Path(directory) / "history.sqlite3")
        job = ImportJob(
            store, "L", (2022,), ("player_week",), provider="nflverse",
        )
        job.create()
        assert job.acquire()
        tracemalloc.start()
        started = time.perf_counter()
        batches = 0
        for offset in range(0, EVENTS, BATCH_SIZE):
            batches += 1
            raw = [
                record(index, False)
                for index in range(offset, offset + BATCH_SIZE)
            ]
            derived = [
                record(index, True)
                for index in range(offset, offset + BATCH_SIZE)
            ]
            batch_started = utcnow()
            time.sleep(PERSISTENT_COMMIT_LATENCY_SECONDS)
            store.commit_enrichment_batch(
                raw_records=raw,
                derived_records=derived,
                progress={
                    "batch_key": f"L:2022:nflverse:{batches}:1.2",
                    "job_id": job.job_id,
                    "lease_owner": job.worker_identity,
                    "league_id": "L",
                    "season": 2022,
                    "week": batches,
                    "provider": "nflverse",
                    "batch_sequence": batches,
                    "raw_records_received": len(raw),
                    "batch_started_at": batch_started.isoformat(),
                    "batch_completed_at": utcnow().isoformat(),
                    "last_durable_event_identity": derived[-1]["record_key"],
                },
                lease_expires_at=(
                    utcnow() + timedelta(minutes=15)
                ).isoformat(),
            )
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        job.release()
        raw_count, _ = store.records("L", "player_raw_week", limit=1)
        derived_count, _ = store.records("L", "player_fantasy_week", limit=1)
        print(f"events={EVENTS}")
        print(f"batches={batches}")
        print(
            "simulated_commit_latency_ms="
            f"{PERSISTENT_COMMIT_LATENCY_SECONDS * 1000:.1f}"
        )
        print(f"elapsed_seconds={elapsed:.3f}")
        print(f"events_per_second={EVENTS / elapsed:.1f}")
        print(f"estimated_six_season_minutes={(elapsed * 6) / 60:.2f}")
        print(f"peak_python_mib={peak / 1024 / 1024:.2f}")
        print(f"raw_records={raw_count}")
        print(f"derived_records={derived_count}")


if __name__ == "__main__":
    main()
