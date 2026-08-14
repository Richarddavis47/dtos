"""Sleeper-cache-backed canonical history contract.

This intentionally resembles the bounded read surface formerly supplied by
``HistoricalStore`` so consumers can migrate without retaining a SQLite
provider archive. It never opens the dormant legacy database.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from config import SLEEPER_SEASON_CACHE_ROOT
from .season_cache import SleeperSeasonCache

from .metadata import minimal_metadata_store

sleeper_season_cache = SleeperSeasonCache(SLEEPER_SEASON_CACHE_ROOT)


def _digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


class CanonicalHistoryStore:
    """Read model over disposable Sleeper facts and current operational state."""

    def __init__(self) -> None:
        self.path: Path = minimal_metadata_store.path
        self._lock = RLock()
        self._current: dict[str, dict[str, Any]] = {}
        self._current_digests: dict[str, str] = {}
        self._identities: dict[str, dict[str, Any]] = {}
        self._relevance: dict[str, dict[str, tuple[str, ...]]] = {}
        self._generation = 0
        self._dataset_metrics = {"point_queries": 0, "archive_scans": 0}

    def update_current(self, league_id: str, data: dict[str, Any]) -> None:
        """Replace bounded operational state; no historical snapshots are appended."""
        identities = {}
        for player_id, player in (data.get("normalized_players") or {}).items():
            identities[str(player_id)] = {
                "dtos_player_id": str(player_id), "provider": "Sleeper",
                "provider_player_id": str(player_id),
                "display_name": str(player.get("name") or player_id),
                "confidence": 100, "metadata": {
                    "position": player.get("position"),
                    "team": player.get("team"),
                    "provider_ids": player.get("provider_ids") or {},
                },
            }
        key = str(league_id)
        semantic = _digest({
            "league": data.get("league") or {}, "teams": data.get("teams") or [],
            "players": identities, "projections": data.get("projection_intelligence") or {},
            "valuation": data.get("valuation_intelligence") or {},
            "market": data.get("market_data") or {},
        })
        with self._lock:
            self._current[key] = data
            self._identities.update(identities)
            if self._current_digests.get(key) != semantic:
                self._current_digests[key] = semantic
                self._generation += 1

    def database_uuid(self) -> str:
        return minimal_metadata_store.database_uuid()

    def database_identity(self) -> tuple[int, int, str]:
        stat = self.path.stat()
        return (int(stat.st_dev), int(stat.st_ino), self.database_uuid())

    def dataset_version(self, league_id: str | None = None) -> str:
        with self._lock:
            current = self._current.get(str(league_id), {}) if league_id else self._current
            generation = self._generation
            self._dataset_metrics["point_queries"] += 1
        cache = self._cache_index(str(league_id)) if league_id else {}
        return _digest({
            "league": str(league_id or "global"), "operational": generation,
            "current": {
                "league": (current.get("league") or {}).get("league_id")
                if isinstance(current, dict) else None,
                "semantic": self._current_digests.get(str(league_id)),
            },
            "completed_seasons": cache,
        })

    def dataset_version_metrics(self) -> dict[str, int]:
        return dict(self._dataset_metrics)

    def semantic_generations(self, league_id: str | None = None) -> dict[str, int]:
        return {
            "provider_cache": len(self._cache_index(str(league_id))) if league_id else 0,
            "operational_context": self._generation,
            "quality_reconciliation": 0,
        }

    def identity_generations(self) -> dict[str, int]:
        return {"mapping": self._generation, "observations": self._generation}

    def _cache_index(self, league_id: str) -> dict[int, str]:
        result = {}
        for season in sleeper_season_cache.available_seasons(league_id):
            cached = sleeper_season_cache.read(league_id, season)
            if cached is not None:
                result[season] = cached.checksum
        return result

    def _facts(self, league_id: str, season: int) -> dict[str, Any] | None:
        cached = sleeper_season_cache.read(league_id, season)
        return cached.facts if cached else None

    @staticmethod
    def _record(
        league_id: str, season: int, entity: str, source_id: str,
        payload: dict[str, Any], *, week: int | None = None,
        player_id: str | None = None, franchise_id: str | None = None,
        provider: str = "Sleeper",
    ) -> dict[str, Any]:
        return {
            "record_key": f"cache:{league_id}:{season}:{entity}:{source_id}",
            "entity_type": entity, "league_id": league_id, "season": season,
            "week": week, "franchise_id": franchise_id, "player_id": player_id,
            "source_record_id": str(source_id), "observed_at": None,
            "retrieved_at": None, "provider": provider,
            "availability": "observed", "confidence": 100,
            "calculation_method": "sleeper_season_cache", "derived": False,
            "schema_version": "provider-cache-1", "payload": payload,
        }

    def _season_records(self, league_id: str, season: int) -> list[dict[str, Any]]:
        facts = self._facts(league_id, season)
        if not facts:
            return []
        league = facts.get("league") or {}
        rows = [self._record(league_id, season, "league_season", league_id, {
            "league_name": league.get("name") or "Sleeper League",
            "total_rosters": league.get("total_rosters"),
            "settings": league.get("settings") or {},
            "scoring_settings": league.get("scoring_settings") or {},
            "roster_positions": league.get("roster_positions") or [],
        })]
        users = {str(row.get("user_id")): row for row in facts.get("users") or []}
        rosters = facts.get("rosters") or []
        for roster in rosters:
            roster_id = int(roster.get("roster_id") or 0)
            owner_id = str(roster.get("owner_id") or "")
            user = users.get(owner_id, {})
            franchise = f"{league_id}:franchise:{roster_id}"
            rows.append(self._record(league_id, season, "franchise_identity", str(roster_id), {
                "sleeper_roster_id": roster_id, "owner_id": owner_id,
                "sleeper_username": user.get("display_name") or user.get("username"),
                "dtos_display_name": (user.get("metadata") or {}).get("team_name")
                or user.get("display_name") or f"Roster {roster_id}",
                "franchise_id": franchise,
            }, franchise_id=franchise))
            settings = roster.get("settings") or {}
            rows.append(self._record(league_id, season, "season_standing", str(roster_id), {
                "roster_id": roster_id, "wins": settings.get("wins"),
                "losses": settings.get("losses"), "ties": settings.get("ties"),
                "points_for": settings.get("fpts"), "points_against": settings.get("fpts_against"),
                "rank": settings.get("rank"),
            }, franchise_id=franchise))
        for week_key, matchups in (facts.get("matchups") or {}).items():
            week = int(week_key)
            grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in matchups or []:
                grouped[int(row.get("matchup_id") or 0)].append(row)
                points = row.get("players_points") or {}
                starters = set(map(str, row.get("starters") or ()))
                roster_id = int(row.get("roster_id") or 0)
                for player_id, score in points.items():
                    rows.append(self._record(
                        league_id, season, "player_week",
                        f"{week}:{roster_id}:{player_id}",
                        {"fantasy_points": score, "points": score,
                         "starter": str(player_id) in starters, "roster_id": roster_id},
                        week=week, player_id=str(player_id),
                        franchise_id=f"{league_id}:franchise:{roster_id}",
                    ))
            for matchup_id, sides in grouped.items():
                scores = {str(side.get("roster_id")): side.get("points") for side in sides}
                ordered = sorted(sides, key=lambda side: float(side.get("points") or 0), reverse=True)
                winner = ordered[0].get("roster_id") if len(ordered) > 1 and ordered[0].get("points") != ordered[1].get("points") else None
                rows.append(self._record(league_id, season, "matchup", f"{week}:{matchup_id}", {
                    "matchup_id": matchup_id,
                    "franchises": [side.get("roster_id") for side in sides],
                    "team_points": scores, "winner": winner,
                    "loser": ordered[-1].get("roster_id") if winner else None,
                    "tie": winner is None, "postseason_context": False,
                }, week=week))
        for week_key, transactions in (facts.get("transactions") or {}).items():
            week = int(week_key)
            for transaction in transactions or []:
                transaction_id = str(transaction.get("transaction_id") or _digest(transaction)[:16])
                payload = dict(transaction)
                payload.setdefault("roster_ids", transaction.get("roster_ids") or [])
                entity = "trade" if transaction.get("type") == "trade" else "transaction"
                rows.append(self._record(league_id, season, entity, transaction_id, payload, week=week))
        for draft in facts.get("drafts") or []:
            draft_id = str(draft.get("draft_id") or _digest(draft)[:16])
            rows.append(self._record(league_id, season, "draft", draft_id, dict(draft)))
        for pick in facts.get("draft_picks") or []:
            pick_id = str(pick.get("pick_no") or pick.get("pick_id") or _digest(pick)[:16])
            rows.append(self._record(league_id, season, "draft_pick", pick_id, dict(pick), player_id=str(pick.get("player_id") or "") or None))
        brackets = []
        for bracket_name in ("winners_bracket", "losers_bracket"):
            for row in facts.get(bracket_name) or []:
                payload = {**row, "bracket": bracket_name}
                rows.append(self._record(league_id, season, "playoff_bracket", f"{bracket_name}:{row.get('m')}", payload))
                brackets.append(payload)
        championship = next((row for row in brackets if row.get("p") == 1), None)
        if championship:
            rows.append(self._record(league_id, season, "playoff_result", "final", {
                "champion_roster_id": championship.get("w"),
                "runner_up_roster_id": championship.get("l"),
                "placements": {"1": championship.get("w"), "2": championship.get("l")},
            }))
        return rows

    def records(
        self, league_id: str, entity_type: str | None, *, season: int | None = None,
        week: int | None = None, franchise_id: str | None = None,
        player_id: str | None = None, limit: int = 100, offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        seasons = [season] if season is not None else sorted(self._cache_index(league_id), reverse=True)
        rows = [row for selected in seasons for row in self._season_records(league_id, selected)]
        rows = [row for row in rows if (
            (entity_type is None or row["entity_type"] == entity_type)
            and (week is None or row["week"] == week)
            and (franchise_id is None or row["franchise_id"] == franchise_id)
            and (player_id is None or row["player_id"] == player_id)
        )]
        return len(rows), rows[offset:offset + limit]

    def identities(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._identities.values())

    def identity_for_provider_id(self, provider_player_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._identities.get(str(provider_player_id))

    def identity_positions(self) -> dict[str, str]:
        return {
            key: str((row.get("metadata") or {}).get("position") or "")
            for key, row in self._identities.items()
        }

    def persist_relevant_player_universe(self, league_id: str, rows: Iterable[dict[str, Any]], generation: str, updated_at: str) -> None:
        with self._lock:
            self._relevance[str(league_id)] = {
                str(row["player_id"]): tuple(row.get("reason_codes") or ()) for row in rows
            }

    def relevant_player_reasons(self, league_id: str) -> dict[str, set[str]]:
        with self._lock:
            result = {
                player_id: set(reasons)
                for player_id, reasons in self._relevance.get(str(league_id), {}).items()
            }
        # Completed-season transaction and matchup membership is rebuilt from
        # provider cache; it is not persisted as a historical universe.
        for season in self._cache_index(league_id):
            for row in self._season_records(league_id, season):
                if row.get("player_id"):
                    result.setdefault(str(row["player_id"]), set()).add("historical_matchup")
                if row["entity_type"] in {"trade", "transaction"}:
                    payload = row.get("payload") or {}
                    for key in ("adds", "drops"):
                        values = payload.get(key) or {}
                        for value in values if isinstance(values, list) else values.keys():
                            result.setdefault(str(value), set()).add("historical_transaction")
        return result

    def import_active(self, league_id: str) -> bool:
        return False

    def quality(self, league_id: str) -> list[dict[str, Any]]:
        return []

    def latest_completed_foundation(self, league_id: str) -> dict[str, Any] | None:
        seasons = self._cache_index(league_id)
        return {"status": "complete", "run_id": "sleeper-cache", "completed_at": None} if seasons else None

    def season_player_leaders(self, league_id: str, season: int, limit: int = 40) -> tuple[int, list[dict[str, Any]]]:
        count, rows = self.records(league_id, "player_week", season=season, limit=1_000_000)
        totals: dict[str, float] = defaultdict(float)
        for row in rows:
            totals[str(row["player_id"])] += float(row["payload"].get("fantasy_points") or 0)
        ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return count, [{"player_id": player_id, "points": points,
                        "display_name": (self._identities.get(player_id) or {}).get("display_name"),
                        "position": (self._identities.get(player_id) or {}).get("metadata", {}).get("position")}
                       for player_id, points in ranked]

    def distinct_player_ids(self, league_id: str) -> list[str]:
        values = set(self._identities)
        for season in self._cache_index(league_id):
            _, rows = self.records(league_id, "player_week", season=season, limit=1_000_000)
            values.update(str(row["player_id"]) for row in rows if row.get("player_id"))
        return sorted(values)

    def distinct_pick_ids(self, league_id: str) -> list[str]:
        _, rows = self.records(league_id, "draft_pick", limit=1_000_000)
        return sorted({str(row["source_record_id"]) for row in rows})

    def search_player_ids(self, league_id: str, needle: str, limit: int) -> list[str]:
        query = needle.casefold()
        return [row["dtos_player_id"] for row in self.identities()
                if query in str(row.get("display_name") or "").casefold()][:limit]

    def search_transaction_ids(self, league_id: str, needle: str, limit: int) -> list[str]:
        _, rows = self.records(league_id, None, limit=1_000_000)
        query = needle.casefold()
        return [str(row["source_record_id"]) for row in rows
                if row["entity_type"] in {"trade", "transaction"}
                and query in json.dumps(row["payload"], default=str).casefold()][:limit]

    def transaction_record(self, league_id: str, transaction_id: str) -> dict[str, Any] | None:
        _, rows = self.records(league_id, None, limit=1_000_000)
        return next((row for row in rows if row["entity_type"] in {"trade", "transaction"}
                     and str(row["source_record_id"]) == str(transaction_id)), None)

    def discoverable_trade_records(self, league_id: str) -> list[dict[str, Any]]:
        _, rows = self.records(league_id, "trade", limit=1_000_000)
        return rows

    def asset_event_records(self, league_id: str, asset_id: str) -> list[dict[str, Any]]:
        _, rows = self.records(league_id, None, limit=1_000_000)
        return [row for row in rows if row.get("player_id") == asset_id
                or asset_id in json.dumps(row.get("payload") or {}, default=str)]

    def player_week_totals(self, league_id: str) -> dict[int, dict[str, float]]:
        _, rows = self.records(league_id, "player_week", limit=1_000_000)
        result: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for row in rows:
            result[int(row["season"])][str(row["player_id"])] += float(row["payload"].get("fantasy_points") or 0)
        return {season: dict(players) for season, players in result.items()}

    def entity_counts_by_season(self, league_id: str) -> tuple[list[int], dict[int, dict[str, int]]]:
        counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for season in self._cache_index(league_id):
            for row in self._season_records(league_id, season):
                counts[season][row["entity_type"]] += 1
        return sorted(counts), {season: dict(values) for season, values in counts.items()}

    def compact_event_statistics(self, league_id: str) -> dict[str, Any]:
        seasons, counts = self.entity_counts_by_season(league_id)
        return {"seasons": seasons, "counts": counts, "source": "sleeper_season_cache"}

    def compact_identity_coverage(self, league_id: str) -> dict[str, Any]:
        return {"canonical": len(self._identities), "unresolved": 0, "source": "operational_catalog"}


canonical_history_store = CanonicalHistoryStore()
