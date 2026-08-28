"""Import-safe one-shot FOIS compute worker."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter
from src.platform.validation.progress import progress_from_environment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    progress = progress_from_environment()
    record = progress.record if progress is not None else lambda *_args, **_kwargs: None
    record("fois_child_phase", phase="entry", status="started")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    record("fois_child_phase", phase="input_decode", status="completed", input_bytes=args.input.stat().st_size)
    os.environ.update({
        "DTOS_FOIS_DB_FILE": str(payload["fois_database"]),
        "DTOS_INTELLIGENCE_CHECKPOINT_FILE": str(payload["intelligence_checkpoint_file"]),
        "DTOS_METADATA_DB_FILE": str(payload["metadata_database_file"]),
        "DTOS_SLEEPER_SEASON_CACHE_ROOT": str(payload["sleeper_season_cache_root"]),
        "DTOS_FOIS_ENABLED": "1",
    })

    import psutil
    from src.core.fois.history import load_results_history
    from src.core.fois.repository import FOISRepository
    from src.core.fois.service import FOISService
    from src.core.history_context import canonical_history_store

    data = payload["data"]
    league_id = str(payload["league_id"])
    canonical_history_store.update_current(league_id, data)
    repository = FOISRepository(Path(payload["fois_database"]))
    service = FOISService(
        repository,
        history_loader=lambda selected: load_results_history(
            canonical_history_store, selected,
        ),
    )
    started = perf_counter()
    record("fois_child_phase", phase="compute", status="started")
    scores = service._generate_sync(data)
    record("fois_child_phase", phase="compute", status="completed", duration_ms=round((perf_counter() - started) * 1000, 3), records=len(scores))
    result = {
        "status": "complete",
        "records": len(scores),
        "duration_ms": round((perf_counter() - started) * 1000, 3),
        "peak_rss_bytes": psutil.Process(os.getpid()).memory_info().rss,
    }
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    temporary.replace(args.output)
    record("fois_child_phase", phase="output", status="completed", output_bytes=args.output.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
