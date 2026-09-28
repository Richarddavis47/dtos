"""Sleeper-cache-backed canonical history contract.

This intentionally resembles the bounded read surface formerly supplied by
``HistoricalStore`` so consumers can migrate without retaining a SQLite
provider archive. It never opens the dormant legacy database.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from config import SLEEPER_SEASON_CACHE_ROOT
from .season_cache import SleeperSeasonCache
from .timestamps import canonical_transaction_timestamp, canonical_draft_bounds
from .playoffs import playoff_facts

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

    def release_current(self, league_id: str, expected_data: dict[str, Any]) -> None:
        """Release an evicted runtime, without deleting provider facts/checkpoints.

        Identity comparison prevents a late close from removing a newer runtime.
        Public player identities remain shared independently of league residency.
        """
        key = str(league_id)
        with self._lock:
            if self._current.get(key) is not expected_data:
                return
            self._current.pop(key, None)
            self._current_digests.pop(key, None)
            self._relevance.pop(key, None)

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
        from .recovery import HistoricalCheckpoints
        return {**HistoricalCheckpoints(sleeper_season_cache.root).index(league_id),
                **sleeper_season_cache.checksum_index(league_id)}

    def preserve_reader_checkpoint(self, league_id: str, season: int, *, current_season: int) -> bool:
        """Explicit prerequisite, not authorization to evict a whole season."""
        from .recovery import HistoricalCheckpoints, HistoricalRecoveryUnavailable
        cached = sleeper_season_cache.read(league_id, season)
        if cached is None or season >= current_season - 1:
            raise HistoricalRecoveryUnavailable('Missing cache or protected current/prior season')
        source = cached.facts.get('league') or {}
        if int(source.get('season') or 0) != int(season):
            raise HistoricalRecoveryUnavailable('Provider season identity mismatch')
        if cached.completeness.get('league') != 'available':
            raise HistoricalRecoveryUnavailable('Incomplete historical checkpoint inputs')
        families = self._supported_families(cached)
        return HistoricalCheckpoints(sleeper_season_cache.root).preserve(
            league=league_id, season=season, source_league=source.get('league_id'),
            source_checksum=cached.checksum, records=self._season_records(league_id, season), families=families)

    @staticmethod
    def _supported_families(cached) -> set[str]:
        """One availability contract for provider cache and compact recovery."""
        families = {'league_season'}
        users, rosters = cached.facts.get('users'), cached.facts.get('rosters')
        valid_users = (
            cached.completeness.get('users') == 'available'
            and isinstance(users, list) and all(
                isinstance(row, dict) and str(row.get('user_id') or '')
                for row in users
            )
            and len({str(row['user_id']) for row in users}) == len(users)
        )
        valid_rosters = (cached.completeness.get('rosters') == 'available'
                         and isinstance(rosters, list) and all(isinstance(row, dict) for row in rosters))
        owners = {str(row.get('owner_id') or '') for row in rosters or ()
                  if isinstance(row, dict) and row.get('owner_id')}
        if valid_users and valid_rosters and owners <= {str(row['user_id']) for row in users}:
            families.add('franchise_identity')
        if cached.completeness.get('rosters') == 'available':
            families.update(('season_standing', 'roster_snapshot'))
        if cached.completeness.get('matchups') == 'available':
            families.update(('player_week', 'matchup'))
        if cached.completeness.get('transactions') == 'available':
            families.update(('trade', 'transaction'))
        if cached.completeness.get('drafts') == 'available':
            families.add('draft')
        if cached.completeness.get('draft_picks') == 'available':
            families.add('draft_pick')
        if cached.completeness.get('traded_picks') == 'available':
            families.add('pick_snapshot')
        if (cached.completeness.get('winners_bracket') == 'available'
                and cached.completeness.get('losers_bracket') == 'available'):
            families.add('playoff_bracket')
        if cached.completeness.get('winners_bracket') == 'available':
            families.add('playoff_result')
        return families

    def historical_availability(self, league_id: str, season: int) -> dict[str, Any]:
        from .recovery import HistoricalCheckpoints
        cached = sleeper_season_cache.read(league_id, season)
        if cached is not None:
            return {'state': 'cached', 'covered_families': sorted(self._supported_families(cached))}
        checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
        return {'state': 'partial' if checkpoint else 'unavailable',
                'covered_families': checkpoint['families'] if checkpoint else [],
                'reason': 'compact_canonical_checkpoint' if checkpoint else 'historical_recovery_required'}

    def recovered_season_source(self, league_id: str, season: int):
        """Rebuild the bounded weekly-report source surface from canonical rows.

        This is not the raw provider season and is used only when that cache is
        absent. Missing families stay absent so consumers report partial state.
        """
        from .recovery import HistoricalCheckpoints
        from .season_cache import CachedSeason
        checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
        if checkpoint is None:
            return None
        families, rows = set(checkpoint['families']), checkpoint['records']
        required = {'league_season', 'franchise_identity', 'roster_snapshot', 'matchup', 'player_week'}
        if not required <= families:
            return None
        by_type = {kind: [row for row in rows if row['entity_type'] == kind] for kind in families}
        league_payload = by_type['league_season'][0]['payload']
        source_league = checkpoint['source_league_id']
        league = {
            'league_id': source_league, 'season': str(season),
            'name': league_payload.get('league_name'), 'status': league_payload.get('status'),
            'total_rosters': league_payload.get('total_rosters'),
            'settings': league_payload.get('settings') or {},
            'scoring_settings': league_payload.get('scoring_settings') or {},
            'roster_positions': league_payload.get('roster_positions') or [],
        }
        roster_rows = {int(row['payload']['roster_id']): row['payload'] for row in by_type['roster_snapshot']}
        rosters = [{**payload, 'roster_id': rid} for rid, payload in roster_rows.items()]
        player_weeks = {}
        for row in by_type['player_week']:
            payload = row['payload']
            key = (int(row['week']), int(payload['roster_id']))
            player_weeks.setdefault(key, []).append((str(row['player_id']), payload))
        matchups = {}
        for row in by_type['matchup']:
            payload, week = row['payload'], int(row['week'])
            for rid in payload.get('franchises') or ():
                rid = int(rid)
                players = player_weeks.get((week, rid), [])
                points = {player: item.get('fantasy_points') for player, item in players}
                matchups.setdefault(str(week), []).append({
                    'roster_id': rid, 'matchup_id': payload.get('matchup_id'),
                    'points': (payload.get('team_points') or {}).get(str(rid)),
                    'players': list(points), 'players_points': points,
                    'starters': [player for player, item in players if item.get('starter')],
                })
        facts = {'league': league, 'rosters': rosters, 'matchups': matchups}
        if {'trade', 'transaction'} & families:
            transactions = {}
            for kind in ('trade', 'transaction'):
                for row in by_type.get(kind, []):
                    transactions.setdefault(str(row.get('week') or 0), []).append(row['payload'])
            facts['transactions'] = transactions
        if 'playoff_bracket' in families:
            for name in ('winners_bracket', 'losers_bracket'):
                facts[name] = [{key: value for key, value in row['payload'].items() if key != 'bracket'}
                               for row in by_type[name and 'playoff_bracket']
                               if row['payload'].get('bracket') == name]
        completeness = {key: ('available' if key in facts else 'unavailable') for key in (
            'league', 'users', 'rosters', 'matchups', 'transactions', 'drafts',
            'draft_picks', 'traded_picks', 'winners_bracket', 'losers_bracket')}
        return CachedSeason(str(league_id), int(season), 'partial', completeness, facts,
                            checkpoint['source_checksum'])

    async def recover_historical_season(self, league_id: str, season: int, fetch_facts) -> dict[str, Any]:
        """Explicit preparation boundary; never fetch on synchronous page reads."""
        from .recovery import HistoricalCheckpoints, HistoricalRecoveryUnavailable
        from src.platform.cache_budget import CacheAdmissionError
        import httpx
        checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
        if checkpoint is None:
            return self.historical_availability(league_id, season)
        try:
            facts = await fetch_facts(checkpoint['source_league_id'], int(season))
            source = (facts or {}).get('league') or {}
            if str(source.get('league_id')) != checkpoint['source_league_id'] or int(source.get('season') or 0) != int(season):
                raise HistoricalRecoveryUnavailable('Upstream historical scope unavailable')
            rebuilt = sleeper_season_cache.normalize(league_id, season, facts)
            if rebuilt.checksum != checkpoint['source_checksum']:
                raise HistoricalRecoveryUnavailable('Upstream differs from preserved historical boundary')
            sleeper_season_cache.write(rebuilt)
        except (OSError, ValueError, CacheAdmissionError, httpx.HTTPError) as exc:
            return {**self.historical_availability(league_id, season), 'recovery_error': type(exc).__name__}
        return self.historical_availability(league_id, season)

    async def publish_with_verified_turnover(
        self, league_id: str, current_season: int, incoming, fetch_facts,
    ) -> dict[str, Any]:
        """Publish one raw cache entry after exact oldest-first turnover proof.

        This is an explicit background-preparation operation. It is not called
        by page reads and is not enabled against production by this change.
        """
        from src.core.history_context.recovery import HistoricalCheckpoints, HistoricalRecoveryUnavailable
        from src.platform.cache_budget import SEASON_COUNT, SEASON_LEAGUE_BYTES
        if incoming.league_id != str(league_id):
            raise HistoricalRecoveryUnavailable('Incoming cache league mismatch')
        seasons = list(sleeper_season_cache.available_seasons(league_id))
        existing = incoming.season in seasons
        current_bytes = sum(sleeper_season_cache.path(league_id, value).stat().st_size for value in seasons)
        replacing = sleeper_season_cache.path(league_id, incoming.season).stat().st_size if existing else 0
        incoming_bytes = sleeper_season_cache.encoded_size(incoming)
        candidates = [value for value in seasons if value < int(current_season) - 1 and value != incoming.season]
        planned = []
        planned_bytes = current_bytes
        planned_count = len(seasons)
        while ((planned_count + (0 if existing else 1) > SEASON_COUNT)
               or planned_bytes - replacing + incoming_bytes > SEASON_LEAGUE_BYTES):
            if not candidates:
                raise HistoricalRecoveryUnavailable('No verified old cache is eligible for turnover')
            season = candidates.pop(0)
            cached = sleeper_season_cache.read(league_id, season)
            if cached is None:
                raise HistoricalRecoveryUnavailable('Turnover candidate disappeared')
            self.preserve_reader_checkpoint(league_id, season, current_season=current_season)
            checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
            facts = await fetch_facts(checkpoint['source_league_id'], season)
            rebuilt = sleeper_season_cache.normalize(league_id, season, facts or {})
            if not facts or rebuilt.checksum != cached.checksum or rebuilt.checksum != checkpoint['source_checksum']:
                raise HistoricalRecoveryUnavailable('Exact upstream rebuild proof failed')
            size = sleeper_season_cache.path(league_id, season).stat().st_size
            planned.append({'season': season, 'raw_bytes': size, 'source_checksum': cached.checksum,
                            'checkpoint_bytes': HistoricalCheckpoints(sleeper_season_cache.root).path(league_id, season).stat().st_size})
            planned_count -= 1
            planned_bytes -= size
        # All candidates have exact source/checkpoint proof before the first
        # cache is removed. A failed proof above leaves every raw cache intact.
        sleeper_season_cache.write(incoming, verified_evictions={
            item['season']: item['source_checksum'] for item in planned})
        return {'evicted': planned, 'retained_raw_seasons': list(sleeper_season_cache.available_seasons(league_id)),
                'raw_bytes': sum(sleeper_season_cache.path(league_id, value).stat().st_size
                                 for value in sleeper_season_cache.available_seasons(league_id)),
                'maximum_raw_seasons': SEASON_COUNT, 'maximum_raw_bytes': SEASON_LEAGUE_BYTES}

    def season_chain(self, league_id: str) -> dict[str, Any] | None:
        """Return the compact durable discovery manifest for progress surfaces."""
        return minimal_metadata_store.season_chain(league_id)

    def _facts(self, league_id: str, season: int) -> dict[str, Any] | None:
        cached = sleeper_season_cache.read(league_id, season)
        return cached.facts if cached else None

    def ownership_observations(self, league_id: str) -> dict[str, Any]:
        """Background reconciliation over canonical records; no provider reads."""
        from .ownership import reconcile_ownership
        seasons = []
        for season in sorted(self._cache_index(str(league_id))):
            _, league_rows = self.records(league_id, 'league_season', season=season, limit=1)
            _, roster_rows = self.records(league_id, 'roster_snapshot', season=season, limit=None)
            if league_rows and roster_rows:
                league = league_rows[0]['payload']
                seasons.append({'league': {
                    'league_id': league.get('sleeper_season_league_id') or league_id,
                    'previous_league_id': league.get('previous_league_id'), 'season': season,
                }, 'rosters': [{
                    'roster_id': row['payload'].get('roster_id'),
                    'owner_id': row['payload'].get('owner_id'),
                    'co_owners': row['payload'].get('co_owners') or [],
                } for row in roster_rows]})
        return reconcile_ownership(seasons)

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
        from .results import matchup_result, standing_points
        facts = self._facts(league_id, season)
        if not facts:
            from .recovery import HistoricalCheckpoints
            checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
            return checkpoint['records'] if checkpoint else []
        league = facts.get("league") or {}
        rows = [self._record(league_id, season, "league_season", league_id, {
            "sleeper_season_league_id": league.get("league_id"),
            "previous_league_id": league.get("previous_league_id"),
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
                "co_owners": list(map(str, roster.get("co_owners") or ())),
                "sleeper_username": user.get("display_name") or user.get("username"),
                "dtos_display_name": (user.get("metadata") or {}).get("team_name")
                or user.get("display_name") or f"Roster {roster_id}",
                "franchise_id": franchise,
            }, franchise_id=franchise))
            rows.append(self._record(
                league_id, season, "roster_snapshot", str(roster_id), {
                    "roster_id": roster_id,
                    "owner_id": owner_id,
                    "co_owners": list(map(str, roster.get("co_owners") or ())),
                    "players": list(map(str, roster.get("players") or ())),
                    "starters": list(map(str, roster.get("starters") or ())),
                    "reserve": list(map(str, roster.get("reserve") or ())),
                    "taxi": list(map(str, roster.get("taxi") or ())),
                },
                franchise_id=franchise,
            ))
            settings = roster.get("settings") or {}
            rows.append(self._record(league_id, season, "season_standing", str(roster_id), {
                "roster_id": roster_id, "wins": settings.get("wins"),
                "losses": settings.get("losses"), "ties": settings.get("ties"),
                "points_for": standing_points(settings, "fpts"),
                "points_against": standing_points(settings, "fpts_against"),
                "rank": settings.get("rank"),
            }, franchise_id=franchise))
        for week_key, matchups in (facts.get("matchups") or {}).items():
            week = int(week_key)
            grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in matchups or []:
                # Unpaired/bye rows still supply player evidence, never a
                # fabricated game against another unpaired franchise.
                if row.get("matchup_id") is not None:
                    grouped[int(row["matchup_id"])].append(row)
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
                rows.append(self._record(league_id, season, "matchup", f"{week}:{matchup_id}", {
                    "matchup_id": matchup_id,
                    **matchup_result(sides, playoff_week=(league.get("settings") or {}).get("playoff_week_start"), week=week),
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
        drafts_by_id = {str(draft.get('draft_id')): draft for draft in facts.get('drafts') or []
                        if draft.get('draft_id')}
        for pick in facts.get("draft_picks") or []:
            if str(pick.get('draft_id')) in drafts_by_id:
                pick = {**pick, **canonical_draft_bounds(drafts_by_id[str(pick['draft_id'])])}
            pick_id = str(pick.get("pick_no") or pick.get("pick_id") or _digest(pick)[:16])
            if pick.get("draft_id"):
                pick_id = f"{pick['draft_id']}:{pick_id}"
            roster_id = pick.get("roster_id")
            rows.append(self._record(
                league_id, season, "draft_pick", pick_id, dict(pick),
                player_id=str(pick.get("player_id") or "") or None,
                franchise_id=f"{league_id}:franchise:{roster_id}" if roster_id is not None else None,
            ))
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
        winners = [row for row in brackets if row["bracket"] == "winners_bracket"]
        if winners:
            rows.append(self._record(
                league_id, season, "playoff_result", "final", playoff_facts(winners),
            ))
        return rows

    def _transaction_records(
        self, league_id: str, season: int, entity_type: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if sleeper_season_cache.read(league_id, season) is None:
            from .recovery import HistoricalCheckpoints
            checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
            return [row for row in checkpoint['records'] if row['entity_type'] == entity_type] if checkpoint else []
        transactions_by_week = sleeper_season_cache.section(
            league_id, season, "transactions",
        ) or {}
        processed = 0
        for week_key, transactions in transactions_by_week.items():
            week = int(week_key)
            for transaction in transactions or []:
                selected = (
                    "trade" if transaction.get("type") == "trade" else "transaction"
                )
                if selected != entity_type:
                    continue
                transaction_id = str(
                    transaction.get("transaction_id") or _digest(transaction)[:16]
                )
                payload = dict(transaction)
                payload.setdefault("roster_ids", transaction.get("roster_ids") or [])
                occurred_at, timestamp_provenance = canonical_transaction_timestamp(payload)
                rows.append(self._record(
                    league_id, season, selected, transaction_id, payload, week=week,
                    occurred_at=occurred_at,
                    timestamp_provenance=timestamp_provenance,
                ))
                processed += 1
                if processed % 32 == 0:
                    time.sleep(0)
        return rows

    def _current_records(self, league_id: str, season: int) -> list[dict[str, Any]]:
        """Project bounded active state through the same canonical record shape."""
        with self._lock:
            data = self._current.get(str(league_id))
        if not data:
            return []
        league = data.get("league") or {}
        try:
            current_season = int(league.get("season") or 0)
        except (TypeError, ValueError):
            current_season = 0
        if current_season != int(season):
            return []
        rows = [self._record(league_id, season, "league_season", league_id, {
            "league_name": league.get("name") or "Sleeper League",
            "status": league.get("status"),
            "total_rosters": league.get("total_rosters"),
            "settings": data.get("league_settings") or league.get("settings") or {},
            "scoring_settings": data.get("scoring_settings") or league.get("scoring_settings") or {},
            "roster_positions": data.get("roster_positions") or league.get("roster_positions") or [],
        })]
        for team in data.get("teams") or ():
            roster_id = int(team.get("roster_id") or 0)
            franchise = f"{league_id}:franchise:{roster_id}"
            player_rows = team.get("players") or ()
            rows.append(self._record(league_id, season, "franchise_identity", str(roster_id), {
                "sleeper_roster_id": roster_id,
                "owner_id": str(team.get("owner_id") or ""),
                "dtos_display_name": team.get("team_name") or team.get("owner"),
                "franchise_id": franchise,
            }, franchise_id=franchise))
            rows.append(self._record(league_id, season, "roster_snapshot", str(roster_id), {
                "roster_id": roster_id,
                "owner_id": str(team.get("owner_id") or ""),
                "players": [str(row.get("id") or row.get("player_id")) for row in player_rows if row.get("id") or row.get("player_id")],
                "starters": [str(row.get("id") or row.get("player_id")) for row in player_rows if row.get("starter")],
                "reserve": [str(row.get("id") or row.get("player_id")) for row in player_rows if row.get("roster_slot") == "IR"],
                "taxi": [str(row.get("id") or row.get("player_id")) for row in player_rows if row.get("roster_slot") == "Taxi"],
            }, franchise_id=franchise))
        for pick in data.get("traded_picks") or ():
            source_id = str(pick.get("pick_id") or _digest(pick)[:16])
            rows.append(self._record(league_id, season, "pick_snapshot", source_id, dict(pick)))
        transactions = data.get("transactions") or ()
        if isinstance(transactions, dict):
            transaction_rows = [row for values in transactions.values() for row in values or ()]
        else:
            transaction_rows = list(transactions)
        for transaction in transaction_rows:
            transaction_id = str(transaction.get("transaction_id") or _digest(transaction)[:16])
            payload = dict(transaction)
            occurred_at, timestamp_provenance = canonical_transaction_timestamp(payload)
            entity = "trade" if transaction.get("type") == "trade" else "transaction"
            rows.append(self._record(
                league_id, season, entity, transaction_id, payload,
                week=transaction.get("week") or transaction.get("leg"),
                occurred_at=occurred_at, timestamp_provenance=timestamp_provenance,
            ))
        return rows

    def records(
        self, league_id: str, entity_type: str | None, *, season: int | None = None,
        week: int | None = None, franchise_id: str | None = None,
        player_id: str | None = None, limit: int | None = 100, offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        if season is not None:
            seasons = [season]
        else:
            seasons = sorted(self._cache_index(league_id), reverse=True)
            with self._lock:
                current = self._current.get(str(league_id)) or {}
            try:
                current_season = int((current.get("league") or {}).get("season") or 0)
            except (TypeError, ValueError):
                current_season = 0
            if current_season and current_season not in seasons:
                seasons.insert(0, current_season)
        from .recovery import HistoricalCheckpoints, HistoricalRecoveryUnavailable
        coverage = {}
        for selected in seasons:
            cached = sleeper_season_cache.read(league_id, selected)
            if cached is not None:
                coverage[selected] = self._supported_families(cached)
            else:
                checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, selected)
                if checkpoint:
                    coverage[selected] = set(checkpoint['families'])
            if selected in coverage and entity_type is not None and entity_type not in coverage[selected]:
                raise HistoricalRecoveryUnavailable('Requested historical family requires source recovery; coverage is partial')
        if entity_type in {"trade", "transaction"}:
            rows = [
                row for selected in seasons
                for row in self._transaction_records(league_id, selected, entity_type)
            ]
        else:
            rows = [
                row for selected in seasons
                for row in self._season_records(league_id, selected)
            ]
        rows = [row for row in rows if row['season'] not in coverage
                or row['entity_type'] in coverage[row['season']]]
        for selected in seasons:
            rows.extend(self._current_records(league_id, selected))
        rows = list({str(row["record_key"]): row for row in rows}.values())
        rows = [row for row in rows if (
            (entity_type is None or row["entity_type"] == entity_type)
            and (week is None or row["week"] == week)
            and (franchise_id is None or row["franchise_id"] == franchise_id)
            and (player_id is None or row["player_id"] == player_id)
        )]
        return len(rows), rows[offset:] if limit is None else rows[offset:offset + limit]

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
        totals: dict[str, float] = defaultdict(float)
        cached = sleeper_season_cache.read(league_id, season)
        if cached is not None:
            from .recovery import HistoricalRecoveryUnavailable
            if 'player_week' not in self._supported_families(cached):
                raise HistoricalRecoveryUnavailable('Historical player-week source unavailable')
            count = 0
            for matchups in (cached.facts.get('matchups') or {}).values():
                for matchup in matchups or ():
                    for player_id, score in (matchup.get('players_points') or {}).items():
                        totals[str(player_id)] += float(score or 0)
                        count += 1
        else:
            count, rows = self.records(league_id, 'player_week', season=season, limit=None)
            for row in rows:
                totals[str(row['player_id'])] += float((row.get('payload') or {}).get('fantasy_points') or 0)
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
