"""Bounded, deterministic Asset Market over canonical cached DTOS contracts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil

from app_metadata import BUILD_NUMBER, VERSION
from src.core.brain import brain_service
from src.core.historical_memory.read_model import historical_graph
from src.core.historical_memory.models import DATABASE_MIGRATION_VERSION
from src.core.history_context.store import CanonicalHistoryStore as HistoricalStore
from src.core.valuation_intelligence.engine import (
    asset_market_input_revision,
)
from src.core.valuation.universe import LAYER_NAMES, ValuationUniverse
from src.core.asset_market.read_model import (
    MARKET_READ_MODEL_SCHEMA,
    MarketMemoryBudgetError,
    MarketReadModel,
    build_read_model,
    memory_admission,
)
from src.core.asset_market.semantic_contract import (
    PROTOCOL_VERSION,
    digest as _digest,
    reference_identities,
    semantic_record,
)
from src.core.asset_market.resource_diagnostics import resource_diagnostics
from src.platform.lifecycle import lifecycle_coordinator, memory_snapshot

MARKET_SCHEMA_VERSION = "1.0"
SORT_FIELDS = {
    "market": "market_value",
    "intrinsic": "intrinsic_dtos_value",
    "league": "league_adjusted_value",
    "contender": "contender_value",
    "rebuilder": "rebuilder_value",
    "confidence": "confidence_score",
    "risk": "risk_score",
    "liquidity": "liquidity_score",
}

MEMORY_ADMISSION_BACKOFF_SECONDS = 30.0
MEMORY_ADMISSION_IMPROVEMENT_BYTES = 64 * 1024 * 1024

SEMANTIC_CHILD_TIMEOUT_SECONDS = 30.0
SEMANTIC_CHILD_MEMORY_ESTIMATE = 96 * 1024 * 1024
SEMANTIC_STREAM_FLUSH_RECORDS = 16
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MarketWarmingError(RuntimeError):
    """Raised when no safe market snapshot exists during a heavy lifecycle phase."""


class _BuildDeferred(RuntimeError):
    """Internal signal that a guarded background build was safely deferred."""


class SemanticWorkerError(RuntimeError):
    """Raised when isolated semantic preparation fails closed."""


def _layer_value(asset: dict[str, Any], name: str) -> float | None:
    value = ((asset.get("layers") or {}).get(name) or {}).get("value")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _display_name(asset: dict[str, Any]) -> str:
    identity = asset.get("identity") or {}
    return str(
        identity.get("player_name")
        or identity.get("draft_pick_description")
        or asset.get("asset_id")
    )


def _canonical_url(asset: dict[str, Any]) -> str:
    identity = asset.get("identity") or {}
    if asset.get("asset_type") == "pick":
        raw = str(asset["asset_id"]).split(":")
        return f"/picks/PICK-{raw[1]}-R{raw[2]}-ORIG{raw[3]}"
    return f"/players/{identity.get('sleeper_id')}"


def _availability(asset: dict[str, Any]) -> str:
    identity = asset.get("identity") or {}
    if asset.get("asset_type") == "pick":
        return "owned_pick"
    owner = identity.get("current_owner")
    slot = str((owner or {}).get("roster_slot") or "").casefold()
    status = str(identity.get("status") or "").casefold()
    if slot in {"taxi", "reserve", "ir"}:
        return slot
    if owner:
        return "rostered"
    if status in {"inactive", "retired"}:
        return status
    return "day_traders_free_agent"


def _market_id_from_history(canonical_id: str) -> str:
    if canonical_id.startswith("DTOS-P-"):
        return f"player:{canonical_id.removeprefix('DTOS-P-')}"
    if canonical_id.startswith("PICK-"):
        parts = canonical_id.split("-")
        if len(parts) >= 4:
            return ":".join((
                "pick", parts[1], parts[2].removeprefix("R"),
                parts[3].removeprefix("ORIG"),
            ))
    return canonical_id


def _summary(asset: dict[str, Any], brain_asset: dict[str, Any] | None) -> dict[str, Any]:
    identity = asset.get("identity") or {}
    audit = asset.get("audit") or {}
    scores = (brain_asset or {}).get("scores") or {}
    values = {name: _layer_value(asset, name) for name in LAYER_NAMES}
    brain_layers = (brain_asset or {}).get("valuation_layers") or {}
    for name, layer in brain_layers.items():
        if name in values and isinstance(layer, dict):
            value = layer.get("value")
            values[name] = float(value) if value is not None else None
    owner = identity.get("current_owner") or {}
    historical = bool(identity.get("sleeper_id"))
    return {
        "asset_id": asset["asset_id"],
        "asset_type": asset["asset_type"],
        "display_name": _display_name(asset),
        "position": identity.get("position"),
        "nfl_team": identity.get("nfl_team"),
        "age": identity.get("age"),
        "status": identity.get("status"),
        "owner": owner or None,
        "availability": _availability(asset),
        "rookie": bool(identity.get("rookie_class")),
        "year": identity.get("year"),
        "round": identity.get("round"),
        "values": values,
        "confidence": int(scores.get("confidence", audit.get("confidence") or 0)),
        "agreement": int(scores.get("agreement") or 0),
        "evidence_coverage": int(scores.get("coverage") or 0),
        "provider_coverage": int(audit.get("provider_count") or 0),
        "missing_evidence": list((brain_asset or {}).get("missing_evidence") or []),
        "historical_availability": "available" if historical else "unavailable",
        "canonical_url": _canonical_url(asset),
        "market_detail_url": f"/api/market/assets/{asset['asset_id']}",
    }


class AssetMarket:
    """Immutable compact index with detail hydration delegated to canonical systems."""

    def __init__(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str, *, generation: str,
        artifact_path: Path, load_existing: bool = False,
        compatibility: dict[str, Any] | None = None,
        admission_observer: Any = None,
    ) -> None:
        started = time.perf_counter()
        self.data = data
        self.state = state
        self.store = store
        self.league_id = league_id
        self.dataset_version = store.dataset_version(league_id)
        brain = brain_service(data)
        self._brain = brain
        self.brain_generation = brain.report.get("generated_at")
        self.generated_at = datetime.now(timezone.utc).isoformat()
        self._prepared_health: dict[str, Any] | None = None
        self._memory_admission: dict[str, Any] | None = None
        if load_existing:
            self._read_model = MarketReadModel(artifact_path)
            metadata = self._read_model.metadata()
            self.generated_at = str(metadata["generated_at"])
            self.brain_generation = metadata.get("brain_generation")
            self._prepared_health = self._read_model.cooperative_summary_metadata()
        else:
            universe = ValuationUniverse.streaming(data, state)

            def rows():
                for asset in universe.iter_assets():
                    yield _summary(asset, brain.asset(asset["asset_id"])), asset

            self._read_model = build_read_model(
                artifact_path, generation, rows(), {
                    "generated_at": self.generated_at,
                    "brain_generation": self.brain_generation,
                    "historical_dataset_version": self.dataset_version,
                    "valuation_generation": (
                        (data.get("valuation_intelligence") or {}).get("generated_at")
                    ),
                    "semantic_identity": {
                        key: value for key, value in (compatibility or {}).items()
                        if key.endswith("_digest") or key == "asset_count"
                    },
                    "compatibility": compatibility or {},
                },
                admission_observer=admission_observer,
            )
        metadata = self._read_model.metadata()
        self.semantic_generation = str(metadata["generation"])
        self.semantic_identity = dict(metadata.get("semantic_identity") or {})
        stages = list(metadata.get("build_stages") or [])
        if stages:
            before = stages[-1].get("memory_before") or {}
            admission = before.get("admission") or {}
            allowed = {
                "raw_cgroup_bytes", "inactive_file_bytes",
                "effective_working_set_bytes", "stage_estimate_bytes",
                "predicted_effective_bytes", "target_ceiling_bytes",
                "raw_headroom_bytes", "effective_headroom_bytes",
                "reclaimable_allowance_bytes", "hard_pressure_margin_bytes",
                "hard_pressure_ceiling_bytes", "predicted_hard_pressure_bytes",
                "accounting_mode", "memory_event_deltas", "admitted", "reason",
            }
            self._memory_admission = {
                key: value for key, value in admission.items() if key in allowed
            }
        self.assets = self._read_model.assets
        self.by_id = self._read_model.by_id
        self._artifact_path = artifact_path
        self.build_duration_ms = round((time.perf_counter() - started) * 1000, 3)

    def identity(
        self, brain_snapshot_id: str | None = None,
        dataset_version: str | None = None,
    ) -> dict[str, Any]:
        dataset_scope = "live_store" if dataset_version is not None else "artifact_build"
        identity = {
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "market_schema_version": MARKET_SCHEMA_VERSION,
            "league_id": self.league_id,
            "historical_dataset_version": dataset_version
            or self.dataset_version,
            "historical_dataset_version_scope": dataset_scope,
            "market_generation": self.generated_at,
            "brain_generation": self.brain_generation,
            "valuation_generation": (
                (self.data.get("valuation_intelligence") or {}).get("generated_at")
            ),
            "generated_at": self.generated_at,
        }
        if brain_snapshot_id is not None:
            identity["brain_snapshot_id"] = brain_snapshot_id
        return identity

    def audit_identity(self) -> dict[str, Any]:
        """Expose retained canonical identities without evaluation or durable reads."""
        semantic = self._brain.report.get("semantic_generation")
        return {
            **self.identity(),
            "brain_snapshot_id": f"{VERSION}:{semantic or 'pending'}",
            "brain_semantic_generation": semantic,
        }

    def health(self) -> dict[str, Any]:
        prepared = self._prepared_health
        if prepared is None:
            prepared = self._read_model.cooperative_summary_metadata()
            self._prepared_health = prepared
        return {
            **self.identity(), "status": "ready", "counts": prepared["counts"],
            "duplicate_asset_ids": prepared["duplicate_asset_ids"],
            "build_duration_ms": self.build_duration_ms,
            "read_contract": {
                "provider_sync": False, "pagination_before_hydration": True,
                "single_flight": True, "detail_history_hydration": "on_demand",
            },
            "dataset_identity_cache": self.store.dataset_version_metrics(),
            "search_index": {
                "current_assets": len(self.assets),
                "historical_players": "on_demand",
                "normalization": "durable_build_time",
                "storage": "bounded_sqlite",
            },
            "memory_admission": dict(self._memory_admission or {}),
            "semantic_identity": dict(self.semantic_identity),
            "artifact_brain_semantic_digest": self.semantic_identity.get(
                "brain_semantic_output_digest"
            ),
        }

    def directory(
        self, *, offset: int = 0, limit: int = 50, sort: str = "market",
        direction: str = "desc", asset_type: str | None = None,
        position: str | None = None, availability: str | None = None,
        owner: int | None = None, minimum: float | None = None,
        maximum: float | None = None, age_min: float | None = None,
        age_max: float | None = None, year: int | None = None,
        round_number: int | None = None,
    ) -> dict[str, Any]:
        layer = SORT_FIELDS.get(sort, "market_value")
        columns = {
            "market_value": "market_value", "intrinsic_dtos_value": "intrinsic_value",
            "league_adjusted_value": "league_value", "contender_value": "contender_value",
            "rebuilder_value": "rebuilder_value", "confidence_score": "confidence_value",
            "risk_score": "risk_value", "liquidity_score": "liquidity_value",
        }
        column = columns[layer]
        where: list[str] = []
        parameters: list[Any] = []
        for value, expression in (
            (asset_type, "asset_type=?"), (position, "position=?"),
            (availability, "availability=?"), (owner, "owner_id=?"),
            (year, "year=?"), (round_number, "round_number=?"),
        ):
            if value is not None:
                where.append(expression)
                parameters.append(value)
        for value, expression in (
            (age_min, "age>=?"), (age_max, "age<=?"),
            (minimum, f"{column}>=?"), (maximum, f"{column}<=?"),
        ):
            if value is not None:
                where.append(expression)
                parameters.append(value)
        total, page = self._read_model.query(
            where, parameters, column, direction, limit, offset,
        )
        page = [dict(row, rank=offset + index + 1) for index, row in enumerate(page)]
        return {
            **self.identity(), "total": total, "offset": offset,
            "limit": limit, "sort": sort, "direction": direction,
            "tie_breaker": "canonical_asset_id", "assets": page,
        }

    def search(self, query: str, limit: int = 50) -> dict[str, Any]:
        needle = query.strip().casefold()
        normalized = needle.replace("-", " ")
        wants_free_agent = "free agent" in normalized
        wants_taxi = "taxi" in normalized
        wants_rookie = "rookie" in normalized
        wants_pick = "pick" in normalized or "draft" in normalized
        position = next((
            value for phrase, value in (
                ("qb", "QB"), ("rb", "RB"), ("wr", "WR"), ("te", "TE"),
                ("quarterback", "QB"), ("running back", "RB"),
                ("wide receiver", "WR"), ("tight end", "TE"),
            ) if phrase in normalized
        ), None)
        ignored = {
            "free", "agent", "agents", "rookie", "rookies", "taxi",
            "pick", "picks", "draft", "quarterback", "quarterbacks",
            "running", "back", "backs", "wide", "receiver", "receivers",
            "tight", "end", "ends",
            "1st", "2nd", "3rd", "4th", "5th", "6th", "7th",
        }
        tokens = tuple(
            token for token in normalized.split() if token and token not in ignored
        )
        clauses: list[str] = []
        parameters: list[Any] = []
        if wants_free_agent:
            clauses.append("availability=?")
            parameters.append("day_traders_free_agent")
        if wants_taxi:
            clauses.append("availability=?")
            parameters.append("taxi")
        if wants_rookie:
            clauses.append("rookie=1")
        if wants_pick:
            clauses.append("asset_type='pick'")
        if position:
            clauses.append("position=?")
            parameters.append(position)
        rows = self._read_model.search(tokens, clauses, parameters, limit)
        historical_resolution = bool(
            needle and tokens and not rows
            and not any((
                wants_free_agent, wants_taxi, wants_rookie, wants_pick,
                position is not None,
            ))
        )
        current_players = self.data.get("players") or {}
        extras = []
        if historical_resolution:
            for identity in self.store.identities():
                provider_id = str(identity["provider_player_id"])
                search_text = " ".join((
                    provider_id, str(identity.get("display_name") or ""),
                    f"DTOS-P-{provider_id}",
                )).casefold()
                if provider_id in current_players or not all(token in search_text for token in tokens):
                    continue
                asset_id = f"DTOS-P-{provider_id}"
                if _market_id_from_history(asset_id) in self.by_id:
                    continue
                extras.append({
                    "asset_id": asset_id, "asset_type": "player",
                    "display_name": identity.get("display_name")
                    or f"Unresolved Sleeper player {provider_id}",
                    "position": (identity.get("metadata") or {}).get("position"),
                    "nfl_team": None, "owner": None,
                    "resolution_status": "resolved" if int(identity.get("confidence") or 0) >= 70 else "unresolved",
                    "market_value": None, "contender_value": None,
                    "rebuilder_value": None, "confidence": 0,
                    "canonical_url": f"/players/{provider_id}",
                    "historical_availability": "available",
                })
        existing = {row["asset_id"] for row in extras}
        transaction_query = bool(
            needle and (
                "trade" in normalized or "transaction" in normalized
                or normalized.startswith("tx ")
            )
        )
        transactions = (
            self.store.search_transaction_ids(self.league_id, query, limit)
            if transaction_query else []
        )
        for transaction in transactions:
            transaction_id = transaction["source_record_id"]
            source_league = str(
                (transaction.get("payload") or {}).get("source_league_id")
                or self.league_id
            )
            prefix = "TRADE" if transaction["entity_type"] == "trade" else "TX"
            canonical_id = f"{prefix}-{source_league}-{transaction_id}"
            if canonical_id in existing:
                continue
            extras.append({
                "asset_id": canonical_id,
                "asset_type": transaction["entity_type"],
                "display_name": f"{transaction['entity_type'].title()} {transaction_id}",
                "position": None, "nfl_team": None, "owner": None,
                "resolution_status": "resolved", "market_value": None,
                "contender_value": None, "rebuilder_value": None,
                "confidence": 100,
                "canonical_url": (
                    f"/trades/history/{transaction_id}"
                    if transaction["entity_type"] == "trade"
                    else f"/transactions?search={transaction_id}"
                ),
                "historical_availability": "available",
            })
        for team in self.data.get("teams") or []:
            label = str(team.get("team_name") or team.get("owner") or "")
            if needle and needle not in label.casefold() and needle not in str(team.get("owner") or "").casefold():
                continue
            roster_id = int(team.get("roster_id") or 0)
            extras.append({
                "asset_id": f"{self.league_id}:franchise:{roster_id}",
                "asset_type": "team", "display_name": label,
                "position": None, "nfl_team": None,
                "owner": {"roster_id": roster_id, "owner": team.get("owner")},
                "resolution_status": "resolved", "market_value": None,
                "contender_value": None, "rebuilder_value": None,
                "confidence": 100, "canonical_url": f"/teams/{roster_id}",
                "historical_availability": "available",
            })
        compact = [{
            **row, "resolution_status": "resolved",
            "market_value": row["values"].get("market_value"),
            "contender_value": row["values"].get("contender_value"),
            "rebuilder_value": row["values"].get("rebuilder_value"),
        } for row in rows]
        combined = sorted([*compact, *extras], key=lambda row: (
            str(row.get("display_name") or "").casefold(), str(row["asset_id"]),
        ))[:limit]
        dataset_version = self.store.dataset_version(self.league_id)
        return {
            **self.identity(dataset_version=dataset_version), "query": query,
            "count": len(combined), "results": combined,
        }

    def detail(self, asset_id: str, front_office: int | None = None) -> dict[str, Any] | None:
        row = self.by_id.get(asset_id)
        if row is None:
            return None
        brain_asset = self._brain.asset(asset_id)
        decision = self._brain.decision("Asset Market", (asset_id,))
        historical_dataset_version = self.store.dataset_version(self.league_id)
        graph = historical_graph(
            self.store, self.league_id, self.data, historical_dataset_version,
        )
        if row["asset_type"] == "player":
            raw_id = asset_id.removeprefix("player:")
            history = graph.player_dossier(raw_id)
        else:
            _, season, round_number, original = asset_id.split(":", 3)
            history = graph.pick_dossier(f"PICK-{season}-R{round_number}-ORIG{original}")
        canonical = self._read_model.canonical(asset_id) or {}
        canonical_layers = dict(canonical.get("layers") or {})
        canonical_layers.update({
            name: {**(canonical_layers.get(name) or {}), **layer}
            for name, layer in ((brain_asset or {}).get("valuation_layers") or {}).items()
            if isinstance(layer, dict)
        })
        return {
            **self.identity(
                decision.brain_snapshot_id, historical_dataset_version,
            ), "asset": row,
            "valuation": brain_asset,
            "value_layers": {
                name: {
                    **layer, "scale": "DTOS 0-10000 normalized scale",
                    "dataset_version": historical_dataset_version,
                    "brain_snapshot_id": decision.brain_snapshot_id,
                    "provider_coverage": row["provider_coverage"],
                    "agreement": row["agreement"],
                    "evidence_categories": [
                        item["name"] for item in (brain_asset or {}).get("categories", [])
                        if item.get("available")
                    ],
                    "missing_evidence": row["missing_evidence"],
                    "limitations": (
                        [] if layer.get("value") is not None
                        else ["This canonical layer is unavailable; no substitute value was used."]
                    ),
                }
                for name, layer in canonical_layers.items()
            },
            "providers": list(
                canonical.get("providers") or []
            ),
            "front_office": front_office,
            "recommendation": {
                "action": "Monitor",
                "availability": "advisory_only",
                "primary_reason": "Canonical Brain evidence is available for review; DTOS does not execute transactions.",
                "supporting_evidence": list(decision.recommendation_explanation),
                "counterarguments": list((brain_asset or {}).get("missing_evidence") or []),
                "expected_impact": "Requires Front Office judgment.",
                "confidence": decision.confidence.value,
                "missing_evidence": list((brain_asset or {}).get("missing_evidence") or []),
                "brain_snapshot_id": decision.brain_snapshot_id,
                "decision_provenance": list(decision.decision_provenance),
            },
            "history": history,
        }

    def trending(self, limit: int = 10) -> dict[str, Any]:
        timeline = (self.data.get("valuation_intelligence") or {}).get("timeline") or {}
        comparable = []
        for asset_id, observations in timeline.items():
            if not isinstance(observations, list) or len(observations) < 2:
                continue
            asset = self.by_id.get(asset_id)
            if asset is None:
                continue
            first, last = observations[0], observations[-1]
            start = first.get("confidence")
            end = last.get("confidence")
            if start is None or end is None or first.get("timestamp") == last.get("timestamp"):
                continue
            comparable.append({
                "asset": asset, "starting_observation": first,
                "ending_observation": last, "direction": "rising" if end > start else "falling" if end < start else "stable",
                "magnitude": end - start, "measurement": "canonical evidence confidence",
                "reason": "Comparable timestamped Brain observations are available.",
            })
        risers = sorted(comparable, key=lambda row: (row["magnitude"], row["asset"]["asset_id"]), reverse=True)[:limit]
        fallers = sorted(comparable, key=lambda row: (row["magnitude"], row["asset"]["asset_id"]))[:limit]
        available = bool(comparable)
        unavailable = None if available else "At least two timestamped comparable canonical Brain observations are required."
        return {
            **self.identity(), "measurement_window": "oldest_to_latest_retained_brain_observation",
            "minimum_evidence": "two timestamped comparable observations",
            "biggest_risers": risers if available else [],
            "biggest_fallers": fallers if available else [],
            "most_stable": [row for row in comparable if row["magnitude"] == 0][:limit],
            "most_discussed": {"status": "unsupported", "reason": "No verified discussion-data provider is configured."},
            "availability": "available" if available else "unavailable",
            "unavailable_reason": unavailable,
        }


class AssetMarketCache:
    """Single-flight last-valid cache keyed by every canonical input identity."""

    def __init__(
        self, *, clock: Any = None, memory_observer: Any = None,
        semantic_process_factory: Any = None, resource_context_provider: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self._build_lock = threading.Lock()
        self._key: str | None = None
        self._store_identity: str | None = None
        self._market: AssetMarket | None = None
        self.build_count = 0
        self.hits = 0
        self.last_error: str | None = None
        self.last_miss_reason: str | None = None
        self._health_metadata: dict[str, Any] = {}
        self._building = False
        self._build_thread: threading.Thread | None = None
        self._build_phase = "idle"
        self._build_started_at: str | None = None
        self._build_started_monotonic: float | None = None
        self._build_duration_ms: float | None = None
        self._refresh_state = "idle"
        self._artifact_compatibility = "discovery_pending"
        self.artifact_candidates = 0
        self.artifact_loads = 0
        self.artifact_restore_failures = 0
        self.durable_publications = 0
        self._request_marker: tuple[Any, ...] | None = None
        self._requested_generation: str | None = None
        self._memory_backoff: dict[str, Any] | None = None
        self.attempted_constructions = 0
        self.rebuild_requests = 0
        self.semantic_rebuild_requests = 0
        self.noop_rebuild_requests = 0
        self.construction_admission_skips = 0
        self.actual_constructions = 0
        self._scheduler_state = "idle"
        self._scheduler_last_invoked: str | None = None
        self._scheduler_skip_reason: str | None = None
        self.failed_constructions = 0
        self._clock = clock or time.monotonic
        self._memory_observer = memory_observer or memory_snapshot
        self._semantic_process_factory = semantic_process_factory or subprocess.Popen
        self._resource_context_provider = resource_context_provider or (lambda: {})
        self._semantic_preparation: dict[str, Any] = {}
        self._prepared_semantic_contract: tuple[
            tuple[Any, ...], dict[str, Any]
        ] | None = None
        self.semantic_child_count = 0
        self._epoch = 0
        self.artifact_cleanup_count = 0
        self.artifact_cleanup_failures = 0
        self.diagnostic_write_failures = 0
        self._admission_signatures: dict[tuple[str, str], tuple[bool, str]] = {}

    def _resource_context(self) -> dict[str, Any]:
        try:
            return dict(self._resource_context_provider() or {})
        except Exception:
            return {}

    def configure_resource_context_provider(self, provider: Any) -> None:
        """Attach a bounded context observer without changing cache behavior."""
        self._resource_context_provider = provider or (lambda: {})

    def _record_admission(
        self, league_id: str, stage: str, admission: dict[str, Any],
        snapshot: dict[str, Any] | None = None, storage_root: Path | None = None,
    ) -> None:
        signature = (
            bool(admission.get("admitted")), str(admission.get("reason") or "other"),
        )
        key = (str(league_id), stage)
        if signature[0] and self._admission_signatures.get(key) == signature:
            return
        self._admission_signatures[key] = signature
        context = {**self._resource_context(), **dict(snapshot or {})}
        context.update({
            "semantic_child_count": self.semantic_child_count,
            "active_construction_count": int(self._building),
        })
        try:
            resource_diagnostics.record(
                league_id, stage, admission, context=context, root=storage_root,
            )
        except OSError:
            self.diagnostic_write_failures += 1

    def _record_semantic_preparation(self, metrics: dict[str, Any]) -> None:
        """Retain one bounded summary without retaining canonical asset data."""
        with self._lock:
            self._semantic_preparation = dict(metrics)

    def _memory_backoff_active(
        self, request_marker: tuple[Any, ...],
    ) -> bool:
        """Return whether a failed admission still applies to this request."""
        with self._lock:
            backoff = dict(self._memory_backoff or {})
        if not backoff:
            return False
        now = float(self._clock())
        if backoff.get("request_marker") != request_marker or now >= float(
            backoff.get("expires_monotonic", 0.0)
        ):
            with self._lock:
                self._memory_backoff = None
            return False
        try:
            current = memory_admission(self._memory_observer(), estimate=0)
            previous = int(backoff.get("effective_working_set_bytes") or 0)
            improved = previous - int(
                current.get("effective_working_set_bytes") or 0
            )
            if current.get("admitted") and improved >= MEMORY_ADMISSION_IMPROVEMENT_BYTES:
                with self._lock:
                    self._memory_backoff = None
                return False
        except (OSError, TypeError, ValueError):
            pass
        with self._lock:
            self._build_phase = "memory_backoff"
            self._refresh_state = "memory_backoff"
        return True

    def _record_memory_backoff(
        self, request_marker: tuple[Any, ...], error: MarketMemoryBudgetError,
    ) -> None:
        observation = dict(error.observation)
        now = float(self._clock())
        with self._lock:
            self._memory_backoff = {
                "request_marker": request_marker,
                "requested_generation": self._requested_generation,
                "reason": observation.get("reason", "memory_admission_failed"),
                "accounting_mode": observation.get("accounting_mode"),
                "raw_cgroup_bytes": observation.get("raw_cgroup_bytes"),
                "inactive_file_bytes": observation.get("inactive_file_bytes"),
                "effective_working_set_bytes": observation.get(
                    "effective_working_set_bytes"
                ),
                "target_ceiling_bytes": observation.get("target_ceiling_bytes"),
                "predicted_effective_bytes": observation.get("predicted_effective_bytes"),
                "retry_after_seconds": MEMORY_ADMISSION_BACKOFF_SECONDS,
                "expires_monotonic": now + MEMORY_ADMISSION_BACKOFF_SECONDS,
            }

    @staticmethod
    def request_marker(
        data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> tuple[Any, ...]:
        """Return a bounded process-local input marker without durable reads."""
        valuation = data.get("valuation_intelligence") or {}
        semantic_revision = data.get("asset_market_semantic_revision")
        if not semantic_revision:
            semantic_revision = asset_market_input_revision(
                valuation.get("semantic_generation"),
                valuation.get("input_manifest") or {},
            )
        return (
            VERSION, BUILD_NUMBER, MARKET_SCHEMA_VERSION, league_id,
            id(store), valuation.get("schema_version"), semantic_revision,
        )

    def _set_build_phase(self, phase: str) -> None:
        with self._lock:
            self._build_phase = phase

    @staticmethod
    def store_identity(store: HistoricalStore) -> str:
        """Return a private instance/durable-generation cache namespace."""
        payload = {
            "instance": id(store),
            "database_uuid": store.database_uuid(),
            "database_schema": DATABASE_MIGRATION_VERSION,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @classmethod
    def key(
        cls, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> tuple[str, str]:
        store_identity = cls.store_identity(store)
        payload = {
            "version": VERSION, "build": BUILD_NUMBER,
            "market_schema": MARKET_SCHEMA_VERSION, "league_id": league_id,
            "store_namespace": store_identity,
            "semantic_revision": cls.request_marker(
                data, state, store, league_id,
            )[-1],
            "valuation": (data.get("valuation_intelligence") or {}).get("schema_version"),
        }
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return key, store_identity

    @staticmethod
    def durable_generation(
        data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
        contract: dict[str, Any] | None = None,
    ) -> str:
        payload = contract or AssetMarketCache.artifact_contract(
            data, state, store, league_id,
        )
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def artifact_contract(
        data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
        *, semantic_metrics_observer: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        return {
            "version": VERSION, "build": BUILD_NUMBER,
            "market_schema": MARKET_SCHEMA_VERSION,
            "read_model_schema": MARKET_READ_MODEL_SCHEMA,
            "league_id": league_id,
            "database_identity_digest": _digest(store.database_uuid()),
            **AssetMarketCache.semantic_identities(
                data, state, metrics_observer=semantic_metrics_observer,
            ),
        }

    @staticmethod
    def semantic_identities(
        data: dict[str, Any], state: dict[str, Any],
        metrics_observer: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Reference implementation for exact subprocess equivalence tests."""
        started = time.perf_counter()
        identities = reference_identities(
            AssetMarketCache._semantic_records(data, state),
            (data.get("valuation_intelligence") or {}).get("schema_version"),
        )
        if metrics_observer is not None:
            metrics_observer({
                "execution": "in_process_reference",
                "asset_count": identities["asset_count"],
                "total_duration_ms": round((time.perf_counter() - started) * 1000, 3),
            })
        return identities

    @staticmethod
    def _semantic_records(
        data: dict[str, Any], state: dict[str, Any],
    ) -> Any:
        brain = brain_service(data)
        universe = ValuationUniverse.streaming(data, state)
        for sequence, asset in enumerate(universe.iter_assets()):
            brain_asset = brain.asset(asset["asset_id"])
            yield semantic_record(
                asset, brain_asset, _summary(asset, brain_asset), sequence,
            )

    @staticmethod
    def _expected_semantic_assets(data: dict[str, Any]) -> int:
        players = data.get("normalized_players") or data.get("players") or {}
        relevance = data.get("relevant_player_universe") or {}
        member_ids = relevance.get("member_ids")
        if isinstance(member_ids, list):
            allowed = {str(player_id) for player_id in member_ids}
            players = {
                player_id: row for player_id, row in players.items()
                if str(player_id) in allowed
            }
        return sum(isinstance(row, dict) for row in players.values()) + len(
            data.get("pick_ledger") or []
        )

    @staticmethod
    def _semantic_json(value: Any) -> bytes:
        def fallback(item: Any) -> Any:
            if isinstance(item, set):
                return sorted(item)
            return getattr(item, "value", str(item))

        return (json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=fallback,
        ) + "\n").encode("utf-8")

    def _isolated_semantic_identities(
        self, data: dict[str, Any], state: dict[str, Any],
        request_marker: tuple[Any, ...], league_id: str,
        storage_root: Path | None = None,
    ) -> dict[str, Any]:
        """Stream canonical records to one minimal spawned semantic worker."""
        snapshot = self._memory_observer()
        admission = memory_admission(
            snapshot, estimate=SEMANTIC_CHILD_MEMORY_ESTIMATE,
        )
        self._record_admission(
            league_id, "semantic_preparation", admission, snapshot, storage_root,
        )
        if not admission.get("admitted"):
            raise MarketMemoryBudgetError("semantic_preparation", admission)
        expected = self._expected_semantic_assets(data)
        request_generation = hashlib.sha256(json.dumps(
            request_marker, default=str, separators=(",", ":"),
        ).encode()).hexdigest()
        header = {
            "protocol": PROTOCOL_VERSION,
            "request_generation": request_generation,
            "application_version": VERSION,
            "application_build": BUILD_NUMBER,
            "market_schema": MARKET_SCHEMA_VERSION,
            "read_model_schema": MARKET_READ_MODEL_SCHEMA,
            "valuation_schema": (
                data.get("valuation_intelligence") or {}
            ).get("schema_version"),
            "league_identity": _digest(league_id),
            "expected_asset_count": expected,
        }
        root = Path(__file__).resolve().parents[3]
        child_environment = {
            name: os.environ[name] for name in ("PATH", "SYSTEMROOT", "WINDIR")
            if name in os.environ
        }
        child_environment.update({
            "PYTHONPATH": str(root),
            "PYTHONUNBUFFERED": "1",
        })
        started = time.perf_counter()
        parent_cpu_started = time.process_time()
        input_bytes = 0
        records = 0
        peak_child_rss = 0
        process: Any = None
        exit_status: int | None = None
        failure: str | None = None
        reaped = False
        try:
            process = self._semantic_process_factory(
                [sys.executable, "-m", "src.core.asset_market.semantic_worker"],
                cwd=root, env=child_environment, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            with self._lock:
                self.semantic_child_count += 1
            child = psutil.Process(process.pid)
            encoded = self._semantic_json(header)
            process.stdin.write(encoded)
            input_bytes += len(encoded)
            for record in self._semantic_records(data, state):
                encoded = self._semantic_json(record)
                process.stdin.write(encoded)
                input_bytes += len(encoded)
                records += 1
                if records % SEMANTIC_STREAM_FLUSH_RECORDS == 0:
                    process.stdin.flush()
                    try:
                        peak_child_rss = max(
                            peak_child_rss, int(child.memory_info().rss),
                        )
                    except (psutil.Error, OSError):
                        pass
            process.stdin.close()
            process.stdin = None
            elapsed = time.perf_counter() - started
            remaining = max(0.001, SEMANTIC_CHILD_TIMEOUT_SECONDS - elapsed)
            try:
                stdout, stderr = process.communicate(timeout=remaining)
            except subprocess.TimeoutExpired:
                failure = "timeout"
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate(timeout=2.0)
                raise SemanticWorkerError("Semantic preparation timed out.") from None
            exit_status = process.returncode
            reaped = True
            if exit_status != 0:
                failure = "nonzero_exit"
                raise SemanticWorkerError(
                    "Semantic preparation exited without a valid result."
                )
            try:
                output = json.loads(stdout.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                failure = "malformed_output"
                raise SemanticWorkerError(
                    "Semantic preparation returned malformed output."
                ) from None
            try:
                identities = self._validate_semantic_output(
                    output, request_generation, expected,
                    header["valuation_schema"], input_bytes,
                )
            except SemanticWorkerError:
                failure = "invalid_output_contract"
                raise
            metrics = {
                "execution": "spawned_subprocess",
                "worker_pid": process.pid,
                "request_generation": request_generation,
                "input_bytes": input_bytes,
                "output_bytes": len(stdout),
                "records": records,
                "child_duration_ms": (output.get("timing") or {}).get("duration_ms"),
                "parent_duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "parent_cpu_ms": round((time.process_time() - parent_cpu_started) * 1000, 3),
                "peak_child_rss_bytes": peak_child_rss or (
                    output.get("timing") or {}
                ).get("peak_rss_bytes"),
                "child_cpu_ms": (output.get("timing") or {}).get("cpu_ms"),
                "exit_status": exit_status,
                "failure": None,
                "reaped": reaped,
                "memory_admission": admission,
                "semantic_identities": {
                    name: identities[name] for name in (
                        "asset_universe_digest",
                        "brain_semantic_output_digest",
                        "ownership_dependency_digest",
                        "provider_evidence_digest",
                    )
                },
            }
            self._record_semantic_preparation(metrics)
            return identities
        except (BrokenPipeError, OSError) as exc:
            failure = failure or "spawn_or_pipe_failure"
            raise SemanticWorkerError(
                f"Semantic preparation failed: {type(exc).__name__}."
            ) from None
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2.0)
            if process is not None:
                reaped = process.poll() is not None
            if failure is not None:
                self._record_semantic_preparation({
                    "execution": "spawned_subprocess",
                    "worker_pid": getattr(process, "pid", None),
                    "request_generation": request_generation,
                    "input_bytes": input_bytes,
                    "output_bytes": 0,
                    "records": records,
                    "parent_duration_ms": round(
                        (time.perf_counter() - started) * 1000, 3,
                    ),
                    "parent_cpu_ms": round(
                        (time.process_time() - parent_cpu_started) * 1000, 3,
                    ),
                    "peak_child_rss_bytes": peak_child_rss,
                    "exit_status": (
                        process.poll() if process is not None else exit_status
                    ),
                    "failure": failure,
                    "reaped": reaped,
                    "memory_admission": admission,
                })

    @staticmethod
    def _validate_semantic_output(
        output: Any, request_generation: str, expected_assets: int,
        valuation_schema: Any, input_bytes: int,
    ) -> dict[str, Any]:
        if not isinstance(output, dict):
            raise SemanticWorkerError("Semantic preparation output is not an object.")
        if (
            output.get("protocol") != PROTOCOL_VERSION
            or output.get("status") != "ok"
            or output.get("request_generation") != request_generation
            or output.get("asset_count") != expected_assets
            or output.get("valuation_schema_version") != valuation_schema
        ):
            raise SemanticWorkerError("Semantic preparation output identity is invalid.")
        timing = output.get("timing")
        if (
            not isinstance(timing, dict)
            or timing.get("records") != expected_assets
            or timing.get("input_bytes") != input_bytes
        ):
            raise SemanticWorkerError("Semantic preparation output metrics are invalid.")
        digests = output.get("digests")
        names = {
            "asset_universe": "asset_universe_digest",
            "brain_semantic_output": "brain_semantic_output_digest",
            "ownership_dependency": "ownership_dependency_digest",
            "provider_evidence": "provider_evidence_digest",
        }
        if not isinstance(digests, dict) or any(
            not isinstance(digests.get(name), str)
            or _SHA256.fullmatch(digests[name]) is None for name in names
        ):
            raise SemanticWorkerError("Semantic preparation returned an invalid digest.")
        return {
            target: digests[source] for source, target in names.items()
        } | {
            "asset_count": expected_assets,
            "valuation_schema": valuation_schema,
        }

    @staticmethod
    def artifact_path(store: HistoricalStore, generation: str) -> Path:
        return store.path.with_name(f".{store.path.stem}.asset-market-{generation[:20]}.sqlite3")

    @staticmethod
    def artifact_manifest_path(
        store: HistoricalStore, league_id: str | None = None,
    ) -> Path:
        if league_id is None:
            legacy = store.path.with_name(
                f".{store.path.stem}.asset-market-manifest.json"
            )
            if legacy.exists():
                return legacy
            namespaced = sorted(store.path.parent.glob(
                f".{store.path.stem}.asset-market-manifest-*.json"
            ))
            if len(namespaced) == 1:
                return namespaced[0]
        suffix = "" if league_id is None else f"-{_digest(str(league_id))[:16]}"
        return store.path.with_name(
            f".{store.path.stem}.asset-market-manifest{suffix}.json"
        )

    @staticmethod
    def _artifact_checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as artifact:
            while chunk := artifact.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _publish_artifact_manifest(
        cls, store: HistoricalStore, artifact: Path, generation: str,
        league_id: str | None = None,
    ) -> None:
        manifest = cls.artifact_manifest_path(store, league_id)
        temporary = manifest.with_name(f".{manifest.name}.{os.getpid()}.tmp")
        payload = {
            "schema_version": "1.0",
            "generation": generation,
            "artifact": artifact.name,
            "size": artifact.stat().st_size,
            "sha256": cls._artifact_checksum(artifact),
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            temporary.write_text(
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with temporary.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, manifest)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def prune_stale_artifacts(
        cls, store: HistoricalStore, *, protected: tuple[Path, ...] = (),
    ) -> dict[str, Any]:
        """Delete only complete artifacts not selected by any league manifest."""
        directory = store.path.parent
        manifests = list(directory.glob(
            f".{store.path.stem}.asset-market-manifest*.json"
        ))
        active: set[Path] = {path.resolve() for path in protected}
        selected: dict[str, tuple[str, Path]] = {}
        for manifest in manifests:
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                name = str(payload.get("artifact") or "")
                candidate = directory / name
                if (
                    name == Path(name).name and candidate.is_file()
                    and candidate.stat().st_size == int(payload.get("size") or -1)
                    and cls._artifact_checksum(candidate) == payload.get("sha256")
                ):
                    metadata = MarketReadModel(candidate).metadata()
                    league = str(
                        (metadata.get("compatibility") or {}).get("league_id")
                        or metadata.get("league_id") or ""
                    )
                    published = str(payload.get("published_at") or "")
                    if league and (
                        league not in selected or published > selected[league][0]
                    ):
                        selected[league] = (published, candidate.resolve())
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
        active.update(item[1] for item in selected.values())
        removed = failures = stale_bytes = 0
        for candidate in directory.glob(
            f".{store.path.stem}.asset-market-*.sqlite3"
        ):
            if ".partial" in candidate.name or candidate.resolve() in active:
                continue
            try:
                metadata = MarketReadModel(candidate).metadata()
                if not metadata.get("complete"):
                    continue
                size = candidate.stat().st_size
                candidate.unlink()
                stale_bytes += size
                removed += 1
            except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError):
                failures += 1
        remaining = list(directory.glob(
            f".{store.path.stem}.asset-market-*.sqlite3"
        ))
        active_existing = [path for path in remaining if path.resolve() in active]
        stale_existing = [path for path in remaining if path.resolve() not in active]
        return {
            "removed": removed, "removed_bytes": stale_bytes,
            "failures": failures, "artifact_count": len(remaining),
            "artifact_bytes": sum(path.stat().st_size for path in remaining),
            "active_count": len(active_existing),
            "active_bytes": sum(path.stat().st_size for path in active_existing),
            "stale_count": len(stale_existing),
            "stale_bytes": sum(path.stat().st_size for path in stale_existing),
        }

    def cleanup_artifacts(
        self, store: HistoricalStore, *, protected: tuple[Path, ...] = (),
    ) -> dict[str, Any]:
        """Run bounded non-fatal cleanup and retain scalar diagnostics."""
        try:
            cleanup = self.prune_stale_artifacts(store, protected=protected)
            with self._lock:
                self.artifact_cleanup_count += int(cleanup["removed"])
                self.artifact_cleanup_failures += int(cleanup["failures"])
            return cleanup
        except Exception:
            with self._lock:
                self.artifact_cleanup_failures += 1
            return {
                "removed": 0, "removed_bytes": 0, "failures": 1,
                "artifact_count": 0, "artifact_bytes": 0,
                "active_count": 0, "active_bytes": 0,
                "stale_count": 0, "stale_bytes": 0,
            }

    @staticmethod
    def _artifact_candidates(
        store: HistoricalStore, league_id: str | None = None,
    ) -> list[Path]:
        pattern = f".{store.path.stem}.asset-market-*.sqlite3"
        discovered = sorted(
            path for path in store.path.parent.glob(pattern)
            if path.is_file() and ".partial" not in path.name
        )
        manifest = AssetMarketCache.artifact_manifest_path(store, league_id)
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            name = str(payload.get("artifact") or "")
            candidate = store.path.parent / name
            if (
                name == Path(name).name and candidate.is_file()
                and candidate in discovered
                and candidate.stat().st_size == int(payload.get("size") or -1)
                and AssetMarketCache._artifact_checksum(candidate)
                == payload.get("sha256")
            ):
                discovered.remove(candidate)
                discovered.append(candidate)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
        return discovered

    @classmethod
    def _discover_artifact(
        cls, store: HistoricalStore, generation: str,
        expected: dict[str, Any],
    ) -> tuple[Path | None, str]:
        """Inspect bounded manifests and select one compatible final artifact."""
        candidates = cls._artifact_candidates(store, str(expected.get("league_id") or ""))
        if not candidates:
            return None, "artifact_not_found"
        corrupt = incomplete = incompatible = False
        mismatch_reasons: list[str] = []
        compatible: list[Path] = []
        for path in candidates:
            try:
                metadata = MarketReadModel(path).metadata()
            except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError):
                corrupt = True
                continue
            if not bool(metadata.get("complete")):
                incomplete = True
                continue
            if metadata.get("schema_version") != MARKET_READ_MODEL_SCHEMA:
                incompatible = True
                mismatch_reasons.append("schema_incompatible")
                continue
            contract = metadata.get("compatibility") or {}
            if metadata.get("generation") == generation and contract == expected:
                compatible.append(path)
            else:
                incompatible = True
                if not isinstance(contract, dict) or not contract:
                    mismatch_reasons.append("schema_incompatible")
                    continue
                reason = "semantic_identity_changed"
                for field, code in (
                    ("database_identity_digest", "database_identity_changed"),
                    ("league_id", "league_identity_changed"),
                    ("asset_universe_digest", "asset_universe_changed"),
                    ("brain_semantic_output_digest", "brain_semantic_output_changed"),
                    ("ownership_dependency_digest", "ownership_dependency_changed"),
                    ("provider_evidence_digest", "provider_evidence_changed"),
                ):
                    if contract.get(field) != expected.get(field):
                        reason = code
                        break
                if any(
                    contract.get(field) != expected.get(field)
                    for field in (
                        "version", "build", "market_schema", "read_model_schema",
                        "valuation_schema",
                    )
                ):
                    reason = "schema_incompatible"
                mismatch_reasons.append(reason)
        if compatible:
            return compatible[-1], "compatible"
        if corrupt:
            return None, "artifact_corrupt"
        if incomplete:
            return None, "artifact_incomplete"
        if incompatible:
            return None, sorted(mismatch_reasons)[0]
        return None, "artifact_not_found"

    def _publish(
        self, market: AssetMarket, key: str, store_identity: str,
        request_marker: tuple[Any, ...] | None = None,
        epoch: int | None = None,
        *, artifact_loaded: bool = False,
    ) -> AssetMarket:
        health = market.health()
        prepared_health = {
            name: health[name] for name in (
                "application_version", "application_build",
                "market_schema_version", "league_id",
                "historical_dataset_version", "historical_dataset_version_scope",
                "market_generation",
                "brain_generation", "valuation_generation", "generated_at",
                "status", "counts", "duplicate_asset_ids",
                "build_duration_ms", "read_contract", "search_index",
                "memory_admission", "semantic_identity",
                "artifact_brain_semantic_digest",
            ) if name in health
        }
        with self._lock:
            if epoch is not None and epoch != self._epoch:
                raise _BuildDeferred("Asset Market generation was superseded.")
            previous = self._market
            self._market, self._key = market, key
            self._store_identity = store_identity
            self._request_marker = request_marker
            self._memory_backoff = None
            self.build_count += 1
            self.last_error = None
            self._refresh_state = "ready"
            self._scheduler_state = "ready"
            self._scheduler_skip_reason = None
            self._health_metadata = prepared_health
            if artifact_loaded:
                self.artifact_loads += 1
        if previous is not None and previous._artifact_path != market._artifact_path:
            try:
                previous._artifact_path.unlink(missing_ok=True)
            except OSError:
                pass
        self.cleanup_artifacts(
            market.store, protected=(market._artifact_path,),
        )
        # Other league generations share this durable store directory. They are
        # intentionally retained for lazy restoration and must not be removed by
        # publication from the currently active league cache.
        return market

    def _construct(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str, key: str,
        store_identity: str, generation: str, path: Path,
        contract: dict[str, Any],
        request_marker: tuple[Any, ...] | None = None,
        epoch: int | None = None,
        lifecycle_managed: bool = False,
    ) -> AssetMarket:
        with self._build_lock:
            with self._lock:
                if key == self._key and self._market is not None:
                    self.hits += 1
                    return self._market
            def construct() -> AssetMarket:
                with self._lock:
                    self.actual_constructions += 1
                market = AssetMarket(
                    data, state, store, league_id, generation=generation,
                    artifact_path=path, compatibility=contract,
                    admission_observer=lambda stage, decision, snapshot: self._record_admission(
                        league_id, stage, decision, snapshot, store.path.parent,
                    ),
                )
                return market

            if lifecycle_managed:
                market = construct()
            else:
                with lifecycle_coordinator.phase("asset_market_build") as phase:
                    market = construct()
                    phase.update({
                        "asset_count": len(market.assets),
                        "canonical_generation": market.generated_at,
                        "build_duration_ms": market.build_duration_ms,
                        "storage": "bounded_sqlite",
                    })
            if epoch is not None:
                self._set_build_phase("publishing")
            self._publish_artifact_manifest(store, path, generation, league_id)
            with self._lock:
                self.durable_publications += 1
            return self._publish(
                market, key, store_identity, request_marker, epoch,
            )

    def _prepare_generation(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
        request_marker: tuple[Any, ...], epoch: int,
        phase: dict[str, Any],
    ) -> None:
        key, store_identity = self.key(data, state, store, league_id)
        with self._lock:
            prepared = self._prepared_semantic_contract
            if prepared is not None and prepared[0] == request_marker:
                contract = dict(prepared[1])
                self._prepared_semantic_contract = None
            else:
                contract = None
        if contract is None:
            contract = {
                "version": VERSION, "build": BUILD_NUMBER,
                "market_schema": MARKET_SCHEMA_VERSION,
                "read_model_schema": MARKET_READ_MODEL_SCHEMA,
                "league_id": league_id,
                "database_identity_digest": _digest(store.database_uuid()),
                **self._isolated_semantic_identities(
                    data, state, request_marker, league_id, store.path.parent,
                ),
            }
        if (
            epoch != self._epoch
            or self.request_marker(data, state, store, league_id) != request_marker
        ):
            raise _BuildDeferred("Asset Market semantic generation was superseded.")
        generation = self.durable_generation(
            data, state, store, league_id, contract,
        )
        with self._lock:
            self._requested_generation = generation
        expected_path = self.artifact_path(store, generation)
        artifact, compatibility = self._discover_artifact(
            store, generation, contract,
        )
        path = artifact or expected_path
        with self._lock:
            self._artifact_compatibility = compatibility
        with self._lock:
            if epoch != self._epoch:
                raise _BuildDeferred("Asset Market generation was superseded.")
            if (
                self._market is not None
                and self._market.store is store
                and self._market.semantic_generation == generation
            ):
                self.hits += 1
                self.noop_rebuild_requests += 1
                self.construction_admission_skips += 1
                self._request_marker = request_marker
                self._requested_generation = generation
                self._artifact_compatibility = "compatible"
                self._refresh_state = "ready"
                self._build_phase = "ready"
                self._scheduler_state = "ready"
                self._scheduler_skip_reason = "semantic_generation_current"
                return
            if key == self._key and self._market is not None:
                self.hits += 1
                self._request_marker = request_marker
                self._refresh_state = "ready"
                self._build_phase = "ready"
                return
            self.semantic_rebuild_requests += 1
        if artifact is not None:
            self._set_build_phase("loading_artifact")
            market = AssetMarket(
                data, state, store, league_id, generation=generation,
                artifact_path=path, load_existing=True,
                compatibility=contract,
            )
            self._set_build_phase("publishing")
            self._publish(
                market, key, store_identity, request_marker, epoch,
                artifact_loaded=True,
            )
        else:
            self._set_build_phase("building")
            market = self._construct(
                data, state, store, league_id, key, store_identity,
                generation, path, contract, request_marker, epoch,
                lifecycle_managed=True,
            )
        phase.update({
                    "asset_count": len(market.assets),
                    "canonical_generation": market.generated_at,
                    "build_duration_ms": market.build_duration_ms,
                    "storage": "bounded_sqlite",
        })

    def _background_construct(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
        request_marker: tuple[Any, ...], epoch: int,
    ) -> None:
        try:
            self._set_build_phase("preparing_generation")
            with lifecycle_coordinator.phase("asset_market_build") as phase:
                self._prepare_generation(
                    data, state, store, league_id, request_marker, epoch, phase,
                )
            self._set_build_phase("ready")
        except _BuildDeferred:
            with self._lock:
                if epoch == self._epoch:
                    self._build_phase = "idle"
                    self._scheduler_state = "idle"
                    self._scheduler_skip_reason = "generation_superseded"
        except MarketMemoryBudgetError as exc:
            with self._lock:
                self.failed_constructions += 1
                self.last_error = str(exc)
                self._build_phase = "memory_backoff"
                self._refresh_state = "memory_backoff"
                self._scheduler_state = "blocked"
                self._scheduler_skip_reason = "memory_backoff"
            self._record_memory_backoff(request_marker, exc)
        except Exception as exc:
            with self._lock:
                self.failed_constructions += 1
                self.last_error = str(exc)
                self._build_phase = "failed"
                self._refresh_state = "failed"
                self._scheduler_state = "failed"
                self._scheduler_skip_reason = "build_failed"
        finally:
            lifecycle_coordinator.release_market_critical()
            with self._lock:
                if epoch == self._epoch:
                    if self._build_started_monotonic is not None:
                        self._build_duration_ms = round(
                            (self._clock() - self._build_started_monotonic) * 1000,
                            3,
                        )
                if self._build_thread is threading.current_thread():
                    self._building = False
                    self._build_thread = None
                    if epoch != self._epoch:
                        self._build_phase = "idle"

    def _start_background(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
        request_marker: tuple[Any, ...],
    ) -> bool:
        if self._memory_backoff_active(request_marker):
            with self._lock:
                self._scheduler_state = "blocked"
                self._scheduler_skip_reason = "memory_backoff"
            return False
        with self._lock:
            if self._build_thread is not None:
                self._scheduler_state = "building"
                self._scheduler_skip_reason = "single_flight_active"
                return False
            epoch = self._epoch
            self._building = True
            self._build_phase = "preparing_generation"
            self._build_started_at = datetime.now(timezone.utc).isoformat()
            self._build_started_monotonic = self._clock()
            self._build_duration_ms = None
            self._refresh_state = "refreshing"
            self.last_error = None
            self.attempted_constructions += 1
            self.rebuild_requests += 1
            self._scheduler_state = "queued"
            self._scheduler_skip_reason = None
            lifecycle_coordinator.reserve_market_critical(
                "Asset Market generation has no compatible published model."
                if self._market is None else
                "Asset Market semantic replacement is active."
            )
            self._build_thread = threading.Thread(
                target=self._background_construct,
                args=(data, state, store, league_id, request_marker, epoch),
                name="dtos-market-builder", daemon=True,
            )
            try:
                self._build_thread.start()
            except BaseException:
                self._build_thread = None
                self._building = False
                lifecycle_coordinator.release_market_critical()
                raise
            self._scheduler_state = "building"
            return True

    def begin_warming_guard(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
        *, start_background: bool = True,
    ) -> bool:
        """Start or observe generation using only bounded in-memory state."""
        invoked_at = datetime.now(timezone.utc).isoformat()
        allowed = lifecycle_coordinator.market_build_allowed()
        request_marker = self.request_marker(data, state, store, league_id)
        with self._lock:
            self._scheduler_last_invoked = invoked_at
        if self._memory_backoff_active(request_marker):
            with self._lock:
                self._scheduler_state = "blocked"
                self._scheduler_skip_reason = "memory_backoff"
            return True
        with self._lock:
            market = self._market
            current = (
                market is not None and market.store is store
                and request_marker == self._request_marker
            )
            if current:
                self._scheduler_state = "ready"
                self._scheduler_skip_reason = "current_generation"
                return False
            if self._refresh_state == "failed" or self._build_phase == "failed":
                self._scheduler_state = "failed"
                self._scheduler_skip_reason = "build_failed"
                return False
            active = self._build_thread is not None
        if active:
            with self._lock:
                self._scheduler_state = "building"
                self._scheduler_skip_reason = "single_flight_active"
            return True
        if not allowed:
            with self._lock:
                self._scheduler_state = "blocked"
                self._scheduler_skip_reason = "lifecycle_prerequisite"
            return market is None or market.store is not store
        if start_background:
            self._start_background(data, state, store, league_id, request_marker)
        return True

    def reconcile(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> bool:
        """Enforce the model-less eligible-state single-flight invariant."""
        if not data:
            with self._lock:
                self._scheduler_last_invoked = datetime.now(timezone.utc).isoformat()
                self._scheduler_state = "blocked"
                self._scheduler_skip_reason = "canonical_data_unavailable"
            return False
        return self.begin_warming_guard(data, state, store, league_id)

    def restore_compatible(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str,
    ) -> bool:
        """Synchronously restore one compatible durable artifact without building."""
        if not data:
            return False
        with self._lock:
            self._artifact_compatibility = "discovery_pending"
        try:
            request_marker = self.request_marker(data, state, store, league_id)
            key, store_identity = self.key(data, state, store, league_id)
            contract = {
                "version": VERSION, "build": BUILD_NUMBER,
                "market_schema": MARKET_SCHEMA_VERSION,
                "read_model_schema": MARKET_READ_MODEL_SCHEMA,
                "league_id": league_id,
                "database_identity_digest": _digest(store.database_uuid()),
                **self._isolated_semantic_identities(
                    data, state, request_marker, league_id, store.path.parent,
                ),
            }
            generation = self.durable_generation(
                data, state, store, league_id, contract,
            )
            candidates = self._artifact_candidates(store, league_id)
            with self._lock:
                self.artifact_candidates = len(candidates)
                self._requested_generation = generation
            artifact, compatibility = self._discover_artifact(
                store, generation, contract,
            )
            with self._lock:
                self._artifact_compatibility = compatibility
            if artifact is None:
                with self._lock:
                    self._prepared_semantic_contract = (
                        request_marker, dict(contract),
                    )
                return False
            market = AssetMarket(
                data, state, store, league_id, generation=generation,
                artifact_path=artifact, load_existing=True,
                compatibility=contract,
            )
            self._publish_artifact_manifest(store, artifact, generation, league_id)
            self._publish(
                market, key, store_identity, request_marker,
                artifact_loaded=True,
            )
            return True
        except Exception:
            with self._lock:
                self.artifact_restore_failures += 1
                self._artifact_compatibility = "artifact_unreadable"
            return False

    def get(
        self, data: dict[str, Any], state: dict[str, Any],
        store: HistoricalStore, league_id: str, *, background: bool = False,
    ) -> AssetMarket:
        if not lifecycle_coordinator.market_build_allowed():
            with self._lock:
                if self._market is not None and self._market.store is store:
                    self.hits += 1
                    self.last_miss_reason = "heavy_phase_last_valid"
                    return self._market
            raise MarketWarmingError(
                "Asset Market is warming while canonical data maintenance completes."
            )
        request_marker = self.request_marker(data, state, store, league_id)
        if background:
            with self._lock:
                market = self._market
                if (
                    market is not None and market.store is store
                    and request_marker == self._request_marker
                ):
                    self.hits += 1
                    return market
                self.last_miss_reason = (
                    "cold_start" if market is None
                    else "canonical_market_inputs_changed"
                )
            self._start_background(
                data, state, store, league_id, request_marker,
            )
            with self._lock:
                if self._market is not None and self._market.store is store:
                    # Retain the complete last-valid model for atomic fallback,
                    # but never serialize it while a CPU-heavy replacement is
                    # active. The bounded warming contract avoids durable reads
                    # and request-thread contention until publication.
                    raise MarketWarmingError(
                        "Asset Market generation is building safely in the "
                        "background; retry shortly."
                    )
            raise MarketWarmingError(
                "Asset Market generation is building safely in the background; retry shortly."
            )
        try:
            key, store_identity = self.key(data, state, store, league_id)
        except Exception:
            with self._lock:
                if self._market is not None and self._market.store is store:
                    self._key = None
                    self._store_identity = None
                    self._market = None
            raise
        contract = {
            "version": VERSION, "build": BUILD_NUMBER,
            "market_schema": MARKET_SCHEMA_VERSION,
            "read_model_schema": MARKET_READ_MODEL_SCHEMA,
            "league_id": league_id,
            "database_identity_digest": _digest(store.database_uuid()),
            **self._isolated_semantic_identities(
                data, state, request_marker, league_id, store.path.parent,
            ),
        }
        generation = self.durable_generation(
            data, state, store, league_id, contract,
        )
        expected_path = self.artifact_path(store, generation)
        artifact, compatibility = self._discover_artifact(
            store, generation, contract,
        )
        path = artifact or expected_path
        with self._lock:
            self._artifact_compatibility = compatibility
        if key == self._key and self._market is not None:
            with self._lock:
                self.hits += 1
                return self._market
        with self._lock:
            if key == self._key and self._market is not None:
                self.hits += 1
                return self._market
            self.last_miss_reason = (
                "cold_start" if self._market is None
                else "canonical_market_inputs_changed"
            )
        if artifact is not None:
            market = AssetMarket(
                data, state, store, league_id, generation=generation,
                artifact_path=path, load_existing=True,
                compatibility=contract,
            )
            return self._publish(
                market, key, store_identity, request_marker,
                artifact_loaded=True,
            )
        try:
            return self._construct(
                data, state, store, league_id, key, store_identity,
                generation, path, contract, request_marker,
            )
        except (MarketMemoryBudgetError, _BuildDeferred) as exc:
            if self._market is not None and self._store_identity == store_identity:
                return self._market
            raise MarketWarmingError(str(exc)) from exc
        except Exception as exc:
            self.last_error = str(exc)
            if self._market is not None and self._store_identity == store_identity:
                return self._market
            raise

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            market = self._market
            return {
                "status": "ready" if market is not None else "warming",
                "build_count": self.build_count, "cache_hits": self.hits,
                "attempted_constructions": self.attempted_constructions,
                "market_rebuild_requests": self.rebuild_requests,
                "market_rebuild_requests_semantic": self.semantic_rebuild_requests,
                "market_rebuild_requests_noop": self.noop_rebuild_requests,
                "market_construction_admission_skips": self.construction_admission_skips,
                "market_actual_constructions": self.actual_constructions,
                "semantic_child_count": self.semantic_child_count,
                "failed_constructions": self.failed_constructions,
                "last_error": self.last_error,
                "last_miss_reason": self.last_miss_reason,
                "last_valid_model": market is not None,
                "market_generation": market.generated_at if market else None,
                "brain_generation": market.brain_generation if market else None,
                "historical_dataset_version": market.dataset_version if market else None,
                "historical_dataset_version_scope": (
                    self._health_metadata.get("historical_dataset_version_scope")
                    if market else None
                ),
                "asset_count": len(market.assets) if market else 0,
                "build_duration_ms": market.build_duration_ms if market else None,
                "last_successful_build": market.generated_at if market else None,
                "build_active": self._building,
                "build_phase": self._build_phase,
                "build_started_at": self._build_started_at,
                "background_duration_ms": self._build_duration_ms,
                "refresh_state": self._refresh_state,
                "artifact_compatibility": self._artifact_compatibility,
                "artifact_candidates": self.artifact_candidates,
                "artifact_loads": self.artifact_loads,
                "artifact_restore_failures": self.artifact_restore_failures,
                "durable_publications": self.durable_publications,
                "artifact_cleanup_count": self.artifact_cleanup_count,
                "artifact_cleanup_failures": self.artifact_cleanup_failures,
                "diagnostic_write_failures": self.diagnostic_write_failures,
                "requested_generation": self._requested_generation,
                "memory_admission_backoff": (
                    {
                        key: value for key, value in self._memory_backoff.items()
                        if key not in {
                            "request_marker", "expires_monotonic",
                            "retry_after_seconds",
                        }
                    } | {
                        "active": True,
                        "retry_after_seconds": max(
                            0.0,
                            round(
                                float(self._memory_backoff["expires_monotonic"])
                                - float(self._clock()),
                                3,
                            ),
                        ),
                    } if self._memory_backoff else None
                ),
                "served_generation": market.generated_at if market else None,
                "build_queued": bool(
                    self._build_thread is not None and not self._build_thread.is_alive()
                ),
                "scheduler_state": self._scheduler_state,
                "scheduler_last_invoked": self._scheduler_last_invoked,
                "scheduler_skip_reason": self._scheduler_skip_reason,
                "semantic_preparation": dict(self._semantic_preparation),
                "lifecycle": lifecycle_coordinator.snapshot(),
            }

    def current(self) -> AssetMarket | None:
        """Return the retained immutable model without discovery or construction."""
        with self._lock:
            return self._market

    def health(self) -> dict[str, Any]:
        """Return bounded retained build metadata without hydrating a model."""
        with self._lock:
            metadata = dict(self._health_metadata)
        cache = self.metrics()
        refreshing = bool(cache["build_active"])
        return {
            **metadata,
            "status": "warming" if refreshing else metadata.get("status") or cache["status"],
            "availability": (
                "last_valid_refreshing" if refreshing and cache["last_valid_model"]
                else "available" if cache["last_valid_model"] else "warming"
            ),
            "counts": dict(metadata.get("counts") or {}),
            "duplicate_asset_ids": int(metadata.get("duplicate_asset_ids") or 0),
            "cache": cache,
        }

    def clear(self) -> None:
        with self._lock:
            self._epoch += 1
            self._key = None
            self._store_identity = None
            self._market = None
            self._health_metadata = {}
            self._request_marker = None
            self._requested_generation = None
            self._memory_backoff = None
            self._semantic_preparation = {}
            self._prepared_semantic_contract = None
            active = self._build_thread is not None
            self._building = active
            self._build_phase = "superseded" if active else "idle"
            self._build_started_at = None
            self._build_started_monotonic = None
            self._build_duration_ms = None
            self._refresh_state = "idle"
            self._scheduler_state = "idle"
            self._scheduler_last_invoked = None
            self._scheduler_skip_reason = None

    def wait_for_background(self, timeout: float = 5.0) -> bool:
        """Wait for the tracked worker without acquiring any durable state."""
        with self._lock:
            thread = self._build_thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()


asset_market_cache = AssetMarketCache()


def asset_market(
    data: dict[str, Any], state: dict[str, Any], store: HistoricalStore,
    league_id: str,
) -> AssetMarket:
    return asset_market_cache.get(data, state, store, league_id, background=True)
