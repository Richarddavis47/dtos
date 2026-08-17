"""Nonblocking FOIS orchestration over cached and supplied historical facts."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import asdict
from time import perf_counter
from collections.abc import Callable
from typing import Any

from src.core.fois.configuration import DEFAULT_FOIS_CONFIGURATION
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import DraftFact, FOISFacts, SeasonResult, TradeFact, WaiverFact
from src.core.fois.identity import canonical_league_identity, identity_from_team
from src.core.fois.models import GMTenure, TakeoverSnapshot
from src.core.fois.repository import FOISRepository
from src.core.brain import brain_service
from src.core.fois.models import FrontOfficeEvidence
from src.core.intelligence_memory import (
    fois_process_evidence, intelligence_checkpoint_store,
)

LOGGER = logging.getLogger("dtos.fois")


def fois_enabled() -> bool:
    return os.getenv("DTOS_FOIS_ENABLED", "1").casefold() in {"1", "true", "yes", "on"}


class FOISService:
    def __init__(
        self,
        repository: FOISRepository | None = None,
        *,
        repository_factory: Callable[[], FOISRepository] | None = None,
        history_loader: Callable[[str], dict[str, dict[str, Any]]] | None = None,
    ) -> None:
        if repository is None and repository_factory is None:
            raise ValueError("FOIS requires a repository or repository factory.")
        self._repository = repository
        self._repository_factory = repository_factory
        self._history_loader = history_loader
        self._generation_listeners: list[
            Callable[[dict[str, Any], tuple[Any, ...]], None]
        ] = []
        self.engine = FOISEngine()
        self._status: dict[str, Any] = {
            "state": "disabled" if not fois_enabled() else "waiting",
            "last_run": None,
            "last_duration_ms": None,
            "last_error": None,
            "model_version": DEFAULT_FOIS_CONFIGURATION.model_version,
            "request_time_provider_calls": 0,
        }

    @property
    def repository(self) -> FOISRepository:
        if self._repository is None:
            assert self._repository_factory is not None
            self._repository = self._repository_factory()
        return self._repository

    def status(self) -> dict[str, Any]:
        """Return memory-only status; never access providers or persistence."""
        return {**self._status, "enabled": fois_enabled()}

    def add_generation_listener(
        self, listener: Callable[[dict[str, Any], tuple[Any, ...]], None],
    ) -> None:
        """Register bounded post-generation work that must not affect FOIS output."""
        self._generation_listeners.append(listener)

    async def generate(self, data: dict[str, Any]) -> tuple[Any, ...]:
        if not fois_enabled():
            self._status["state"] = "disabled"
            return ()
        self._status["state"] = "running"
        started = perf_counter()
        try:
            scores = await asyncio.to_thread(self._generate_sync, data)
            league_id = str((data.get("league") or {}).get("league_id") or "configured-league")
            canonical = self.repository.canonical_health(
                league_id, DEFAULT_FOIS_CONFIGURATION.model_version,
            )
            self._status.update({
                "state": "complete",
                "last_run": scores[0].generated_at if scores else None,
                "last_duration_ms": round((perf_counter() - started) * 1000, 3),
                "last_error": None,
                "records": len(scores),
                "generation_status": "complete",
                **canonical,
            })
            LOGGER.info(
                "FOIS generation complete: model=%s records=%s duration_ms=%s",
                DEFAULT_FOIS_CONFIGURATION.model_version,
                len(scores),
                self._status["last_duration_ms"],
            )
            return scores
        except Exception as exc:
            self._status.update({"state": "failed", "last_error": str(exc)})
            LOGGER.exception(
                "FOIS generation failed: model=%s",
                DEFAULT_FOIS_CONFIGURATION.model_version,
            )
            raise

    def _generate_sync(self, data: dict[str, Any]) -> tuple[Any, ...]:
        league = data.get("league") or {}
        league_id = str(league.get("league_id") or "configured-league")
        identity_league_id = canonical_league_identity(league)
        supplied_history = data.get("fois_history")
        history = (
            supplied_history
            if supplied_history is not None
            else self._history_loader(league_id)
            if self._history_loader is not None
            else {}
        )
        placement_expected = max(
            (int(row.get("placement_seasons_expected") or 0) for row in history.values()),
            default=0,
        )
        placement_available = max(
            (int(row.get("placement_seasons_available") or 0) for row in history.values()),
            default=0,
        )
        self._status["placement_evidence"] = {
            "available_seasons": placement_available,
            "expected_completed_seasons": placement_expected,
            "completeness": round(
                placement_available / placement_expected * 100, 2,
            ) if placement_expected else 0.0,
        }
        permanent_checkpoints = intelligence_checkpoint_store.checkpoints(
            league_id=league_id, limit=10_000,
        )
        scores = []
        snapshots_written = 0
        snapshots_deduplicated = 0
        teams = data.get("teams") or ()
        canonical_brain = None
        if teams and supplied_history is None:
            canonical_brain = brain_service(data)
        for team in data.get("teams") or ():
            identity = identity_from_team(identity_league_id, team)
            roster_id = str(team.get("roster_id") or "")
            roster_checkpoints = tuple(
                row for row in permanent_checkpoints
                if row.roster_id in {None, roster_id}
            )
            checkpoint_coverage = fois_process_evidence(roster_checkpoints)
            checkpoint_evidence = tuple(FrontOfficeEvidence(
                evidence_type=f"intelligence_checkpoint:{row.trigger_type.value}",
                source_system="DTOS IntelligenceCheckpoint",
                source_identifier=row.checkpoint_id,
                description=("Definitive transaction-time evidence."
                             if row.provenance_type.definitive_process_evidence
                             else "Context-only evidence; excluded from definitive process grading."),
                observed_value={"dtos_value": row.dtos_value, "market_value": row.market_value,
                                "provenance": row.provenance_type.value,
                                "completeness": row.evidence_completeness.value},
                observed_at=row.timestamp, season=row.season, week=row.week,
                transaction_id=row.related_event_id,
                player_id=row.asset_id.removeprefix("player:") if row.asset_type == "player" else None,
            ) for row in roster_checkpoints)
            rows = history.get(roster_id) or {}
            owner_by_season = rows.get("owner_by_season") or {}
            current_owner = identity.owner_id
            seasons = tuple(
                SeasonResult(**row) for row in rows.get("seasons") or ()
                if current_owner is None or owner_by_season.get(str(row.get("season"))) in {None, current_owner}
            )
            trades = tuple(TradeFact(**row) for row in rows.get("trades") or ())
            drafts = tuple(DraftFact(**row) for row in rows.get("drafts") or ())
            waivers = tuple(WaiverFact(**row) for row in rows.get("waivers") or ())
            roster_metrics = dict(rows.get("roster_metrics") or {})
            asset_ids = tuple(
                str(player.get("id") or player.get("player_id"))
                for player in team.get("players") or ()
                if isinstance(player, dict) and (player.get("id") or player.get("player_id"))
            )
            brain_decision = (
                canonical_brain.decision("FOIS", asset_ids)
                if canonical_brain is not None else None
            )
            brain_snapshot_id = brain_decision.brain_snapshot_id if brain_decision else None
            brain_version = brain_decision.brain_version if brain_decision else None
            started_at = str(rows.get("tenure_started_at") or f"{min((row.season for row in seasons), default=int(league.get('season') or 0))}-01-01")
            tenure = GMTenure(
                identity.tenure_id(started_at), league_id, identity.franchise_id,
                identity.gm_id, identity.owner_name, started_at,
            )
            takeover_context = dict(rows.get("takeover_context") or {})
            takeover = TakeoverSnapshot(
                hashlib.sha256(f"takeover|{tenure.tenure_id}".encode()).hexdigest(),
                tenure.tenure_id, started_at, brain_snapshot_id,
                rows.get("competitive_window"),
                tuple(sorted(str(asset) for asset in team.get("players") or ())),
                tuple(sorted(str(pick) for pick in rows.get("draft_pick_ids") or ())),
                tuple(sorted(str(item) for item in rows.get("inherited_obligations") or ())),
                takeover_context,
            )
            self.repository.ensure_tenure(tenure, takeover)
            history_source = (
                "explicit FOIS facts"
                if supplied_history is not None
                else "canonical Historical Memory"
            )
            facts = FOISFacts(
                league_id, identity.franchise_id, identity.owner_id,
                seasons, trades, drafts, roster_metrics,
                data.get("league_settings") or league.get("settings") or {},
                evidence=checkpoint_evidence,
                warnings=(
                    f"Results source: {history_source}; unsupported categories remain unavailable.",
                    f"Permanent checkpoint evidence: {checkpoint_coverage['status']} "
                    f"({checkpoint_coverage['completeness']}% definitive).",
                    "Placement evidence: "
                    f"{rows.get('placement_seasons_available', 0)}/"
                    f"{rows.get('placement_seasons_expected', 0)} completed seasons; "
                    "unavailable placement is incomplete evidence, never zero.",
                ),
                ownership_changes=int(rows.get("ownership_changes") or 0),
                expected_seasons=rows.get("expected_seasons"),
                gm_id=identity.gm_id,
                gm_name=identity.owner_name,
                tenure_id=tenure.tenure_id,
                tenure_started_at=started_at,
                brain_snapshot_id=brain_snapshot_id,
                brain_version=brain_version,
                current_team_score=rows.get("current_team_score") or roster_metrics.get("current_team_score"),
                competitive_window=rows.get("competitive_window"),
                waivers=waivers,
                franchise_name=identity.franchise_name,
            )
            score = self.engine.evaluate(facts)
            fingerprint = hashlib.sha256(
                json.dumps(asdict(facts), sort_keys=True, default=str).encode()
            ).hexdigest()
            if self.repository.save(score, fingerprint):
                snapshots_written += 1
            else:
                snapshots_deduplicated += 1
            LOGGER.info(
                "FOIS franchise evaluated: model=%s league=%s franchise=%s "
                "window=%s-%s status=%s",
                score.model_version,
                score.league_id,
                score.franchise_id,
                score.evaluation_start_season,
                score.evaluation_end_season,
                "provisional" if score.provisional else "complete",
            )
            scores.append(score)
        self._status.update({
            "snapshots_written": snapshots_written,
            "snapshots_deduplicated": snapshots_deduplicated,
        })
        completed = tuple(scores)
        for listener in tuple(self._generation_listeners):
            try:
                listener(data, completed)
            except Exception as exc:
                LOGGER.warning(
                    "FOIS generation listener failed: type=%s",
                    type(exc).__name__,
                )
        return completed
