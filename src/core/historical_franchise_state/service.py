"""Derived historical franchise states over canonical history and market memory."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from statistics import mean
from threading import RLock
from typing import Any, Iterable, Mapping

from src.core.competitive_window import build_competitive_window
from src.core.historical_intelligence import (
    CheckpointDirection, HistoricalEvent, HistoricalEventType,
    HistoricalIntelligenceService, historical_intelligence, semantic_identity,
)

from .models import (
    BoundaryMode, CoverageDimension, EvidenceCoverage, HistoricalAssetState,
    HistoricalBoundary, HistoricalFranchiseState, HistoricalLineupState,
    HistoricalRecordState, HistoricalWindowState, ReconstructionAvailability,
    StateDifference,
)


def _franchise_id(league_id: str, value: object) -> str:
    text = str(value)
    return text if ":franchise:" in text else f"{league_id}:franchise:{text}"


def _roster_number(franchise_id: str) -> str:
    return franchise_id.rsplit(":", 1)[-1]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class HistoricalFranchiseStateService:
    """Reconstruct state by reversing post-boundary events from provider truth."""

    def __init__(self, history: HistoricalIntelligenceService = historical_intelligence) -> None:
        self.history = history
        self._lock = RLock()
        self._metrics = {
            "reconstructions": 0, "provider_calls": 0, "cache_hits": 0,
            "global_market_lookups": 0, "source_record_queries": 0,
        }
        self._record_cache: dict[
            tuple[tuple[str, int], str, int, str], tuple[dict[str, Any], ...]
        ] = {}
        self._state_cache: dict[
            tuple[tuple[str, int], str, str, int, str | None, int | None, str | None, str],
            HistoricalFranchiseState,
        ] = {}

    @staticmethod
    def _event_order(event: HistoricalEvent) -> tuple[str, int, str]:
        return (event.occurred_at or "", event.week or 0, event.event_id)

    def _at_boundary(
        self, event: HistoricalEvent, boundary: HistoricalBoundary,
        target: HistoricalEvent | None = None,
    ) -> bool:
        if event.season < boundary.season:
            return True
        if event.season > boundary.season:
            return False
        if boundary.event_id:
            target = target or self.history.event_by_identity(
                event.league_id, boundary.event_id,
            )
            if target is None:
                raise KeyError("Unknown event boundary for selected league.")
            comparison = self._event_order(event) <= self._event_order(target)
            if boundary.mode is BoundaryMode.BEFORE and event.event_id == target.event_id:
                return False
            return comparison
        if boundary.occurred_at and event.occurred_at:
            if boundary.mode is BoundaryMode.BEFORE:
                return event.occurred_at < boundary.occurred_at
            return event.occurred_at <= boundary.occurred_at
        if boundary.week is not None and event.week is not None:
            return event.week <= boundary.week
        return False

    def _records(self, league_id: str, season: int, entity: str) -> list[dict[str, Any]]:
        generation = self.history.cache_identity(league_id)
        key = (generation, str(league_id), int(season), str(entity))
        with self._lock:
            cached = self._record_cache.get(key)
            if cached is not None:
                self._metrics["cache_hits"] += 1
                return list(cached)
        self._metrics["source_record_queries"] += 1
        _count, rows = self.history.store.records(
            league_id, entity, season=season, limit=10_000,
        )
        frozen = tuple(rows)
        with self._lock:
            if len(self._record_cache) >= 512:
                self._record_cache.clear()
            self._record_cache[key] = frozen
        return list(frozen)

    def _final_rosters(self, league_id: str, season: int) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for row in self._records(league_id, season, "roster_snapshot"):
            franchise = str(row.get("franchise_id") or "")
            if franchise:
                result[franchise] = set(map(str, (row.get("payload") or {}).get("players") or ()))
        return result

    @staticmethod
    def _reverse_event(
        rosters: dict[str, set[str]], picks: dict[str, str], event: HistoricalEvent,
    ) -> None:
        attributes = event.attributes
        adds = attributes.get("adds") or {}
        drops = attributes.get("drops") or {}
        if isinstance(adds, Mapping):
            for player_id, roster_id in adds.items():
                rosters.setdefault(_franchise_id(event.league_id, roster_id), set()).discard(str(player_id))
        if isinstance(drops, Mapping):
            for player_id, roster_id in drops.items():
                rosters.setdefault(_franchise_id(event.league_id, roster_id), set()).add(str(player_id))
        for raw_pick in attributes.get("draft_picks") or ():
            if not isinstance(raw_pick, Mapping):
                continue
            year, round_number = raw_pick.get("season"), raw_pick.get("round")
            original = raw_pick.get("roster_id") or raw_pick.get("original_roster_id")
            previous = raw_pick.get("previous_owner_id") or original
            if year and round_number and original:
                picks[f"PICK-{year}-R{round_number}-ORIG{original}"] = _franchise_id(event.league_id, previous)
        if event.event_type is HistoricalEventType.ROOKIE_DRAFT_SELECTION:
            roster_id = attributes.get("roster_id") or attributes.get("owner_id")
            player_id = next(iter(event.player_ids), None)
            if roster_id and player_id:
                rosters.setdefault(_franchise_id(event.league_id, roster_id), set()).discard(player_id)
                year = attributes.get("season") or attributes.get("year") or event.season
                round_number = attributes.get("round")
                if round_number:
                    picks[f"PICK-{year}-R{round_number}-ORIG{roster_id}"] = _franchise_id(event.league_id, roster_id)

    def _final_picks(self, league_id: str, season: int) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in self._records(league_id, season, "pick_snapshot"):
            payload = row.get("payload") or {}
            pick_id = self.history.store._canonical_pick_id(payload, season)
            owner = payload.get("owner_id") or payload.get("roster_id")
            if pick_id and owner:
                result[pick_id] = _franchise_id(league_id, owner)
        return result

    def _settings(self, league_id: str, season: int) -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...], tuple[str, ...]]:
        rows = self._records(league_id, season, "league_season")
        if not rows:
            return {}, {}, (), ()
        payload = rows[0].get("payload") or {}
        return (
            dict(payload.get("settings") or {}),
            dict(payload.get("scoring_settings") or {}),
            tuple(map(str, payload.get("roster_positions") or ())),
            (str(rows[0].get("record_key") or ""),),
        )

    def _record(
        self, league_id: str, franchise_id: str, boundary: HistoricalBoundary,
    ) -> HistoricalRecordState:
        roster_id = _roster_number(franchise_id)
        wins = losses = ties = 0
        points_for = 0.0
        opponents: list[tuple[float, float]] = []
        for row in self._records(league_id, boundary.season, "matchup"):
            payload = row.get("payload") or {}
            week = int(row.get("week") or 0)
            if boundary.week is not None and week > boundary.week:
                continue
            scores = payload.get("team_points") or {}
            if roster_id not in scores:
                continue
            own = float(scores[roster_id] or 0)
            other = max((float(value or 0) for key, value in scores.items() if str(key) != roster_id), default=own)
            points_for += own
            opponents.append((own, other))
            if own > other:
                wins += 1
            elif own < other:
                losses += 1
            else:
                ties += 1
        return HistoricalRecordState(wins, losses, ties, points_for, None, len(opponents))

    def _market_assets(
        self, player_ids: Iterable[str], occurred_at: str | None,
        production: Mapping[str, float] | None = None,
    ) -> tuple[list[HistoricalAssetState], float, int]:
        assets, known = [], 0.0
        for player_id in sorted(set(player_ids)):
            checkpoint = None
            if occurred_at:
                checkpoint = self.history.nearest_market_checkpoint(
                    player_id, occurred_at,
                    direction=CheckpointDirection.AT_OR_BEFORE,
                )
                self._metrics["global_market_lookups"] += 1
            identity = self.history.store.identity_for_provider_id(player_id) or {}
            metadata = identity.get("metadata") or {}
            position = metadata.get("position")
            age = None
            birthdate = metadata.get("birthdate") or metadata.get("birth_date")
            if birthdate and occurred_at:
                try:
                    born = datetime.fromisoformat(str(birthdate).replace("Z", "+00:00"))
                    as_of = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
                    age = round((as_of - born).days / 365.2425, 2)
                except (TypeError, ValueError):
                    age = None
            value = float(checkpoint.normalized_value) if checkpoint else None
            if value is not None:
                known += value
            assets.append(HistoricalAssetState(
                asset_id=player_id, asset_type="player", position=position,
                market_value=value,
                market_checkpoint_id=checkpoint.checkpoint_id if checkpoint else None,
                market_observed_at=checkpoint.occurred_at if checkpoint else None,
                market_confidence=checkpoint.confidence if checkpoint else None,
                season_to_date_points=(production or {}).get(player_id),
                age_as_of=age,
            ))
        return assets, known, sum(row.market_value is not None for row in assets)

    def _lineup_and_production(
        self, league_id: str, franchise_id: str, boundary: HistoricalBoundary,
        player_ids: set[str], roster_positions: tuple[str, ...],
    ) -> tuple[HistoricalLineupState, dict[str, float]]:
        rows = self._records(league_id, boundary.season, "player_week")
        eligible = []
        for row in rows:
            if str(row.get("franchise_id") or "") != franchise_id:
                continue
            week = int(row.get("week") or 0)
            if boundary.week is not None and week > boundary.week:
                continue
            player_id = str(row.get("player_id") or "")
            if player_id in player_ids:
                eligible.append(row)
        production: defaultdict[str, float] = defaultdict(float)
        for row in eligible:
            production[str(row["player_id"])] += float((row.get("payload") or {}).get("points") or 0)
        evidence_week = max((int(row.get("week") or 0) for row in eligible), default=None)
        latest = [row for row in eligible if int(row.get("week") or 0) == evidence_week]
        actual = tuple(sorted(
            str(row["player_id"]) for row in latest
            if (row.get("payload") or {}).get("starter")
        ))
        weekly_points = {
            str(row["player_id"]): float((row.get("payload") or {}).get("points") or 0)
            for row in latest
        }
        positions = {
            player_id: str(((self.history.store.identity_for_provider_id(player_id) or {}).get("metadata") or {}).get("position") or "")
            for player_id in player_ids
        }
        remaining = set(player_ids)
        optimal: list[str] = []
        ignored_slots = {"BN", "BENCH", "IR", "TAXI", "RESERVE", "K", "DEF"}
        for slot in roster_positions:
            normalized = slot.upper()
            if normalized in ignored_slots:
                continue
            if normalized in {"FLEX", "RB_WR_TE", "W_R_T"}:
                allowed = {"RB", "WR", "TE"}
            elif normalized in {"SUPER_FLEX", "SUPERFLEX", "Q_W_R_T"}:
                allowed = {"QB", "RB", "WR", "TE"}
            else:
                allowed = {normalized}
            candidates = [player_id for player_id in remaining if positions.get(player_id) in allowed]
            if candidates:
                selected = max(candidates, key=lambda player_id: (weekly_points.get(player_id, 0), player_id))
                optimal.append(selected)
                remaining.remove(selected)
        return HistoricalLineupState(
            actual_starters=actual, optimal_starters=tuple(optimal),
            actual_points=sum(weekly_points.get(player_id, 0) for player_id in actual) if latest else None,
            optimal_points=sum(weekly_points.get(player_id, 0) for player_id in optimal) if latest else None,
            evidence_week=evidence_week,
        ), dict(production)

    @staticmethod
    def _coverage(availability: ReconstructionAvailability, confidence: int, *reasons: str) -> EvidenceCoverage:
        return EvidenceCoverage(availability, confidence, tuple(reasons))

    def reconstruct(
        self, league_id: str, franchise_id: str, boundary: HistoricalBoundary,
        *, include_trace: bool = False,
    ) -> HistoricalFranchiseState:
        league_id = str(league_id)
        franchise_id = _franchise_id(league_id, franchise_id)
        cache_generation = self.history.cache_identity(league_id)
        history_generation = cache_generation[0]
        cache_key = (
            cache_generation, league_id, franchise_id, int(boundary.season),
            boundary.occurred_at, boundary.week, boundary.event_id,
            boundary.mode.value,
        )
        if not include_trace:
            with self._lock:
                cached = self._state_cache.get(cache_key)
                if cached is not None:
                    self._metrics["cache_hits"] += 1
                    return cached
        settings, scoring, roster_positions, settings_refs = self._settings(league_id, boundary.season)
        events = list(self.history.season_history(league_id, boundary.season))
        final_rosters = self._final_rosters(league_id, boundary.season)
        picks = self._final_picks(league_id, boundary.season)
        warnings: list[str] = []
        if franchise_id not in final_rosters:
            warnings.append("missing_franchise_roster_snapshot")
            final_rosters.setdefault(franchise_id, set())
        target = (
            self.history.event_by_identity(league_id, boundary.event_id)
            if boundary.event_id else None
        )
        later = [
            event for event in events
            if not self._at_boundary(event, boundary, target)
        ]
        trace: list[Mapping[str, Any]] = []
        for event in sorted(later, key=self._event_order, reverse=True):
            if event.event_type in {
                HistoricalEventType.TRADE, HistoricalEventType.WAIVER_ACQUISITION,
                HistoricalEventType.FREE_AGENT_ACQUISITION, HistoricalEventType.DROP,
                HistoricalEventType.PLAYER_EVENT, HistoricalEventType.PICK_TRADE,
                HistoricalEventType.ROOKIE_DRAFT_SELECTION,
            }:
                self._reverse_event(final_rosters, picks, event)
                if include_trace:
                    trace.append({"event_id": event.event_id, "operation": "reverse", "occurred_at": event.occurred_at})
        players = final_rosters[franchise_id]
        effective_time = boundary.occurred_at
        if effective_time is None and boundary.event_id:
            target = self.history.event_by_identity(league_id, boundary.event_id)
            effective_time = target.occurred_at if target else None
        lineup, production = self._lineup_and_production(
            league_id, franchise_id, boundary, players, roster_positions,
        )
        assets, known_value, known_count = self._market_assets(players, effective_time, production)
        selected_picks = tuple(HistoricalAssetState(asset_id=pick, asset_type="pick") for pick, owner in sorted(picks.items()) if owner == franchise_id)
        position_counts: defaultdict[str, int] = defaultdict(int)
        for asset in assets:
            position_counts[str(asset.position or "UNKNOWN")] += 1
        record = self._record(league_id, franchise_id, boundary)
        market_ratio = known_count / len(assets) if assets else 0.0
        age_count = sum(row.age_as_of is not None for row in assets)
        age_ratio = age_count / len(assets) if assets else 0.0
        ownership_available = bool(final_rosters.get(franchise_id))
        settings_available = bool(settings or scoring or roster_positions)
        market_available = known_count > 0
        coverage = {
            CoverageDimension.SETTINGS.value: self._coverage(ReconstructionAvailability.COMPLETE if settings_available else ReconstructionAvailability.UNAVAILABLE, 100 if settings_available else 0, "historical_season_contract" if settings_available else "missing_historical_settings"),
            CoverageDimension.OWNERSHIP.value: self._coverage(ReconstructionAvailability.COMPLETE if ownership_available else ReconstructionAvailability.UNAVAILABLE, 95 if ownership_available else 0, "reverse_event_reconstruction" if ownership_available else "missing_roster_snapshot"),
            CoverageDimension.PICKS.value: self._coverage(ReconstructionAvailability.COMPLETE if picks else ReconstructionAvailability.PARTIAL, 85 if picks else 35, "provider_pick_snapshot" if picks else "pick_snapshot_unavailable"),
            CoverageDimension.MARKET.value: self._coverage(ReconstructionAvailability.COMPLETE if market_ratio == 1 else ReconstructionAvailability.PARTIAL if market_available else ReconstructionAvailability.UNAVAILABLE, round(market_ratio * 100), "at_or_before_global_checkpoint" if market_available else "historical_market_unavailable"),
            CoverageDimension.LINEUP.value: self._coverage(ReconstructionAvailability.COMPLETE if lineup.evidence_week is not None else ReconstructionAvailability.UNAVAILABLE, 90 if lineup.evidence_week is not None else 0, "historical_week_lineup" if lineup.evidence_week is not None else "historical_lineup_unavailable"),
            CoverageDimension.PRODUCTION.value: self._coverage(ReconstructionAvailability.COMPLETE if production else ReconstructionAvailability.UNAVAILABLE, 90 if production else 0, "season_to_date_actuals" if production else "historical_production_unavailable"),
            CoverageDimension.STANDINGS.value: self._coverage(ReconstructionAvailability.COMPLETE if record.games_observed else ReconstructionAvailability.PARTIAL, 90 if record.games_observed else 25, "matchups_through_boundary"),
            CoverageDimension.AGE.value: self._coverage(
                ReconstructionAvailability.COMPLETE if age_ratio == 1 else ReconstructionAvailability.PARTIAL if age_count else ReconstructionAvailability.UNAVAILABLE,
                round(age_ratio * 100),
                "birthdate_as_of_boundary" if age_count else "birthdate_evidence_unavailable",
            ),
        }
        numeric_confidence = round(mean(row.confidence for row in coverage.values()))
        current_strength = min(100, round((known_value / max(1, len(assets))) / 100)) if market_available else 0
        future_strength = min(100, round((known_value + len(selected_picks) * 1000) / max(1, len(assets) + len(selected_picks)) / 100)) if market_available else 0
        if ownership_available and market_available:
            window = build_competitive_window(
                current_strength=current_strength, overall_strength=current_strength,
                future_strength=future_strength, depth=min(100, len(assets) * 5),
                youth=50, draft_capital=min(100, len(selected_picks) * 12), risk=50,
                confidence=min(numeric_confidence, round(market_ratio * 100)),
            )
            window_state = HistoricalWindowState(
                window.classification.value, window.confidence,
                window.championship_score, window.playoff_score, window.rebuild_score,
                window.reasons,
            )
            coverage[CoverageDimension.COMPETITIVE_WINDOW.value] = self._coverage(ReconstructionAvailability.PARTIAL, window.confidence, "shared_competitive_window_partial_historical_inputs")
        else:
            window_state = HistoricalWindowState(None, 0)
            coverage[CoverageDimension.COMPETITIVE_WINDOW.value] = self._coverage(ReconstructionAvailability.UNAVAILABLE, 0, "insufficient_historical_inputs")
        availability = ReconstructionAvailability.PARTIAL
        if not settings_available or not ownership_available:
            availability = ReconstructionAvailability.INVALID
        elif all(row.availability is ReconstructionAvailability.COMPLETE for row in coverage.values()):
            availability = ReconstructionAvailability.COMPLETE
        checkpoint_ids = tuple(sorted(row.market_checkpoint_id for row in assets if row.market_checkpoint_id))
        market_generation = hashlib.sha256(_canonical_json(checkpoint_ids).encode()).hexdigest()[:24]
        state_id = semantic_identity(
            "historical-franchise-state", league_id, franchise_id,
            _canonical_json({"season": boundary.season, "occurred_at": boundary.occurred_at, "week": boundary.week, "event_id": boundary.event_id, "mode": boundary.mode.value}),
            history_generation, market_generation, "reverse-event-reconstruction-1",
        )
        self._metrics["reconstructions"] += 1
        result = HistoricalFranchiseState(
            state_id, league_id, franchise_id, boundary, history_generation,
            market_generation, availability,
            round(mean(row.confidence for row in coverage.values())),
            settings, scoring, roster_positions, tuple(assets), selected_picks,
            lineup, record, window_state,
            known_value if market_ratio == 1 and assets else None,
            known_value, market_ratio, dict(position_counts), coverage,
            tuple(warnings), settings_refs, len(events) - len(later), tuple(trace),
        )
        if not include_trace:
            with self._lock:
                if len(self._state_cache) >= 4096:
                    self._state_cache.clear()
                self._state_cache[cache_key] = result
        return result

    def around_event(
        self, league_id: str, franchise_id: str, event_id: str, *, include_trace: bool = False,
    ) -> tuple[HistoricalFranchiseState, HistoricalFranchiseState]:
        event = self.history.event_by_identity(str(league_id), str(event_id))
        if event is None:
            raise KeyError("Unknown event boundary for selected league.")
        common = {"season": event.season, "occurred_at": event.occurred_at, "week": event.week, "event_id": event.event_id}
        return (
            self.reconstruct(league_id, franchise_id, HistoricalBoundary(**common, mode=BoundaryMode.BEFORE), include_trace=include_trace),
            self.reconstruct(league_id, franchise_id, HistoricalBoundary(**common, mode=BoundaryMode.AT_OR_BEFORE), include_trace=include_trace),
        )

    async def reconstruct_async(
        self, league_id: str, franchise_id: str, boundary: HistoricalBoundary,
        *, include_trace: bool = False,
    ) -> HistoricalFranchiseState:
        """Keep bounded historical reads and derivation off the event loop."""
        return await asyncio.to_thread(
            self.reconstruct, league_id, franchise_id, boundary,
            include_trace=include_trace,
        )

    async def around_event_async(
        self, league_id: str, franchise_id: str, event_id: str,
        *, include_trace: bool = False,
    ) -> tuple[HistoricalFranchiseState, HistoricalFranchiseState]:
        return await asyncio.to_thread(
            self.around_event, league_id, franchise_id, event_id,
            include_trace=include_trace,
        )

    @staticmethod
    def difference(before: HistoricalFranchiseState, after: HistoricalFranchiseState) -> StateDifference:
        if (before.league_id, before.franchise_id) != (after.league_id, after.franchise_id):
            raise ValueError("State differences require one league-scoped franchise.")
        before_players, after_players = {row.asset_id for row in before.players}, {row.asset_id for row in after.players}
        before_picks, after_picks = {row.asset_id for row in before.draft_picks}, {row.asset_id for row in after.draft_picks}
        dimensions = []
        if before_players != after_players:
            dimensions.append("players")
        if before_picks != after_picks:
            dimensions.append("draft_picks")
        if before.known_market_value != after.known_market_value:
            dimensions.append("known_market_value")
        return StateDifference(
            before.state_id, after.state_id,
            tuple(sorted(after_players - before_players)), tuple(sorted(before_players - after_players)),
            tuple(sorted(after_picks - before_picks)), tuple(sorted(before_picks - after_picks)),
            after.known_market_value - before.known_market_value,
            tuple(dimensions),
        )

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)


historical_franchise_state = HistoricalFranchiseStateService()
