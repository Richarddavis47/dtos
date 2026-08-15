"""Canonical, deterministic read model connecting all historical DTOS assets."""
from __future__ import annotations

import hashlib
import copy
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from collections import OrderedDict

from src.core.historical_memory.models import (
    HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
    HISTORICAL_SCHEMA_VERSION,
    IMPORTER_VERSION,
    PLAYER_HISTORY_SCHEMA_VERSION,
    HistoricalAssetEvent,
    OwnershipInterval,
    PlayerSeasonSummary,
)
from src.core.history_context.store import CanonicalHistoryStore as HistoricalStore


COMPLETED_STATUSES = {"complete", "completed"}
FAILED_STATUSES = {"failed", "failure"}
PLAYER_DOSSIER_CACHE_LIMIT = 128


def canonical_player_id(sleeper_player_id: str) -> str:
    """Return a stable ID without guessing identity or display metadata."""
    return f"DTOS-P-{sleeper_player_id}"


def canonical_pick_id(season: int | str, round_number: int | str, original_roster_id: int | str) -> str:
    return f"PICK-{season}-R{round_number}-ORIG{original_roster_id}"


def canonical_transaction_id(source_league_id: str, transaction_id: str) -> str:
    return f"TX-{source_league_id}-{transaction_id}"


def canonical_trade_id(source_league_id: str, transaction_id: str) -> str:
    return f"TRADE-{source_league_id}-{transaction_id}"


def canonical_event_id(*parts: object) -> str:
    source = "|".join(str(part) for part in parts)
    return "EVENT-" + hashlib.sha256(source.encode()).hexdigest()[:24].upper()


def franchise_id(root_league_id: str, roster_id: object | None) -> str | None:
    if roster_id in (None, ""):
        return None
    return f"{root_league_id}:franchise:{roster_id}"


class HistoricalAssetGraph:
    """Versioned read model built only from immutable historical evidence."""

    def __init__(
        self,
        store: HistoricalStore,
        league_id: str,
        current_data: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.league_id = league_id
        self.current_data = current_data or {}
        self._identity_by_provider_id: dict[str, dict[str, Any] | None] = {}
        self._identity_positions: dict[str, str] | None = None
        self._records_cache: dict[str, list[dict[str, Any]]] = {}
        self._index_lock = threading.RLock()
        self._events_all: list[dict[str, Any]] | None = None
        self._events_by_asset: dict[str, list[dict[str, Any]]] = {}
        self._events_by_parent: dict[str, list[dict[str, Any]]] = {}
        self._player_rows_by_id: dict[str, list[dict[str, Any]]] = {}
        self._player_totals_by_season: dict[int, dict[str, float]] | None = None
        self._directory_ids: dict[str, list[str]] | None = None
        self._trade_dossiers_cache: list[dict[str, Any]] | None = None
        self._trade_by_id: dict[str, dict[str, Any]] = {}
        self._transaction_archive_cache: list[dict[str, Any]] | None = None
        self._coverage_cache: dict[str, Any] | None = None
        self._player_dossiers: OrderedDict[tuple[str, str, str, str], dict[str, Any]] = OrderedDict()
        self._player_dossier_build_count = 0
        self._player_dossier_hits = 0
        self._cache_metadata: dict[str, Any] = {}
        self._query_count = 0
        self._records_hydrated = 0
        self._last_query_duration_ms: float | None = None
        self._approximate_size_bytes = 0

    @property
    def index_event_count(self) -> int:
        if self._events_all is not None:
            return len(self._events_all)
        return sum(len(events) for events in self._events_by_asset.values())

    @property
    def index_asset_count(self) -> int:
        return sum(len(values) for values in (self._directory_ids or {}).values())

    @property
    def approximate_size_bytes(self) -> int:
        return self._approximate_size_bytes

    def set_cache_metadata(self, metadata: dict[str, Any]) -> None:
        self._cache_metadata = metadata

    def prepare_indexes(self) -> None:
        """Build immutable lookup structures exactly once for this graph."""
        self._ensure_event_indexes()
        self._ensure_directory_ids()
        self._approximate_size_bytes = self._estimate_index_size()

    def query_metrics(self) -> dict[str, Any]:
        return {
            **self._cache_metadata,
            "asset_count": self.index_asset_count,
            "event_count": self.index_event_count,
            "approximate_model_bytes": self.approximate_size_bytes,
            "query_count": self._query_count,
            "query_duration_ms": self._last_query_duration_ms,
            "records_hydrated": self._records_hydrated,
            "player_summary_build_count": self._player_dossier_build_count,
            "player_summary_cache_hits": self._player_dossier_hits,
            "player_summary_cache_entries": len(self._player_dossiers),
            "player_summary_cache_limit": PLAYER_DOSSIER_CACHE_LIMIT,
        }

    def _record_query(self, started: float, hydrated: int) -> None:
        self._query_count += 1
        self._records_hydrated = hydrated
        self._last_query_duration_ms = round(
            (time.perf_counter() - started) * 1000, 3,
        )

    def _estimate_index_size(self) -> int:
        """Return a bounded shallow estimate without walking every payload."""
        containers = (
            self._records_cache, self._events_all, self._events_by_asset,
            self._events_by_parent, self._player_rows_by_id,
            self._player_totals_by_season, self._directory_ids,
        )
        total = sum(sys.getsizeof(value) for value in containers)
        events = self._events_all or []
        if events:
            total += len(events) * sys.getsizeof(events[0])
        total += sum(
            len(rows) * 8
            for index in (
                self._events_by_asset, self._events_by_parent,
                self._player_rows_by_id,
            )
            for rows in index.values()
        )
        return total

    def _records(self, entity_type: str) -> list[dict[str, Any]]:
        if entity_type not in self._records_cache:
            _, rows = self.store.records(
                self.league_id, entity_type, limit=100_000,
            )
            self._records_cache[entity_type] = rows
        return self._records_cache[entity_type]

    def player_identity(self, player_id: str) -> dict[str, Any]:
        raw_id = player_id.removeprefix("DTOS-P-")
        if raw_id not in self._identity_by_provider_id:
            self._identity_by_provider_id[raw_id] = self.store.identity_for_provider_id(raw_id)
        identity = self._identity_by_provider_id[raw_id]
        current = (self.current_data.get("players") or {}).get(raw_id) or {}
        display = (
            (identity or {}).get("display_name")
            or current.get("full_name")
            or " ".join(
                value for value in (current.get("first_name"), current.get("last_name"))
                if value
            )
            or f"Unresolved Sleeper player {raw_id}"
        )
        resolved = bool(identity and int(identity.get("confidence") or 0) >= 70) or bool(current)
        return {
            "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            "canonical_id": canonical_player_id(raw_id),
            "asset_type": "player",
            "sleeper_player_id": raw_id,
            "display_label": display,
            "resolution_status": "resolved" if resolved else "unresolved",
            "aliases": {
                "Sleeper": raw_id,
                **({"DTOS legacy": identity["dtos_player_id"]} if identity else {}),
            },
            "metadata": current or ((identity or {}).get("metadata") or {}),
            "provenance": ["Sleeper player ID", "Historical Memory player_identity"],
            "missing_reasons": [] if resolved else [
                "No verified current metadata or approved identity alias is available."
            ],
        }

    def _ensure_event_indexes(self) -> None:
        if self._events_all is not None:
            return
        with self._index_lock:
            if self._events_all is not None:
                return
            if self.store.import_active(self.league_id):
                raise RuntimeError(
                    "Global Historical Asset Graph hydration is unavailable while "
                    "a historical import is active; use an indexed read path."
                )
            self._build_event_indexes()
            self._approximate_size_bytes = self._estimate_index_size()

    def _build_event_indexes(self) -> None:
        events: list[HistoricalAssetEvent] = []
        for row in self._records("draft_pick"):
            payload = row["payload"]
            sleeper_player_id = str(payload.get("player_id") or row.get("player_id") or "")
            if not sleeper_player_id:
                continue
            pick = canonical_pick_id(
                row["season"], payload.get("round") or "UNKNOWN",
                payload.get("roster_id") or payload.get("original_franchise") or "UNKNOWN",
            )
            events.append(self._event(
                row, canonical_player_id(sleeper_player_id), "player",
                "startup_draft_selection" if self._draft_type(payload.get("draft_id")) == "startup" else "rookie_draft_selection",
                "completed", parent_id=pick,
                to_roster=payload.get("picked_by") or payload.get("roster_id"),
                original_roster=payload.get("roster_id") or payload.get("original_franchise"),
            ))
            events.append(self._event(
                row, pick, "pick", "pick_exercise", "completed",
                parent_id=str(payload.get("draft_id") or "") or None,
                to_roster=payload.get("picked_by") or payload.get("roster_id"),
                original_roster=payload.get("roster_id") or payload.get("original_franchise"),
                suffix=sleeper_player_id,
            ))
        for row in (*self._records("transaction"), *self._records("trade")):
            payload = row["payload"]
            status = str(payload.get("status") or "unknown").casefold()
            transaction_type = str(payload.get("type") or row["entity_type"]).casefold()
            parent = (
                canonical_trade_id(self._source_league(row), row["source_record_id"])
                if transaction_type == "trade"
                else canonical_transaction_id(self._source_league(row), row["source_record_id"])
            )
            for player, roster in (payload.get("adds") or {}).items():
                events.append(self._event(
                    row, canonical_player_id(str(player)), "player",
                    self._movement_type(transaction_type, "addition"), status,
                    parent_id=parent, to_roster=roster, suffix=f"add:{player}:{roster}",
                ))
            for player, roster in (payload.get("drops") or {}).items():
                events.append(self._event(
                    row, canonical_player_id(str(player)), "player",
                    self._movement_type(transaction_type, "drop"), status,
                    parent_id=parent, from_roster=roster, suffix=f"drop:{player}:{roster}",
                ))
            for index, pick_payload in enumerate(payload.get("draft_picks") or []):
                pick = canonical_pick_id(
                    pick_payload.get("season") or "UNKNOWN",
                    pick_payload.get("round") or "UNKNOWN",
                    pick_payload.get("roster_id") or "UNKNOWN",
                )
                events.append(self._event(
                    row, pick, "pick", "pick_transfer", status,
                    parent_id=parent,
                    from_roster=pick_payload.get("previous_owner_id"),
                    to_roster=pick_payload.get("owner_id"),
                    original_roster=pick_payload.get("roster_id"), suffix=f"pick:{index}",
                ))
        for row in self._records("pick_snapshot"):
            payload = row["payload"]
            pick = canonical_pick_id(
                payload.get("season") or row["season"],
                payload.get("round") or "UNKNOWN",
                payload.get("roster_id") or payload.get("original_roster_id") or "UNKNOWN",
            )
            events.append(self._event(
                row, pick, "pick", "pick_snapshot", "completed",
                from_roster=payload.get("previous_owner_id"),
                to_roster=payload.get("owner_id") or payload.get("current_owner_id"),
                original_roster=payload.get("roster_id") or payload.get("original_roster_id"),
            ))
        for row in self._records("weekly_roster"):
            payload = row["payload"]
            for player in dict.fromkeys([*(payload.get("starters") or []), *(payload.get("bench") or [])]):
                events.append(self._event(
                    row, canonical_player_id(str(player)), "player", "roster_snapshot",
                    "completed", to_franchise=row.get("franchise_id"),
                    suffix=f"snapshot:{player}",
                ))
        result = [asdict(event) for event in events]
        result.sort(key=lambda item: (
            item["season"], item["week"] or 0, item["occurred_at"] or item["observed_at"],
            0 if item.get("from_franchise_id") and not item.get("to_franchise_id") else 1,
            item["event_id"],
        ))
        by_asset: dict[str, list[dict[str, Any]]] = {}
        by_parent: dict[str, list[dict[str, Any]]] = {}
        for event in result:
            by_asset.setdefault(event["asset_id"], []).append(event)
            if event.get("parent_id"):
                by_parent.setdefault(str(event["parent_id"]), []).append(event)
        self._events_by_asset = by_asset
        self._events_by_parent = by_parent
        self._events_all = result

    def events(self, *, asset_id: str | None = None) -> list[dict[str, Any]]:
        started = time.perf_counter()
        if asset_id is not None and asset_id not in self._events_by_asset:
            targeted = HistoricalAssetGraph(self.store, self.league_id, self.current_data)
            targeted._records_cache.update(
                self.store.asset_event_records(self.league_id, asset_id),
            )
            targeted._build_event_indexes()
            self._events_by_asset[asset_id] = list(
                targeted._events_by_asset.get(asset_id, []),
            )
        elif asset_id is None:
            self._ensure_event_indexes()
        rows = (
            self._events_all or []
            if asset_id is None
            else self._events_by_asset.get(asset_id, [])
        )
        result = list(rows)
        self._record_query(started, len(result))
        return result

    def ownership_intervals(self, asset_id: str) -> list[dict[str, Any]]:
        events = self.events(asset_id=asset_id)
        completed = [
            event for event in events
            if event["event_status"].casefold() in COMPLETED_STATUSES
            and event["event_type"] != "roster_snapshot"
        ]
        snapshots = [event for event in events if event["event_type"] == "roster_snapshot"]
        intervals: list[OwnershipInterval] = []
        active: dict[str, Any] | None = None
        for event in completed:
            outgoing = event.get("from_franchise_id")
            incoming = event.get("to_franchise_id")
            if outgoing and active and active["franchise_id"] == outgoing:
                intervals.append(self._close_interval(active, event))
                active = None
            if incoming:
                if active and active["franchise_id"] != incoming:
                    intervals.append(self._close_interval(active, event, "warning_unobserved_transition"))
                active = {
                    "asset_id": asset_id, "franchise_id": incoming,
                    "event": event, "sources": [event["event_id"]],
                }
        snapshot_owners = [event["to_franchise_id"] for event in snapshots if event.get("to_franchise_id")]
        latest_snapshot_owner = snapshot_owners[-1] if snapshot_owners else None
        if active:
            status = "verified" if latest_snapshot_owner in {None, active["franchise_id"]} else "warning_snapshot_disagreement"
            intervals.append(OwnershipInterval(
                asset_id=asset_id, franchise_id=active["franchise_id"],
                acquisition_event_id=active["event"]["event_id"],
                acquired_at=active["event"]["occurred_at"], disposition_event_id=None,
                disposed_at=None, duration_days=None, season=active["event"]["season"],
                season_end_owner=True, source_event_ids=tuple(active["sources"]),
                reconciliation_status=status,
            ))
        elif latest_snapshot_owner:
            snapshot = snapshots[-1]
            intervals.append(OwnershipInterval(
                asset_id=asset_id, franchise_id=latest_snapshot_owner,
                acquisition_event_id=snapshot["event_id"], acquired_at=snapshot["occurred_at"],
                disposition_event_id=None, disposed_at=None, duration_days=None,
                season=snapshot["season"], season_end_owner=True,
                source_event_ids=(snapshot["event_id"],),
                reconciliation_status="snapshot_only",
            ))
        return [asdict(interval) for interval in intervals]

    def player_season_summaries(self, player_id: str) -> list[dict[str, Any]]:
        raw_id = player_id.removeprefix("DTOS-P-")
        self._ensure_player_indexes(raw_id)
        rows = list((self._player_rows_by_id or {}).get(raw_id, []))
        league_settings = {
            int(row["season"]): row["payload"].get("scoring_settings") or {}
            for row in self._records("league_season")
        }
        by_season: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            by_season.setdefault(int(row["season"]), []).append(row)
        summaries = []
        current_year = datetime.now(timezone.utc).year
        for season, season_rows in sorted(by_season.items()):
            observed = [row for row in season_rows if row["payload"].get("fantasy_points") is not None]
            points = round(sum(float(row["payload"]["fantasy_points"]) for row in observed), 2) if observed else None
            weeks = {int(row["week"]) for row in season_rows if row.get("week")}
            expected = set(range(1, 19))
            player_totals = (self._player_totals_by_season or {}).get(season, {})
            ordered = sorted(player_totals.items(), key=lambda item: (-item[1], item[0]))
            rank = next((index for index, item in enumerate(ordered, 1) if item[0] == raw_id), None)
            franchises = tuple(dict.fromkeys(str(row["franchise_id"]) for row in sorted(season_rows, key=lambda item: item.get("week") or 0) if row.get("franchise_id")))
            summary = PlayerSeasonSummary(
                player_id=canonical_player_id(raw_id), season=season,
                scoring_settings_version=self._settings_version(league_settings.get(season, {})),
                games_observed=len(observed),
                starts=sum(bool(row["payload"].get("starter")) for row in season_rows),
                bench_appearances=sum(not bool(row["payload"].get("starter")) for row in season_rows),
                fantasy_points=points,
                points_per_game=round(points / len(observed), 2) if points is not None and observed else None,
                overall_rank=rank, positional_rank=self._positional_rank(raw_id, player_totals),
                starter_points=round(sum(float(row["payload"].get("fantasy_points") or 0) for row in observed if row["payload"].get("starter")), 2) if observed else None,
                end_of_season_franchise_id=franchises[-1] if franchises else None,
                franchise_ids=franchises,
                completeness_percentage=round(100 * len(weeks) / 18, 1),
                missing_weeks=tuple(sorted(expected - weeks)),
                source_record_ids=tuple(sorted(str(row["source_record_id"]) for row in season_rows)),
                status="in_progress" if season >= current_year else "complete" if len(weeks) >= 14 else "incomplete",
            )
            summaries.append(asdict(summary))
        return summaries

    def _ensure_player_indexes(self, player_id: str) -> None:
        with self._index_lock:
            if self._player_totals_by_season is None:
                self._player_totals_by_season = self.store.player_week_totals(
                    self.league_id,
                )
            if player_id not in self._player_rows_by_id:
                _, rows = self.store.records(
                    self.league_id, "player_week", player_id=player_id,
                    limit=100_000,
                )
                rows.sort(key=lambda row: (
                    int(row["season"]), row.get("week") or 0,
                    row["source_record_id"],
                ))
                self._player_rows_by_id[player_id] = rows
            self._approximate_size_bytes = self._estimate_index_size()

    def player_dossier(self, player_id: str) -> dict[str, Any]:
        canonical_id = canonical_player_id(player_id.removeprefix("DTOS-P-"))
        cache_key = (
            self.league_id,
            str(self._cache_metadata.get("dataset_version") or "unversioned"),
            HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            canonical_id,
        )
        with self._index_lock:
            cached = self._player_dossiers.get(cache_key)
            if cached is not None:
                self._player_dossier_hits += 1
                self._player_dossiers.move_to_end(cache_key)
                return copy.deepcopy(cached)
            dossier = self._build_player_dossier(player_id, canonical_id)
            self._player_dossiers[cache_key] = dossier
            self._player_dossiers.move_to_end(cache_key)
            while len(self._player_dossiers) > PLAYER_DOSSIER_CACHE_LIMIT:
                self._player_dossiers.popitem(last=False)
            self._player_dossier_build_count += 1
            return copy.deepcopy(dossier)

    def _build_player_dossier(
        self, player_id: str, canonical_id: str,
    ) -> dict[str, Any]:
        events = self.events(asset_id=canonical_id)
        draft_events = [event for event in events if "draft_selection" in event["event_type"]]
        origin = draft_events[0] if draft_events else None
        return {
            "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            "identity": self.player_identity(player_id),
            "league_origin": origin or {
                "event_type": "waiver_or_free_agency_or_unavailable",
                "missing_reasons": ["No verified draft selection exists in imported Sleeper history."],
            },
            "season_summaries": self.player_season_summaries(player_id),
            "ownership_timeline": events,
            "ownership_intervals": self.ownership_intervals(canonical_id),
            "trades": self.player_trades(player_id),
            "waiver_and_free_agent_history": [
                event for event in events
                if event["event_type"] in {
                    "waiver_addition", "waiver_drop", "free_agent_addition",
                    "free_agent_drop", "commissioner_addition", "commissioner_drop",
                }
            ],
            "limitations": [
                "Historical value at event remains unavailable without a timestamped valuation snapshot.",
                "Missing Sleeper observations are not converted to zero.",
            ],
        }

    def player_trades(self, player_id: str) -> list[dict[str, Any]]:
        canonical_id = canonical_player_id(player_id.removeprefix("DTOS-P-"))
        transaction_ids = {
            event["source_record_id"] for event in self.events(asset_id=canonical_id)
            if event["event_type"] == "trade" and event.get("parent_id")
        }
        dossiers = [self.trade_dossier(transaction_id) for transaction_id in transaction_ids]
        return sorted(
            (dossier for dossier in dossiers if dossier is not None),
            key=lambda item: (
                item["season"], item["week"] or 0, item["occurred_at"],
                item["trade_id"],
            ),
            reverse=True,
        )

    def pick_dossier(self, pick_id: str) -> dict[str, Any] | None:
        events = self.events(asset_id=pick_id)
        if not events and not pick_id.startswith("PICK-"):
            return None
        parts = self._pick_parts(pick_id)
        exercise = next((event for event in events if event["event_type"] == "pick_exercise"), None)
        selected_player = None
        if exercise:
            candidates = self.store.asset_event_records(
                self.league_id, pick_id,
            )["draft_pick"]
            row = next((row for row in candidates if canonical_event_id(
                self.league_id, row["entity_type"], row["season"], row.get("week") or "",
                row["source_record_id"], str(row.get("player_id") or ""),
            ) == exercise["event_id"]), None)
            if row and row.get("player_id"):
                selected_player = canonical_player_id(str(row["player_id"]))
        owners = [event["to_franchise_id"] for event in events if event.get("to_franchise_id") and event["event_status"].casefold() in COMPLETED_STATUSES]
        return {
            "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            "pick_id": pick_id,
            "season": parts.get("season"), "round": parts.get("round"),
            "original_franchise_id": franchise_id(self.league_id, parts.get("original_roster")),
            "owner_chain": list(dict.fromkeys(owners)),
            "current_owner": owners[-1] if owners else None,
            "events": events,
            "exercised": bool(exercise), "selected_player_id": selected_player,
            "selected_player_url": f"/players/{selected_player.removeprefix('DTOS-P-')}" if selected_player else None,
            "slot_status": "determined" if exercise else "unknown",
            "reconciliation_status": "verified" if events else "no_historical_events",
            "provenance": ["Sleeper drafts", "Sleeper traded-pick transaction snapshots"],
        }

    def trade_dossiers(self) -> list[dict[str, Any]]:
        if self._trade_dossiers_cache is not None:
            return list(self._trade_dossiers_cache)
        with self._index_lock:
            if self._trade_dossiers_cache is not None:
                return list(self._trade_dossiers_cache)
            return self._build_trade_dossiers()

    def _build_trade_dossiers(self) -> list[dict[str, Any]]:
        dossiers = []
        self._ensure_event_indexes()
        for row in self._records("trade"):
            payload = row["payload"]
            trade_id = canonical_trade_id(self._source_league(row), row["source_record_id"])
            trade_events = list(self._events_by_parent.get(trade_id, []))
            dossiers.append({
                "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
                "trade_id": trade_id, "transaction_id": row["source_record_id"],
                "season": row["season"], "week": row["week"],
                "occurred_at": row["observed_at"],
                "status": str(payload.get("status") or "unknown"),
                "participating_franchises": [franchise_id(self.league_id, roster) for roster in payload.get("roster_ids") or []],
                "asset_events": trade_events,
                "faab": payload.get("waiver_budget") or [],
                "value_at_trade": None,
                "value_at_trade_availability": "unavailable_without_timestamped_valuation",
                "current_value_label": "Current value is intentionally separate from historical value.",
                "source": self._source(row),
                "raw_transaction": payload,
            })
        dossiers.sort(key=lambda item: (item["season"], item["week"] or 0, item["occurred_at"], item["trade_id"]), reverse=True)
        self._trade_dossiers_cache = dossiers
        self._trade_by_id = {
            key: dossier
            for dossier in dossiers
            for key in (dossier["trade_id"], dossier["transaction_id"])
        }
        return list(dossiers)

    def trade_dossier(self, transaction_id: str) -> dict[str, Any] | None:
        cached = self._trade_by_id.get(transaction_id)
        if cached is not None:
            return cached
        raw_id = transaction_id.removeprefix("TRADE-")
        if transaction_id.startswith("TRADE-"):
            raw_id = raw_id.rsplit("-", 1)[-1]
        row = self.store.transaction_record(self.league_id, raw_id)
        if row is None or row["entity_type"] != "trade":
            return None
        payload = row["payload"]
        trade_id = canonical_trade_id(self._source_league(row), row["source_record_id"])
        asset_ids = {
            canonical_player_id(str(player))
            for player in [*(payload.get("adds") or {}), *(payload.get("drops") or {})]
        }
        asset_ids.update(
            canonical_pick_id(
                pick.get("season") or "UNKNOWN", pick.get("round") or "UNKNOWN",
                pick.get("roster_id") or "UNKNOWN",
            )
            for pick in payload.get("draft_picks") or []
        )
        trade_events = [
            event
            for asset_id in sorted(asset_ids)
            for event in self.events(asset_id=asset_id)
            if event.get("parent_id") == trade_id
        ]
        dossier = {
            "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            "trade_id": trade_id, "transaction_id": row["source_record_id"],
            "season": row["season"], "week": row["week"],
            "occurred_at": row["observed_at"],
            "status": str(payload.get("status") or "unknown"),
            "participating_franchises": [
                franchise_id(self.league_id, roster)
                for roster in payload.get("roster_ids") or []
            ],
            "asset_events": trade_events,
            "faab": payload.get("waiver_budget") or [],
            "value_at_trade": None,
            "value_at_trade_availability": "unavailable_without_timestamped_valuation",
            "current_value_label": "Current value is intentionally separate from historical value.",
            "source": self._source(row), "raw_transaction": payload,
        }
        self._trade_by_id[raw_id] = dossier
        self._trade_by_id[trade_id] = dossier
        return dossier

    def transaction_archive(self) -> list[dict[str, Any]]:
        if self._transaction_archive_cache is not None:
            return list(self._transaction_archive_cache)
        rows = [*self._records("transaction"), *self._records("trade")]
        result = []
        for row in rows:
            payload = row["payload"]
            transaction_type = str(payload.get("type") or row["entity_type"])
            transaction_id = str(row["source_record_id"])
            result.append({
                "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
                "transaction_id": canonical_transaction_id(self._source_league(row), transaction_id),
                "sleeper_transaction_id": transaction_id,
                "trade_dossier_url": f"/trades/history/{transaction_id}" if transaction_type == "trade" else None,
                "season": row["season"], "week": row["week"],
                "type": transaction_type, "status": payload.get("status") or "unknown",
                "occurred_at": row["observed_at"], "roster_ids": payload.get("roster_ids") or [],
                "adds": payload.get("adds") or {}, "drops": payload.get("drops") or {},
                "draft_picks": payload.get("draft_picks") or [],
                "waiver_budget": payload.get("waiver_budget") or [],
                "source": self._source(row), "raw": payload,
            })
        result.sort(key=lambda item: (item["season"], item["week"] or 0, item["occurred_at"], item["transaction_id"]), reverse=True)
        self._transaction_archive_cache = result
        return list(result)

    def franchise_history(self, roster_id: str) -> dict[str, Any]:
        target = franchise_id(self.league_id, roster_id)
        records = {}
        for entity in ("franchise_identity", "season_standing", "weekly_roster"):
            _, records[entity] = self.store.records(
                self.league_id, entity, franchise_id=target, limit=100_000,
            )
        transactions = [row for row in self.transaction_archive() if str(roster_id) in {str(value) for value in row["roster_ids"]}]
        return {
            "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            "franchise_id": target, "identities": records["franchise_identity"],
            "standings": records["season_standing"],
            "roster_snapshots": records["weekly_roster"],
            "transactions": transactions,
            "season_status": {
                str(season): "in_progress" if season >= datetime.now(timezone.utc).year else "complete"
                for season in sorted({int(row["season"]) for row in records["season_standing"]})
            },
        }

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        needle = query.strip().casefold()
        if not needle:
            return []
        results: dict[tuple[str, str], dict[str, Any]] = {}
        current_players = self.current_data.get("players") or {}
        raw_player_ids = set(
            self.store.search_player_ids(self.league_id, needle, limit),
        )
        raw_player_ids.update(
            str(player_id)
            for player_id, player in current_players.items()
            if needle in str(player_id).casefold()
            or needle in str(player.get("full_name") or "").casefold()
            or needle in str(player.get("first_name") or "").casefold()
            or needle in str(player.get("last_name") or "").casefold()
        )
        for raw_id in raw_player_ids:
            identity = self.player_identity(raw_id)
            if needle in raw_id.casefold() or needle in identity["display_label"].casefold() or needle in identity["canonical_id"].casefold():
                results[("player", identity["canonical_id"])] = {
                    "canonical_id": identity["canonical_id"], "result_type": "player",
                    "display_label": identity["display_label"],
                    "resolution_status": identity["resolution_status"],
                    "canonical_url": f"/players/{raw_id}", "historical_availability": "available",
                    "match_reason": "player identity or alias",
                }
        pick_ids = (
            self.store.distinct_pick_ids(self.league_id)
            if any(character.isdigit() for character in needle)
            else ()
        )
        for pick_id in pick_ids:
            if needle in pick_id.casefold():
                results[("pick", pick_id)] = {
                    "canonical_id": pick_id, "result_type": "pick",
                    "display_label": pick_id, "resolution_status": "resolved",
                    "canonical_url": f"/picks/{pick_id}",
                    "historical_availability": "available", "match_reason": "pick identity",
                }
        for trade in self.store.search_transaction_ids(self.league_id, needle, limit):
            if trade["entity_type"] != "trade":
                continue
            transaction_id = trade["source_record_id"]
            source_league = str(
                trade["payload"].get("source_league_id") or self.league_id
            )
            trade_id = canonical_trade_id(source_league, transaction_id)
            results[("trade", trade_id)] = {
                    "canonical_id": trade_id, "result_type": "trade",
                    "display_label": f"Trade {transaction_id}", "resolution_status": "resolved",
                    "canonical_url": f"/trades/history/{transaction_id}",
                    "historical_availability": "available", "match_reason": "transaction identity",
                }
        for row in self._records("franchise_identity"):
            payload = row["payload"]
            label = str(payload.get("dtos_display_name") or payload.get("sleeper_username") or row["franchise_id"])
            if needle in label.casefold() or needle in str(row["franchise_id"]).casefold():
                results[("franchise", str(row["franchise_id"]))] = {
                    "canonical_id": row["franchise_id"], "result_type": "franchise",
                    "display_label": label, "resolution_status": "resolved",
                    "canonical_url": f"/history/team/{row['franchise_id']}",
                    "historical_availability": "available", "relevant_season": row["season"],
                    "match_reason": "franchise or manager identity",
                }
        return list(results.values())[:limit]

    def _ensure_directory_ids(self) -> None:
        if self._directory_ids is not None:
            return
        with self._index_lock:
            if self._directory_ids is not None:
                return
            player_ids = set((self.current_data.get("players") or {}))
            player_ids.update(self.store.distinct_player_ids(self.league_id))
            pick_ids = set(self.store.distinct_pick_ids(self.league_id))
            self._directory_ids = {
                "player": sorted(str(value) for value in player_ids),
                "pick": sorted(pick_ids),
            }
            self._approximate_size_bytes = self._estimate_index_size()

    def asset_directory_page(
        self, *, asset_type: str | None = None, limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        started = time.perf_counter()
        self._ensure_directory_ids()
        kinds = (
            (asset_type,) if asset_type in {"player", "pick"}
            else () if asset_type
            else ("player", "pick")
        )
        references = [
            (kind, value)
            for kind in kinds
            for value in (self._directory_ids or {}).get(kind, [])
        ]
        selected = references[offset:offset + limit]
        records = []
        for kind, value in selected:
            if kind == "player":
                identity = self.player_identity(value)
                records.append({
                    **identity,
                    "canonical_url": f"/players/{identity['sleeper_player_id']}",
                    "historical_availability": "available",
                })
                continue
            events = self.events(asset_id=value)
            owners = [
                event["to_franchise_id"] for event in events
                if event.get("to_franchise_id")
                and event["event_status"].casefold() in COMPLETED_STATUSES
            ]
            records.append({
                "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
                "canonical_id": value, "asset_type": "pick",
                "display_label": value, "resolution_status": "resolved",
                "canonical_url": f"/picks/{value}",
                "historical_availability": "available",
                "current_owner": owners[-1] if owners else None,
            })
        self._record_query(started, len(records))
        return len(references), records

    def asset_directory(self) -> list[dict[str, Any]]:
        total, records = self.asset_directory_page(limit=max(self.index_asset_count, 1))
        if len(records) < total:
            _, records = self.asset_directory_page(limit=total)
        return records

    def coverage(self) -> dict[str, Any]:
        if self._coverage_cache is not None:
            return {**self._coverage_cache, "read_model": self.query_metrics()}
        entity_types = (
            "league_season", "franchise_identity", "season_standing", "weekly_roster",
            "matchup", "player_week", "transaction", "trade", "draft", "draft_pick",
            "pick_snapshot",
        )
        seasons, counts = self.store.entity_counts_by_season(
            self.league_id, entity_types,
        )
        event_statistics = self.store.compact_event_statistics(self.league_id)
        identity_coverage = self.store.compact_identity_coverage(self.league_id)
        current_ids = {str(value) for value in (self.current_data.get("players") or {})}
        historical_ids = set(identity_coverage.pop("historical_player_ids"))
        resolved_ids = set(identity_coverage.pop("resolved_provider_ids")) | current_ids
        unresolved_ids = sorted((historical_ids | current_ids) - resolved_ids)
        unresolved = [
            self.player_identity(player_id)
            for player_id in unresolved_ids
        ]
        identity_count = len(historical_ids | current_ids)
        quality = self.store.quality(self.league_id)
        latest = self.store.latest_completed_foundation(self.league_id)
        self._coverage_cache = {
            "schema_version": HISTORICAL_ASSET_GRAPH_SCHEMA_VERSION,
            "historical_schema_version": HISTORICAL_SCHEMA_VERSION,
            "player_history_schema_version": PLAYER_HISTORY_SCHEMA_VERSION,
            "importer_version": IMPORTER_VERSION,
            "seasons": seasons, "counts_by_season": counts,
            "asset_event_count": event_statistics["asset_event_count"],
            "duplicate_event_ids": event_statistics["duplicate_event_ids"],
            "resolved_identity_count": identity_count - len(unresolved),
            "unresolved_identity_count": len(unresolved),
            "unresolved_identities": unresolved,
            "reconciliation_warnings": [issue for issue in quality if not issue.get("resolved")],
            "orphaned_events": event_statistics["orphaned_events"],
            "latest_successful_import": (latest or {}).get("completed_at"),
            "source_hashes_available": True,
            "status": "complete" if seasons and event_statistics["duplicate_event_ids"] == 0 else "incomplete",
        }
        return {**self._coverage_cache, "read_model": self.query_metrics()}

    def _event(
        self, row: dict[str, Any], asset_id: str, asset_type: str,
        event_type: str, status: str, *, parent_id: str | None = None,
        from_roster: object | None = None, to_roster: object | None = None,
        original_roster: object | None = None, from_franchise: str | None = None,
        to_franchise: str | None = None, suffix: str = "",
    ) -> HistoricalAssetEvent:
        source_league = self._source_league(row)
        missing = []
        occurred = row.get("observed_at")
        if not occurred:
            missing.append("Source did not provide an occurrence timestamp.")
        return HistoricalAssetEvent(
            event_id=canonical_event_id(
                self.league_id, row["entity_type"], row["season"], row.get("week") or "",
                row["source_record_id"], suffix,
            ), asset_id=asset_id, asset_type=asset_type, event_type=event_type,
            event_status=status, season=int(row["season"]), week=row.get("week"),
            occurred_at=occurred, observed_at=row.get("retrieved_at") or occurred or "",
            source_league_id=source_league, parent_id=parent_id,
            from_franchise_id=from_franchise or franchise_id(self.league_id, from_roster),
            to_franchise_id=to_franchise or franchise_id(self.league_id, to_roster),
            original_franchise_id=franchise_id(self.league_id, original_roster),
            source_provider=row.get("provider") or "Sleeper",
            source_record_id=row["source_record_id"],
            provenance=(
                f"{row.get('provider') or 'Sleeper'}:{source_league}:{row['source_record_id']}",
                f"Historical record schema {row.get('schema_version') or 'unknown'}",
            ), completeness="complete" if not missing else "incomplete",
            missing_reasons=tuple(missing),
        )

    def _source(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = row["payload"]
        return {
            "provider": row.get("provider"), "source_league_id": self._source_league(row),
            "source_record_id": row["source_record_id"], "retrieved_at": row.get("retrieved_at"),
            "observed_at": row.get("observed_at"), "schema_version": row.get("schema_version"),
            "importer_version": payload.get("importer_version") or IMPORTER_VERSION,
            "source_hash": payload.get("source_hash") or self._hash(payload),
            "availability": row.get("availability"),
        }

    def _source_league(self, row: dict[str, Any]) -> str:
        return str(row["payload"].get("source_league_id") or row["payload"].get("league_id") or self.league_id)

    def _draft_type(self, draft_id: object) -> str:
        draft = next((row["payload"].get("draft") or {} for row in self._records("draft") if row["source_record_id"] == str(draft_id)), {})
        return str((draft.get("type") or draft.get("settings", {}).get("type") or "rookie")).casefold()

    @staticmethod
    def _movement_type(transaction_type: str, action: str) -> str:
        if transaction_type == "trade":
            return "trade"
        if transaction_type == "waiver":
            return f"waiver_{action}"
        if transaction_type in {"commissioner", "commissioner_transaction"}:
            return f"commissioner_{action}"
        return f"free_agent_{action}"

    def _close_interval(self, active: dict[str, Any], event: dict[str, Any], status: str = "verified") -> OwnershipInterval:
        acquired = self._parse_time(active["event"].get("occurred_at"))
        disposed = self._parse_time(event.get("occurred_at"))
        return OwnershipInterval(
            asset_id=active["asset_id"], franchise_id=active["franchise_id"],
            acquisition_event_id=active["event"]["event_id"],
            acquired_at=active["event"].get("occurred_at"),
            disposition_event_id=event["event_id"], disposed_at=event.get("occurred_at"),
            duration_days=(disposed - acquired).days if acquired and disposed else None,
            season=active["event"]["season"], season_end_owner=False,
            source_event_ids=tuple([*active["sources"], event["event_id"]]),
            reconciliation_status=status,
        )

    def _positional_rank(self, player_id: str, totals: dict[str, float]) -> int | None:
        position = str(self.player_identity(player_id)["metadata"].get("position") or "")
        if not position:
            return None
        if self._identity_positions is None:
            self._identity_positions = self.store.identity_positions()
        current_players = self.current_data.get("players") or {}

        def candidate_position(candidate: str) -> str:
            current = current_players.get(candidate) or {}
            return str(
                current.get("position")
                or (self._identity_positions or {}).get(candidate)
                or ""
            )

        peers = [
            (candidate, value) for candidate, value in totals.items()
            if candidate_position(candidate) == position
        ]
        peers.sort(key=lambda item: (-item[1], item[0]))
        return next((index for index, item in enumerate(peers, 1) if item[0] == player_id), None)

    def _all_player_identities(self) -> list[dict[str, Any]]:
        player_ids = {
            str(row.get("player_id")) for entity in ("player_week", "draft_pick")
            for row in self._records(entity) if row.get("player_id")
        } | {str(player_id) for player_id in (self.current_data.get("players") or {})}
        return [self.player_identity(player_id) for player_id in sorted(player_ids)]

    @staticmethod
    def _settings_version(settings: dict[str, Any]) -> str:
        return "SLEEPER-SCORING-" + hashlib.sha256(
            repr(sorted(settings.items())).encode()
        ).hexdigest()[:12].upper()

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest()

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _pick_parts(pick_id: str) -> dict[str, str]:
        try:
            season, remainder = pick_id.removeprefix("PICK-").split("-R", 1)
            round_number, original = remainder.split("-ORIG", 1)
        except ValueError:
            return {}
        return {"season": season, "round": round_number, "original_roster": original}
