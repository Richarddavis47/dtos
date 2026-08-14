"""Atomic, disk-backed Asset Market directory and search read model."""
from __future__ import annotations

import gc
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.platform.lifecycle import memory_snapshot

MARKET_READ_MODEL_SCHEMA = "2.0"
TARGET_CGROUP_BYTES = 1536 * 1024 * 1024
HARD_CGROUP_BYTES = 1740 * 1024 * 1024
RESERVED_BYTES = 500 * 1024 * 1024
DEFAULT_STAGE_ESTIMATE = 128 * 1024 * 1024
HARD_PRESSURE_MARGIN_BYTES = 256 * 1024 * 1024
MAX_RECLAIMABLE_FRACTION = 0.75

SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE assets (
  asset_id TEXT PRIMARY KEY,
  asset_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  position TEXT,
  nfl_team TEXT,
  age REAL,
  status TEXT,
  availability TEXT NOT NULL,
  owner_id INTEGER,
  year INTEGER,
  round_number INTEGER,
  rookie INTEGER NOT NULL,
  market_value REAL,
  intrinsic_value REAL,
  league_value REAL,
  contender_value REAL,
  rebuilder_value REAL,
  confidence_value REAL,
  risk_value REAL,
  liquidity_value REAL,
  search_text TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  canonical_json TEXT NOT NULL
);
CREATE INDEX idx_market_type ON assets(asset_type);
CREATE INDEX idx_market_position ON assets(position);
CREATE INDEX idx_market_availability ON assets(availability);
CREATE INDEX idx_market_owner ON assets(owner_id);
CREATE INDEX idx_market_year_round ON assets(year, round_number);
CREATE INDEX idx_market_value ON assets(market_value, asset_id);
CREATE INDEX idx_intrinsic_value ON assets(intrinsic_value, asset_id);
CREATE INDEX idx_contender_value ON assets(contender_value, asset_id);
CREATE INDEX idx_rebuilder_value ON assets(rebuilder_value, asset_id);
"""


class MarketMemoryBudgetError(RuntimeError):
    """Raised before a market stage would violate the cgroup safety budget."""

    def __init__(self, stage: str, observation: dict[str, Any]) -> None:
        super().__init__(
            f"Asset Market stage {stage} deferred by the memory safety budget."
        )
        self.stage = stage
        self.observation = observation


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def _json_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    return decoded if isinstance(decoded, dict) else {}


def _fsync_file(path: Path) -> None:
    """Make a completed artifact durable before its atomic publication."""
    with path.open("r+b") as artifact:
        artifact.flush()
        os.fsync(artifact.fileno())


def _fsync_directory(path: Path) -> None:
    """Persist a POSIX directory rename; Windows has no directory fsync."""
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def memory_admission(
    snapshot: dict[str, Any], estimate: int = DEFAULT_STAGE_ESTIMATE, *,
    baseline_events: dict[str, int] | None = None,
    baseline_effective: int | None = None,
) -> dict[str, Any]:
    """Calculate bounded cgroup admission without discounting unknown memory."""
    current = snapshot.get("cgroup_current_bytes")
    limit = snapshot.get("cgroup_limit_bytes")
    inactive = snapshot.get("cgroup_inactive_file_bytes")
    events = snapshot.get("cgroup_memory_events")
    valid_current = isinstance(current, int) and current >= 0
    valid_cgroup = (
        valid_current and isinstance(limit, int) and limit > 0
    )
    valid_inactive = (
        valid_cgroup and isinstance(inactive, int)
        and 0 <= inactive <= current
    )
    valid_events = (
        isinstance(events, dict)
        and all(
            isinstance(events.get(name), int) and events[name] >= 0
            for name in ("oom", "oom_kill")
        )
    )
    working_set_metrics = valid_inactive and valid_events
    accounting_mode = (
        "cgroup_working_set" if working_set_metrics else "conservative"
    )
    effective = current - inactive if working_set_metrics else current
    finite_limit = limit if valid_cgroup else None
    safe_limit = (
        min(TARGET_CGROUP_BYTES, max(0, finite_limit - RESERVED_BYTES))
        if finite_limit is not None
        else TARGET_CGROUP_BYTES if valid_current else None
    )
    predicted = effective + estimate if isinstance(effective, int) else None
    reclaimable_allowance = (
        min(inactive, int(inactive * MAX_RECLAIMABLE_FRACTION))
        if working_set_metrics else 0
    )
    hard_pressure_ceiling = (
        finite_limit - HARD_PRESSURE_MARGIN_BYTES
        if finite_limit is not None else None
    )
    predicted_hard_pressure = (
        current + estimate - reclaimable_allowance
        if valid_current else None
    )
    event_deltas: dict[str, int] = {}
    if isinstance(events, dict) and baseline_events is not None:
        for name in ("oom", "oom_kill", "oom_group_kill"):
            current_event = events.get(name)
            baseline_event = baseline_events.get(name)
            if isinstance(current_event, int) and isinstance(baseline_event, int):
                event_deltas[name] = current_event - baseline_event
    reason = "admitted"
    admitted = True
    if not valid_current or safe_limit is None or predicted is None:
        admitted = True
        reason = "conservative_non_cgroup"
    elif any(delta > 0 for delta in event_deltas.values()):
        admitted = False
        reason = "memory_event_advanced"
    elif (
        hard_pressure_ceiling is not None
        and predicted_hard_pressure is not None
        and predicted_hard_pressure > hard_pressure_ceiling
    ):
        admitted = False
        reason = "hard_cgroup_pressure"
    elif (
        baseline_effective is not None
        and effective - baseline_effective > DEFAULT_STAGE_ESTIMATE
    ):
        admitted = False
        reason = "observed_growth_exceeded_estimate"
    elif predicted > safe_limit:
        admitted = False
        reason = "predicted_effective_usage_exceeds_target"
    return {
        "raw_cgroup_bytes": current,
        "inactive_file_bytes": inactive if working_set_metrics else None,
        "effective_working_set_bytes": effective,
        "stage_estimate_bytes": estimate,
        "predicted_effective_bytes": predicted,
        "reclaimable_allowance_bytes": reclaimable_allowance,
        "hard_pressure_margin_bytes": HARD_PRESSURE_MARGIN_BYTES,
        "hard_pressure_ceiling_bytes": hard_pressure_ceiling,
        "predicted_hard_pressure_bytes": predicted_hard_pressure,
        "target_ceiling_bytes": safe_limit,
        "raw_headroom_bytes": (
            finite_limit - current if valid_cgroup else None
        ),
        "effective_headroom_bytes": (
            safe_limit - effective
            if safe_limit is not None and isinstance(effective, int) else None
        ),
        "accounting_mode": accounting_mode,
        "memory_event_deltas": event_deltas,
        "admitted": admitted,
        "reason": reason,
    }


def enforce_memory_budget(
    stage: str, estimate: int = DEFAULT_STAGE_ESTIMATE, *,
    baseline_events: dict[str, int] | None = None,
    baseline_effective: int | None = None,
    observer: Callable[[], dict[str, Any]] | None = None,
    decision_observer: Callable[[str, dict[str, Any], dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Refuse a stage before the process can approach the platform OOM limit."""
    snapshot = (observer or memory_snapshot)()
    admission = memory_admission(
        snapshot, estimate, baseline_events=baseline_events,
        baseline_effective=baseline_effective,
    )
    result = {**snapshot, "admission": admission}
    if decision_observer:
        decision_observer(stage, admission, result)
    if not admission["admitted"]:
        raise MarketMemoryBudgetError(stage, admission)
    return result


def _object_counts() -> dict[str, int]:
    counts = Counter(type(item).__name__ for item in gc.get_objects())
    return {name: counts.get(name, 0) for name in ("dict", "list", "tuple", "str")}


class AssetSequence(Sequence[dict[str, Any]]):
    """Compatibility sequence backed by bounded SQLite reads."""

    def __init__(self, model: MarketReadModel) -> None:
        self.model = model

    def __len__(self) -> int:
        return self.model.asset_count

    def __getitem__(self, index: int | slice) -> dict[str, Any] | list[dict[str, Any]]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            rows = self.model.fetch_summaries(stop - start, start)
            return rows[::step]
        if index < 0:
            index += len(self)
        rows = self.model.fetch_summaries(1, index)
        if not rows:
            raise IndexError(index)
        return rows[0]

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for offset in range(0, len(self), 250):
            yield from self.model.fetch_summaries(250, offset)


class AssetMapping(Mapping[str, dict[str, Any]]):
    """Compatibility ID mapping without an in-memory universe-sized dictionary."""

    def __init__(self, model: MarketReadModel) -> None:
        self.model = model

    def __len__(self) -> int:
        return self.model.asset_count

    def __iter__(self) -> Iterator[str]:
        with self.model.connection() as connection:
            for row in connection.execute("SELECT asset_id FROM assets ORDER BY asset_id"):
                yield str(row[0])

    def __getitem__(self, key: str) -> dict[str, Any]:
        row = self.model.summary(key)
        if row is None:
            raise KeyError(key)
        return row


class MarketReadModel:
    """One compatible immutable SQLite market generation."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with self.connection() as connection:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            self.asset_count = int(metadata.get("asset_count", "0"))
        self.assets = AssetSequence(self)
        self.by_id = AssetMapping(self)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        try:
            yield connection
        finally:
            connection.close()

    def metadata(self) -> dict[str, Any]:
        with self.connection() as connection:
            values = dict(connection.execute("SELECT key, value FROM metadata"))
        return {key: json.loads(value) for key, value in values.items()}

    def fetch_summaries(self, limit: int, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT summary_json FROM assets ORDER BY asset_id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_json_object(str(row[0])) for row in rows]

    def cooperative_summary_metadata(
        self,
        *,
        chunk_size: int = 64,
        yield_control: Callable[[], None] | None = None,
        chunk_observer: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Prepare compact generation metadata without retaining decoded rows.

        Artifact rows remain disk-backed. Each bounded batch is decoded, reduced,
        and released before yielding the interpreter to request-serving threads.
        """
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        release = yield_control or (lambda: time.sleep(0))
        counts: dict[str, int] = {"total": 0}
        seen: set[str] = set()
        duplicates = 0
        offset = 0
        chunks = 0
        maximum_chunk_ms = 0.0
        while True:
            started = time.perf_counter()
            with self.connection() as connection:
                rows = connection.execute(
                    "SELECT asset_id, summary_json FROM assets "
                    "ORDER BY asset_id LIMIT ? OFFSET ?",
                    (chunk_size, offset),
                ).fetchall()
            if not rows:
                break
            for row in rows:
                asset_id = str(row[0])
                summary = _json_object(str(row[1]))
                key = (
                    summary["asset_type"]
                    if summary["asset_type"] == "pick"
                    else summary["availability"]
                )
                counts[key] = counts.get(key, 0) + 1
                if asset_id in seen:
                    duplicates += 1
                else:
                    seen.add(asset_id)
            counts["total"] += len(rows)
            offset += len(rows)
            chunks += 1
            elapsed_ms = (time.perf_counter() - started) * 1000
            maximum_chunk_ms = max(maximum_chunk_ms, elapsed_ms)
            if chunk_observer:
                chunk_observer({
                    "sequence": chunks,
                    "rows": len(rows),
                    "duration_ms": round(elapsed_ms, 3),
                })
            del rows
            release()
        return {
            "counts": counts,
            "duplicate_asset_ids": duplicates,
            "chunks": chunks,
            "maximum_chunk_ms": round(maximum_chunk_ms, 3),
        }

    def summary(self, asset_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT summary_json FROM assets WHERE asset_id=?", (asset_id,),
            ).fetchone()
        return _json_object(str(row[0])) if row else None

    def canonical(self, asset_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT canonical_json FROM assets WHERE asset_id=?", (asset_id,),
            ).fetchone()
        return _json_object(str(row[0])) if row else None

    def query(
        self, where: list[str], parameters: list[Any], order_column: str,
        direction: str, limit: int, offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        clause = " AND ".join(where) if where else "1=1"
        order = "ASC" if direction.casefold() == "asc" else "DESC"
        null_order = "ASC" if order == "DESC" else "DESC"
        with self.connection() as connection:
            total = int(connection.execute(
                f"SELECT COUNT(*) FROM assets WHERE {clause}", parameters,
            ).fetchone()[0])
            rows = connection.execute(
                f"SELECT summary_json FROM assets WHERE {clause} "
                f"ORDER BY ({order_column} IS NULL) {null_order}, {order_column} {order}, "
                f"asset_id {order} LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        return total, [_json_object(str(row[0])) for row in rows]

    def search(self, tokens: tuple[str, ...], clauses: list[str], params: list[Any], limit: int) -> list[dict[str, Any]]:
        where = list(clauses)
        parameters = list(params)
        for token in tokens:
            where.append("search_text LIKE ?")
            parameters.append(f"%{token}%")
        condition = " AND ".join(where) if where else "1=1"
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT summary_json FROM assets WHERE {condition} "
                "ORDER BY display_name COLLATE NOCASE, asset_id LIMIT ?",
                (*parameters, limit),
            ).fetchall()
        return [_json_object(str(row[0])) for row in rows]


def build_read_model(
    target: Path, generation: str, rows: Iterator[tuple[dict[str, Any], dict[str, Any]]],
    metadata: dict[str, Any], stage_observer: Callable[[dict[str, Any]], None] | None = None,
    *, chunk_size: int = 32, yield_control: Callable[[], None] | None = None,
    admission_observer: Callable[[str, dict[str, Any], dict[str, Any]], None] | None = None,
) -> MarketReadModel:
    """Stream one generation to SQLite, then publish it atomically."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    # A zero-duration sleep can immediately reacquire the interpreter under a
    # constrained Linux cgroup. A bounded 10 ms handoff gives request-serving
    # and health-check work a reliable scheduling opportunity without moving
    # construction onto the request path.
    release = yield_control or (lambda: time.sleep(0.010))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.partial")
    temporary.unlink(missing_ok=True)
    stages: list[dict[str, Any]] = []

    def observe(stage: str, started: float, before: dict[str, Any], count: int) -> None:
        after = memory_snapshot()
        row = {
            "stage": stage, "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "memory_before": before, "memory_after": after, "rows": count,
            "object_counts": _object_counts(),
        }
        stages.append(row)
        if stage_observer:
            stage_observer(row)

    try:
        before = enforce_memory_budget(
            "artifact_initialization", 32 * 1024 * 1024,
            decision_observer=admission_observer,
        )
        baseline_events = dict(before.get("cgroup_memory_events") or {})
        baseline_effective = before["admission"].get("effective_working_set_bytes")
        started = time.perf_counter()
        connection = sqlite3.connect(temporary, timeout=30)
        try:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            observe("artifact_initialization", started, before, 0)
            count = 0
            started = time.perf_counter()
            before = enforce_memory_budget(
                "canonical_asset_iteration", baseline_events=baseline_events,
                baseline_effective=baseline_effective,
                decision_observer=admission_observer,
            )
            for summary, canonical in rows:
                values = summary.get("values") or {}
                owner = summary.get("owner") or {}
                search_text = " ".join((
                    str(summary["asset_id"]), str(summary["display_name"]),
                    str(summary.get("position") or ""), str(summary.get("nfl_team") or ""),
                    str(owner.get("team_name") or ""), str(owner.get("owner") or ""),
                    str(summary["availability"]),
                )).casefold()
                connection.execute(
                    "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        summary["asset_id"], summary["asset_type"], summary["display_name"],
                        summary.get("position"), summary.get("nfl_team"), summary.get("age"),
                        summary.get("status"), summary["availability"], owner.get("roster_id"),
                        summary.get("year"), summary.get("round"), int(bool(summary.get("rookie"))),
                        values.get("market_value"), values.get("intrinsic_dtos_value"),
                        values.get("league_adjusted_value"), values.get("contender_value"),
                        values.get("rebuilder_value"), values.get("confidence_score"),
                        values.get("risk_score"), values.get("liquidity_score"), search_text,
                        _json(summary), _json(canonical),
                    ),
                )
                count += 1
                if count % 250 == 0:
                    connection.commit()
                    enforce_memory_budget(
                        "canonical_asset_iteration", baseline_events=baseline_events,
                        baseline_effective=baseline_effective,
                        decision_observer=admission_observer,
                    )
                if count % chunk_size == 0:
                    release()
            if count % chunk_size:
                release()
            observe("canonical_asset_iteration", started, before, count)
            started = time.perf_counter()
            before = enforce_memory_budget(
                "model_publication", 16 * 1024 * 1024,
                baseline_events=baseline_events,
                baseline_effective=baseline_effective,
                decision_observer=admission_observer,
            )
            complete_metadata = {
                **metadata, "generation": generation, "schema_version": MARKET_READ_MODEL_SCHEMA,
                "asset_count": count, "complete": True, "build_stages": stages,
            }
            connection.executemany(
                "INSERT INTO metadata(key,value) VALUES (?,?)",
                ((key, _json(value)) for key, value in complete_metadata.items()),
            )
            connection.commit()
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.close()
            _fsync_file(temporary)
            os.replace(temporary, target)
            _fsync_directory(target.parent)
            observe("model_publication", started, before, count)
        finally:
            try:
                connection.close()
            except UnboundLocalError:
                pass
        return MarketReadModel(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def approximate_size(value: Any) -> int:
    """Bounded diagnostic for one object graph without retaining references."""
    seen: set[int] = set()

    def walk(item: Any) -> int:
        identity = id(item)
        if identity in seen:
            return 0
        seen.add(identity)
        size = sys.getsizeof(item)
        if isinstance(item, dict):
            size += sum(walk(key) + walk(child) for key, child in item.items())
        elif isinstance(item, (list, tuple, set)):
            size += sum(walk(child) for child in item)
        return size

    return walk(value)
