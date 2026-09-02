"""Bounded canonical historical-intelligence reads over Sleeper-backed history."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from threading import RLock
from typing import Any, Iterable, Mapping, Protocol

from src.core.history_context.store import CanonicalHistoryStore, canonical_history_store
from src.core.history_context.timestamps import canonical_transaction_timestamp

from .models import (
    CheckpointDirection, EvidenceAvailability, EvidenceScope,
    GlobalMarketCheckpoint, HistoricalEvent, HistoricalEventType,
    semantic_identity,
)


_ENTITY_TYPES = (
    "trade", "transaction", "draft_pick", "matchup", "season_standing",
    "playoff_result",
)


class GlobalCheckpointReader(Protocol):
    def global_market_checkpoints(
        self, *, asset_id: str, limit: int = 500,
    ) -> list[GlobalMarketCheckpoint]: ...


def _stable_values(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value not in (None, "")}))


def _franchise_id(league_id: str, value: object) -> str:
    text = str(value)
    return text if ":franchise:" in text else f"{league_id}:franchise:{text}"


def _pick_identity(payload: Mapping[str, Any], season: int) -> str | None:
    year = payload.get("season") or payload.get("year") or season
    round_number = payload.get("round")
    original = (
        payload.get("roster_id") or payload.get("original_roster_id")
        or payload.get("original_franchise") or payload.get("owner_id")
    )
    if round_number in (None, "") or original in (None, ""):
        return None
    return f"PICK-{year}-R{round_number}-ORIG{original}"


def _event_type(entity: str, payload: Mapping[str, Any]) -> HistoricalEventType | None:
    if entity == "trade":
        return HistoricalEventType.TRADE
    if entity == "transaction":
        kind = str(payload.get("type") or "").casefold()
        if kind == "waiver":
            return HistoricalEventType.WAIVER_ACQUISITION
        if kind in {"free_agent", "free agent"}:
            return HistoricalEventType.FREE_AGENT_ACQUISITION
        if payload.get("drops") and not payload.get("adds"):
            return HistoricalEventType.DROP
        return HistoricalEventType.PLAYER_EVENT
    return {
        "draft_pick": HistoricalEventType.ROOKIE_DRAFT_SELECTION,
        "matchup": HistoricalEventType.MATCHUP_RESULT,
        "season_standing": HistoricalEventType.SEASON_RESULT,
        "playoff_result": HistoricalEventType.CHAMPIONSHIP,
    }.get(entity)


def _event_time_key(value: str | None) -> tuple[int, str]:
    return (1 if value else 0, value or "")


class HistoricalIntelligenceService:
    """One read boundary for league-private events and shared sparse checkpoints.

    League facts remain reconstructable in ``CanonicalHistoryStore``. This class
    persists nothing: it normalizes and indexes one league at a time, and accepts
    only explicitly supplied sparse global market checkpoints.
    """

    def __init__(
        self, store: CanonicalHistoryStore = canonical_history_store,
        checkpoints: Iterable[GlobalMarketCheckpoint] = (),
        checkpoint_reader: GlobalCheckpointReader | None = None,
    ) -> None:
        self.store = store
        self.checkpoint_reader = checkpoint_reader
        self._lock = RLock()
        self._current: dict[str, tuple[int, tuple[dict[str, Any], ...]]] = {}
        self._current_revisions: defaultdict[str, int] = defaultdict(int)
        self._league_cache: dict[str, tuple[str, int, tuple[HistoricalEvent, ...]]] = {}
        self._event_index: dict[str, HistoricalEvent] = {}
        self._checkpoint_index: dict[str, tuple[GlobalMarketCheckpoint, ...]] = {}
        grouped: defaultdict[str, dict[str, GlobalMarketCheckpoint]] = defaultdict(dict)
        for checkpoint in checkpoints:
            grouped[checkpoint.asset_id][checkpoint.checkpoint_id] = checkpoint
        self._checkpoint_index = {
            asset_id: tuple(sorted(rows.values(), key=lambda row: row.occurred_at))
            for asset_id, rows in grouped.items()
        }
        self._metrics = {
            "league_builds": 0, "raw_record_reads": 0,
            "unrelated_league_reads": 0, "checkpoint_queries": 0,
            "durable_checkpoint_reads": 0,
        }

    def use_checkpoint_reader(self, reader: GlobalCheckpointReader) -> None:
        self.checkpoint_reader = reader

    def _checkpoint_rows(self, asset_id: str) -> tuple[GlobalMarketCheckpoint, ...]:
        rows = {row.checkpoint_id: row for row in self._checkpoint_index.get(str(asset_id), ())}
        if self.checkpoint_reader is not None:
            for row in self.checkpoint_reader.global_market_checkpoints(
                asset_id=str(asset_id), limit=500,
            ):
                rows[row.checkpoint_id] = row
            self._metrics["durable_checkpoint_reads"] += 1
        return tuple(sorted(rows.values(), key=lambda row: row.occurred_at))

    def replace_current_transactions(
        self, league_id: str, season: int, transactions: Iterable[Mapping[str, Any]],
    ) -> None:
        """Replace bounded active-season facts without durable snapshots."""
        key = str(league_id)
        rows = tuple(dict(row) for row in transactions)
        with self._lock:
            if self._current.get(key) != (int(season), rows):
                self._current[key] = (int(season), rows)
                self._current_revisions[key] += 1
                self._league_cache.pop(key, None)

    def _raw_records(self, league_id: str) -> list[dict[str, Any]]:
        _count, available = self.store.records(
            league_id, None, limit=1_000_000,
        )
        rows = [row for row in available if row.get("entity_type") in _ENTITY_TYPES]
        self._metrics["raw_record_reads"] += len(rows)
        return rows

    @staticmethod
    def _normalize(row: Mapping[str, Any]) -> HistoricalEvent | None:
        league_id = str(row.get("league_id") or "")
        season = int(row.get("season") or 0)
        entity = str(row.get("entity_type") or "")
        payload = dict(row.get("payload") or {})
        selected_type = _event_type(entity, payload)
        source_id = str(row.get("source_record_id") or "")
        if not league_id or not season or selected_type is None or not source_id:
            return None
        roster_ids: set[object] = set(payload.get("roster_ids") or ())
        for mapping in (payload.get("adds"), payload.get("drops")):
            if isinstance(mapping, Mapping):
                roster_ids.update(mapping.values())
        if row.get("franchise_id"):
            roster_ids.add(row["franchise_id"])
        player_ids = set()
        if row.get("player_id"):
            player_ids.add(str(row["player_id"]))
        for mapping in (payload.get("adds"), payload.get("drops")):
            if isinstance(mapping, Mapping):
                player_ids.update(map(str, mapping.keys()))
        picks = []
        candidates = payload.get("draft_picks") or []
        if entity in {"draft_pick", "pick_snapshot"}:
            candidates = [payload]
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                identity = _pick_identity(candidate, season)
                if identity:
                    picks.append(identity)
        attributes = {
            key: payload.get(key) for key in (
                "type", "status", "adds", "drops", "draft_picks", "matchup_id",
                "team_points", "winner", "loser", "tie", "champion_roster_id",
                "runner_up_roster_id", "placements", "owner_id", "sleeper_roster_id",
                "wins", "losses", "ties", "points_for", "rank", "pick_no", "round",
                "roster_id", "player_id", "season", "year",
            ) if key in payload
        }
        return HistoricalEvent(
            event_id=semantic_identity(
                "history-event", row.get("provider") or "Sleeper",
                league_id, selected_type.value, source_id,
            ),
            event_type=selected_type, scope=EvidenceScope.LEAGUE,
            provider=str(row.get("provider") or "Sleeper"),
            source_record_id=source_id, season=season, league_id=league_id,
            league_season_context_id=f"{league_id}:season:{season}",
            occurred_at=row.get("occurred_at"),
            week=int(row["week"]) if row.get("week") is not None else None,
            timestamp_provenance=dict(row.get("timestamp_provenance") or {}),
            franchise_ids=_stable_values(
                _franchise_id(league_id, value) for value in roster_ids
            ),
            player_ids=_stable_values(player_ids), pick_ids=_stable_values(picks),
            availability=EvidenceAvailability(str(row.get("availability") or "observed")),
            confidence=int(row.get("confidence") or 0),
            source_reference=str(row.get("record_key") or "") or None,
            attributes=attributes,
        )

    @staticmethod
    def _normalize_current(
        league_id: str, season: int, transaction: Mapping[str, Any],
    ) -> HistoricalEvent | None:
        payload = dict(transaction)
        source_id = str(payload.get("transaction_id") or "")
        if not source_id:
            return None
        occurred_at, provenance = canonical_transaction_timestamp(payload)
        entity = "trade" if str(payload.get("type") or "").casefold() == "trade" else "transaction"
        return HistoricalIntelligenceService._normalize({
            "record_key": f"current:{league_id}:{season}:{entity}:{source_id}",
            "entity_type": entity, "league_id": league_id, "season": season,
            "week": payload.get("week") or payload.get("leg"),
            "source_record_id": source_id, "occurred_at": occurred_at,
            "provider": "Sleeper", "availability": "observed", "confidence": 100,
            "payload": payload, "timestamp_provenance": provenance,
        })

    def _events(self, league_id: str) -> tuple[HistoricalEvent, ...]:
        key = str(league_id)
        dataset = self.store.dataset_version(key)
        with self._lock:
            revision = self._current_revisions[key]
            cached = self._league_cache.get(key)
            current = self._current.get(key)
            if cached and cached[:2] == (dataset, revision):
                return cached[2]
        normalized = [self._normalize(row) for row in self._raw_records(key)]
        if current:
            season, rows = current
            normalized.extend(self._normalize_current(key, season, row) for row in rows)
        # Stable semantic identity deduplicates the active/completed season boundary.
        deduplicated = {
            event.event_id: event for event in normalized if event is not None
        }
        events = tuple(sorted(
            deduplicated.values(),
            key=lambda event: (
                event.season, event.week or 0, _event_time_key(event.occurred_at),
                event.event_id,
            ), reverse=True,
        ))
        with self._lock:
            self._league_cache[key] = (dataset, revision, events)
            self._event_index.update((event.event_id, event) for event in events)
            self._metrics["league_builds"] += 1
        return events

    def events_for_league(
        self, league_id: str, *, event_type: HistoricalEventType | None = None,
        season: int | None = None,
    ) -> tuple[HistoricalEvent, ...]:
        return tuple(event for event in self._events(str(league_id)) if (
            (event_type is None or event.event_type is event_type)
            and (season is None or event.season == int(season))
        ))

    def events_for_franchise(
        self, league_id: str, franchise_id: str,
    ) -> tuple[HistoricalEvent, ...]:
        target = _franchise_id(str(league_id), franchise_id)
        return tuple(
            event for event in self._events(str(league_id))
            if target in event.franchise_ids
        )

    def events_for_player(
        self, league_id: str, player_id: str,
    ) -> tuple[HistoricalEvent, ...]:
        return tuple(
            event for event in self._events(str(league_id))
            if str(player_id) in event.player_ids
        )

    def events_between(
        self, league_id: str, start: str, end: str,
    ) -> tuple[HistoricalEvent, ...]:
        return tuple(
            event for event in self._events(str(league_id))
            if event.occurred_at is not None and start <= event.occurred_at <= end
        )

    def event_by_identity(
        self, league_id: str, event_id: str,
    ) -> HistoricalEvent | None:
        self._events(str(league_id))
        event = self._event_index.get(str(event_id))
        return event if event and event.league_id == str(league_id) else None

    def season_history(self, league_id: str, season: int) -> tuple[HistoricalEvent, ...]:
        return self.events_for_league(str(league_id), season=int(season))

    def transaction_history(self, league_id: str) -> tuple[HistoricalEvent, ...]:
        selected = {
            HistoricalEventType.TRADE, HistoricalEventType.WAIVER_ACQUISITION,
            HistoricalEventType.FREE_AGENT_ACQUISITION, HistoricalEventType.DROP,
            HistoricalEventType.PLAYER_EVENT, HistoricalEventType.PICK_TRADE,
        }
        return tuple(event for event in self._events(str(league_id)) if event.event_type in selected)

    def link_checkpoint(
        self, league_id: str, event_id: str, checkpoint_id: str,
    ) -> HistoricalEvent:
        """Return a derived linkage without mutating raw provider truth."""
        event = self.event_by_identity(league_id, event_id)
        if event is None:
            raise KeyError("Unknown league-scoped historical event.")
        if not any(
            checkpoint.checkpoint_id == checkpoint_id
            for player_id in event.player_ids
            for checkpoint in self._checkpoint_rows(player_id)
        ):
            raise KeyError("Unknown global market checkpoint.")
        return replace(
            event,
            market_checkpoint_ids=_stable_values((*event.market_checkpoint_ids, checkpoint_id)),
            availability=EvidenceAvailability.DERIVED,
        )

    def nearest_market_checkpoint(
        self, asset_id: str, occurred_at: str, *,
        direction: CheckpointDirection = CheckpointDirection.AT_OR_BEFORE,
    ) -> GlobalMarketCheckpoint | None:
        self._metrics["checkpoint_queries"] += 1
        rows = self._checkpoint_rows(str(asset_id))
        if direction is CheckpointDirection.EXACT:
            return next((row for row in rows if row.occurred_at == occurred_at), None)
        if direction is CheckpointDirection.AT_OR_BEFORE:
            eligible = [row for row in rows if row.occurred_at <= occurred_at]
            return eligible[-1] if eligible else None
        return next((row for row in rows if row.occurred_at > occurred_at), None)

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)


historical_intelligence = HistoricalIntelligenceService()
