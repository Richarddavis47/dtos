"""Dataset-versioned process-local Historical Asset Graph cache."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.historical_memory.models import (
    HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
    HISTORICAL_SCHEMA_VERSION,
    IMPORTER_VERSION,
    PLAYER_HISTORY_SCHEMA_VERSION,
)
from src.core.historical_memory.store import HistoricalStore

READ_MODEL_VERSION = "1.1"
MAX_CACHE_ENTRIES = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_identity(data: dict[str, Any]) -> str:
    players = data.get("players") or {}
    stable = [
        (
            str(player_id), player.get("full_name"), player.get("first_name"),
            player.get("last_name"), player.get("position"), player.get("team"),
            player.get("status"), player.get("age"),
        )
        for player_id, player in sorted(players.items())
    ]
    source = json.dumps(stable, separators=(",", ":"), default=str)
    return hashlib.sha256(source.encode()).hexdigest()


class HistoricalReadModelCache:
    """Build at most one immutable graph per dataset key under a process lock."""

    def __init__(self, max_entries: int = MAX_CACHE_ENTRIES) -> None:
        self.max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: OrderedDict[str, HistoricalAssetGraph] = OrderedDict()
        self._build_count = 0
        self._hits = 0
        self._misses = 0
        self._last_build_duration_ms: float | None = None
        self._last_load_duration_ms: float | None = None
        self._last_successful_build: str | None = None
        self._last_build_error: str | None = None
        self._active_key: str | None = None

    def cache_key(
        self, store: HistoricalStore, league_id: str, data: dict[str, Any],
    ) -> tuple[str, str]:
        dataset_version = store.dataset_version(league_id)
        source = "|".join((
            str(store.path.resolve()), league_id, dataset_version, HISTORICAL_SCHEMA_VERSION,
            IMPORTER_VERSION, HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            PLAYER_HISTORY_SCHEMA_VERSION, READ_MODEL_VERSION,
            _current_identity(data),
        ))
        return hashlib.sha256(source.encode()).hexdigest(), dataset_version

    def get(
        self, store: HistoricalStore, league_id: str, data: dict[str, Any],
    ) -> HistoricalAssetGraph:
        started = time.perf_counter()
        key, dataset_version = self.cache_key(store, league_id, data)
        with self._lock:
            graph = self._entries.get(key)
            if graph is not None:
                self._hits += 1
                self._entries.move_to_end(key)
                self._active_key = key
                self._last_load_duration_ms = round(
                    (time.perf_counter() - started) * 1000, 3,
                )
                graph.set_cache_metadata(self.metadata(dataset_version))
                return graph
            self._misses += 1
            build_started = time.perf_counter()
            try:
                # Keep construction lightweight. Individual read paths build only
                # the indexes they need, under the graph's single-flight lock.
                graph = HistoricalAssetGraph(store, league_id, data)
            except Exception as exc:
                self._last_build_error = f"{type(exc).__name__}: {exc}"
                previous = next(reversed(self._entries.values()), None)
                if previous is not None and previous.league_id == league_id:
                    previous.set_cache_metadata({
                        **self.metadata(dataset_version),
                        "status": "stale_after_rebuild_failure",
                    })
                    return previous
                raise
            self._build_count += 1
            self._last_build_duration_ms = round(
                (time.perf_counter() - build_started) * 1000, 3,
            )
            self._last_load_duration_ms = round(
                (time.perf_counter() - started) * 1000, 3,
            )
            self._last_successful_build = _now()
            self._last_build_error = None
            self._active_key = key
            self._entries[key] = graph
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            self._persist_manifest(store, key, dataset_version)
            graph.set_cache_metadata(self.metadata(dataset_version))
            return graph

    def _persist_manifest(
        self, store: HistoricalStore, key: str, dataset_version: str,
    ) -> None:
        """Atomically persist the rebuild identity, never the hydrated graph."""
        target = store.path.parent / "historical_read_model_manifest.json"
        temporary = Path(f"{target}.{threading.get_ident()}.tmp")
        payload = {
            "schema_version": READ_MODEL_VERSION,
            "cache_key": key,
            "dataset_version": dataset_version,
            "generated_at": self._last_successful_build,
        }
        try:
            temporary.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def metadata(self, dataset_version: str | None = None) -> dict[str, Any]:
        graph = self._entries.get(self._active_key or "")
        return {
            "status": "ready" if graph else "empty",
            "read_model_version": READ_MODEL_VERSION,
            "dataset_version": dataset_version,
            "cache_key": self._active_key,
            "build_count": self._build_count,
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "build_duration_ms": self._last_build_duration_ms,
            "load_duration_ms": self._last_load_duration_ms,
            "last_successful_build": self._last_successful_build,
            "last_build_error": self._last_build_error,
            "entry_count": len(self._entries),
            "max_entries": self.max_entries,
            "asset_count": graph.index_asset_count if graph else 0,
            "event_count": graph.index_event_count if graph else 0,
            "approximate_model_bytes": graph.approximate_size_bytes if graph else 0,
        }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._active_key = None


historical_read_model_cache = HistoricalReadModelCache()


def historical_graph(
    store: HistoricalStore, league_id: str, data: dict[str, Any],
) -> HistoricalAssetGraph:
    return historical_read_model_cache.get(store, league_id, data)
