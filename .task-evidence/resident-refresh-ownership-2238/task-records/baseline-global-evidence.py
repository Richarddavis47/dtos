async def refresh_global_evidence() -> None:
    """One global current-season flight; never one job per league or request."""
    from config import GLOBAL_EVIDENCE_FILE
    from services.global_evidence_ingestion import ingest_in_background

    delay = 30
    while True:
        await asyncio.sleep(delay)
        data = STATE.get("data") or {}
        season = (data.get("nfl_state") or {}).get("season")
        if not season or not lifecycle_coordinator.startup_complete():
            continue
        runtime_metrics.mark_background("global_evidence", "preparing")
        try:
            async with intelligence_heavy_lock:
                result = await ingest_in_background(int(season), GLOBAL_EVIDENCE_FILE)
            status = result.get("status", "failed")
        except asyncio.CancelledError:
            raise
        except Exception:
            # Provider gaps never erase retained evidence or hold startup ready.
            status = "failed"
        runtime_metrics.mark_background("global_evidence", status)
        delay = 30 if status == "deferred" else 6 * 60 * 60
