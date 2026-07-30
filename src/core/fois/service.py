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
from src.core.fois.facts import DraftFact, FOISFacts, SeasonResult, TradeFact
from src.core.fois.identity import identity_from_team
from src.core.fois.repository import FOISRepository

LOGGER = logging.getLogger("dtos.fois")


def fois_enabled() -> bool:
    return os.getenv("DTOS_FOIS_ENABLED", "0").casefold() in {"1", "true", "yes", "on"}


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
        self.engine = FOISEngine()
        self._status: dict[str, Any] = {
            "state": "disabled" if not fois_enabled() else "waiting",
            "last_run": None,
            "last_duration_ms": None,
            "last_error": None,
            "model_version": DEFAULT_FOIS_CONFIGURATION.model_version,
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

    async def generate(self, data: dict[str, Any]) -> tuple[Any, ...]:
        if not fois_enabled():
            self._status["state"] = "disabled"
            return ()
        self._status["state"] = "running"
        started = perf_counter()
        try:
            scores = await asyncio.to_thread(self._generate_sync, data)
            self._status.update({
                "state": "complete",
                "last_run": scores[0].generated_at if scores else None,
                "last_duration_ms": round((perf_counter() - started) * 1000, 3),
                "last_error": None,
                "records": len(scores),
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
        supplied_history = data.get("fois_history")
        history = (
            supplied_history
            if supplied_history is not None
            else self._history_loader(league_id)
            if self._history_loader is not None
            else {}
        )
        scores = []
        for team in data.get("teams") or ():
            identity = identity_from_team(league_id, team)
            roster_id = str(team.get("roster_id") or "")
            rows = history.get(roster_id) or {}
            seasons = tuple(SeasonResult(**row) for row in rows.get("seasons") or ())
            trades = tuple(TradeFact(**row) for row in rows.get("trades") or ())
            drafts = tuple(DraftFact(**row) for row in rows.get("drafts") or ())
            roster_metrics = rows.get("roster_metrics")
            history_source = (
                "explicit FOIS facts"
                if supplied_history is not None
                else "canonical Historical Memory"
            )
            facts = FOISFacts(
                league_id, identity.franchise_id, identity.owner_id,
                seasons, trades, drafts, roster_metrics,
                data.get("league_settings") or league.get("settings") or {},
                warnings=(
                    f"Results source: {history_source}; unsupported categories remain unavailable.",
                ),
                ownership_changes=int(rows.get("ownership_changes") or 0),
                expected_seasons=rows.get("expected_seasons"),
            )
            score = self.engine.evaluate(facts)
            fingerprint = hashlib.sha256(
                json.dumps(asdict(facts), sort_keys=True, default=str).encode()
            ).hexdigest()
            self.repository.save(score, fingerprint)
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
        return tuple(scores)
