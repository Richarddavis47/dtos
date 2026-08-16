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
from .timestamps import canonical_transaction_timestamp

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

    def season_chain(self, league_id: str) -> dict[str, Any] | None:
        """Return the compact durable discovery manifest for progress surfaces."""
        return minimal_metadata_store.season_chain(league_id)

    def _facts(self, league_id: str, season: int) -> dict[str, Any] | None:
        cached = sleeper_season_cache.read(league_id, season)
        return cached.facts if cached else None

    @staticmethod
    def _record(
        league_id: str, season: int, entity: str, source_id: str,
        payload: dict[str, Any], *, week: int | None = None,
        player_id: str | None = None, franchise_id: str | None = None,
        provider: str = "Sleeper", occurred_at: str | None = None,
        timestamp_provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "record_key": f"cache:{league_id}:{season}:{entity}:{source_id}",
            "entity_type": entity, "league_id": league_id, "season": season,
            "week": week, "franchise_id": franchise_id, "player_id": player_id,
            "source_record_id": str(source_id), "occurred_at": occurred_at,
            "observed_at": None,
            "retrieved_at": None, "provider": provider,
            "availability": "observed", "confidence": 100,
            "calculation_method": "sleeper_season_cache", "derived": False,
            "schema_version": "provider-cache-1", "payload": payload,
            "timestamp_provenance": timestamp_provenance,
        }

    def _season_records(self, league_id: str, season: int) -> list[dict[str, Any]]:
        facts = self._facts(league_id, season)
        if not facts:
            return []
        league = facts.get("league") or {}
        rows = [self._record(league_id, season, "league_season", league_id, {
            "league_name": league.get("name") or "Sleeper League",
            "status": league.get("status"),
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
                occurred_at, timestamp_provenance = canonical_transaction_timestamp(payload)
                rows.append(self._record(
                    league_id, season, entity, transaction_id, payload, week=week,
                    occurred_at=occurred_at,
                    timestamp_provenance=timestamp_provenance,
                ))
        for draft in facts.get("drafts") or []:
            draft_id = str(draft.get("draft_id") or _digest(draft)[:16])
            rows.append(self._record(league_id, season, "draft", draft_id, dict(draft)))
        for pick in facts.get("draft_picks") or []:
            pick_id = str(pick.get("pick_no") or pick.get("pick_id") or _digest(pick)[:16])
            rows.append(self._record(league_id, season, "draft_pick", pick_id, dict(pick), player_id=str(pick.get("player_id") or "") or None))
        for pick in facts.get("traded_picks") or []:
            source_id = str(pick.get("pick_id") or _digest(pick)[:16])
            rows.append(self._record(
                league_id, season, "pick_snapshot", source_id, dict(pick),
            ))
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

    @staticmethod
    def _canonical_pick_id(payload: dict[str, Any], season: int) -> str | None:
        pick_season = payload.get("season") or season
        round_number = payload.get("round")
        original_roster = (
            payload.get("roster_id") or payload.get("original_roster_id")
            or payload.get("original_franchise")
        )
        if round_number in (None, "") or original_roster in (None, ""):
            return None
        return f"PICK-{pick_season}-R{round_number}-ORIG{original_roster}"

    def distinct_pick_ids(self, league_id: str) -> list[str]:
        _, rows = self.records(league_id, None, limit=1_000_000)
        picks: set[str] = set()
        for row in rows:
            payload = row.get("payload") or {}
            candidates = (
                payload.get("draft_picks") or []
                if row["entity_type"] in {"transaction", "trade"}
                else [payload] if row["entity_type"] in {"draft_pick", "pick_snapshot"}
                else []
            )
            for candidate in candidates:
                pick_id = self._canonical_pick_id(candidate, int(row["season"]))
                if pick_id:
                    picks.add(pick_id)
        return sorted(picks)

    def search_player_ids(self, league_id: str, needle: str, limit: int) -> list[str]:
        query = needle.casefold()
        matches = {
            str(row["provider_player_id"])
            for row in self.identities()
            if query in str(row.get("provider_player_id") or "").casefold()
            or query in str(row.get("display_name") or "").casefold()
        }
        for season in self._cache_index(league_id):
            for row in self._season_records(league_id, season):
                player_id = row.get("player_id")
                if player_id is not None and query in str(player_id).casefold():
                    matches.add(str(player_id))
        return sorted(matches)[:limit]

    def search_transaction_ids(self, league_id: str, needle: str, limit: int) -> list[dict[str, Any]]:
        _, rows = self.records(league_id, None, limit=1_000_000)
        query = needle.casefold()
        matches = [row for row in rows
                   if row["entity_type"] in {"trade", "transaction"}
                   and query in str(row["source_record_id"]).casefold()]
        matches.sort(key=lambda row: (
            int(row["season"]), int(row.get("week") or 0),
            str(row.get("observed_at") or ""), str(row["source_record_id"]),
        ), reverse=True)
        return matches[:limit]

    def transaction_record(self, league_id: str, transaction_id: str) -> dict[str, Any] | None:
        _, rows = self.records(league_id, None, limit=1_000_000)
        return next((row for row in rows if row["entity_type"] in {"trade", "transaction"}
                     and str(row["source_record_id"]) == str(transaction_id)), None)

    def discoverable_trade_records(self, league_id: str, limit: int = 3) -> list[dict[str, Any]]:
        _, rows = self.records(league_id, "trade", limit=1_000_000)
        rows = [row for row in rows if str(
            (row.get("payload") or {}).get("status") or "",
        ).casefold() in {"complete", "completed"}]
        rows.sort(key=lambda row: (
            int(row["season"]), int(row.get("week") or 0),
            str(row.get("observed_at") or ""), str(row["source_record_id"]),
        ), reverse=True)
        return rows[:limit]

    def asset_event_records(
        self, league_id: str, asset_id: str,
    ) -> dict[str, list[dict[str, Any]]]:
        entity_types = (
            "draft_pick", "transaction", "trade", "pick_snapshot",
            "weekly_roster", "draft",
        )
        result = {entity_type: [] for entity_type in entity_types}
        _, rows = self.records(league_id, None, limit=1_000_000)
        if asset_id.startswith("DTOS-P-"):
            player_id = asset_id.removeprefix("DTOS-P-")
            selected = [row for row in rows if (
                (row["entity_type"] == "draft_pick" and row.get("player_id") == player_id)
                or (row["entity_type"] in {"transaction", "trade"} and (
                    player_id in (row["payload"].get("adds") or {})
                    or player_id in (row["payload"].get("drops") or {})
                ))
                or (row["entity_type"] == "weekly_roster" and player_id in {
                    *map(str, row["payload"].get("starters") or ()),
                    *map(str, row["payload"].get("bench") or ()),
                })
            )]
        elif asset_id.startswith("PICK-"):
            selected = []
            for row in rows:
                payload = row.get("payload") or {}
                if row["entity_type"] in {"draft_pick", "pick_snapshot"}:
                    if self._canonical_pick_id(payload, int(row["season"])) == asset_id:
                        selected.append(row)
                elif row["entity_type"] in {"transaction", "trade"} and any(
                    self._canonical_pick_id(pick, int(row["season"])) == asset_id
                    for pick in payload.get("draft_picks") or []
                ):
                    selected.append(row)
        else:
            selected = []
        selected.extend(row for row in rows if row["entity_type"] == "draft")
        selected.sort(key=lambda row: (
            -int(row["season"]), -int(row.get("week") or 0),
            str(row["entity_type"]), str(row["source_record_id"]),
        ))
        for row in selected:
            result[row["entity_type"]].append(row)
        return result

    def player_week_totals(self, league_id: str) -> dict[int, dict[str, float]]:
        _, rows = self.records(league_id, "player_week", limit=1_000_000)
        result: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for row in rows:
            result[int(row["season"])][str(row["player_id"])] += float(row["payload"].get("fantasy_points") or 0)
        return {season: dict(players) for season, players in result.items()}

    def entity_counts_by_season(
        self, league_id: str, entity_types: Iterable[str] | str | None = None,
    ) -> tuple[list[int], dict[str, dict[str, int]]]:
        """Return per-season counts using the legacy read-contract shape."""
        requested = (
            (str(entity_types),)
            if isinstance(entity_types, str)
            else tuple(str(value) for value in entity_types or ())
        )
        selected = set(requested)
        counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for season in self._cache_index(league_id):
            for row in self._season_records(league_id, season):
                entity_type = str(row["entity_type"])
                if not selected or entity_type in selected:
                    counts[season][entity_type] += 1
        seasons = sorted(counts)
        return seasons, {
            str(season): {
                entity_type: int(counts[season].get(entity_type, 0))
                for entity_type in (requested or tuple(sorted(counts[season])))
            }
            for season in seasons
        }

    def compact_event_statistics(self, league_id: str) -> dict[str, Any]:
        event_ids: list[str] = []

        def append_event_id(row: dict[str, Any], suffix: str = "") -> None:
            source = "|".join(str(value) for value in (
                league_id, row["entity_type"], row["season"], row.get("week") or "",
                row["source_record_id"], suffix,
            ))
            event_ids.append("EVENT-" + hashlib.sha256(source.encode()).hexdigest()[:24].upper())

        orphaned_events = 0
        for season in self._cache_index(league_id):
            for row in self._season_records(league_id, season):
                payload = row.get("payload") or {}
                if row["entity_type"] == "draft_pick" and row.get("player_id"):
                    append_event_id(row)
                    append_event_id(row, str(row["player_id"]))
                elif row["entity_type"] in {"transaction", "trade"}:
                    for player, roster in (payload.get("adds") or {}).items():
                        append_event_id(row, f"add:{player}:{roster}")
                    for player, roster in (payload.get("drops") or {}).items():
                        append_event_id(row, f"drop:{player}:{roster}")
                    for index, _pick in enumerate(payload.get("draft_picks") or []):
                        append_event_id(row, f"pick:{index}")
                        if not row.get("source_record_id"):
                            orphaned_events += 1
                elif row["entity_type"] == "pick_snapshot":
                    append_event_id(row)
                elif row["entity_type"] == "weekly_roster":
                    players = dict.fromkeys([
                        *(payload.get("starters") or []), *(payload.get("bench") or []),
                    ])
                    for player in players:
                        append_event_id(row, f"snapshot:{player}")
        return {
            "asset_event_count": len(event_ids),
            "duplicate_event_ids": len(event_ids) - len(set(event_ids)),
            "orphaned_events": orphaned_events,
        }

    def compact_identity_coverage(self, league_id: str) -> dict[str, Any]:
        historical_player_ids: set[str] = set()
        for season in self._cache_index(league_id):
            for row in self._season_records(league_id, season):
                if row["entity_type"] in {"player_week", "draft_pick"} and row.get("player_id"):
                    historical_player_ids.add(str(row["player_id"]))
        with self._lock:
            resolved_provider_ids = {
                str(identity.get("provider_player_id"))
                for identity in self._identities.values()
                if int(identity.get("confidence") or 0) >= 70
                and identity.get("provider_player_id") is not None
            }
        resolved = historical_player_ids & resolved_provider_ids
        unresolved = sorted(historical_player_ids - resolved)
        return {
            "resolved_identity_count": len(resolved),
            "unresolved_identity_count": len(unresolved),
            "unresolved_player_ids": unresolved,
            "historical_player_ids": sorted(historical_player_ids),
            "resolved_provider_ids": sorted(resolved),
        }


canonical_history_store = CanonicalHistoryStore()
