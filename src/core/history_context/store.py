"""Sleeper-cache-backed canonical history contract.

This intentionally resembles the bounded read surface formerly supplied by
``HistoricalStore`` so consumers can migrate without retaining a SQLite
provider archive. It never opens the dormant legacy database.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, OrderedDict
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from config import SLEEPER_SEASON_CACHE_ROOT
from .season_cache import SleeperSeasonCache
from .timestamps import canonical_transaction_timestamp
from .playoffs import playoff_facts
from .assets import draft_pick, future_pick_id, reconcile_player_weeks, PlayerWeekIndexLimit

from .metadata import minimal_metadata_store
from .coverage import family_observed, mapping, object_rows, readable_buckets, season_coverage

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
        self._event_indexes = OrderedDict()
        self._player_index_cache = None
        self._dataset_metrics = {"point_queries": 0, "archive_scans": 0}

    def update_current(self, league_id: str, data: dict[str, Any]) -> None:
        """Replace bounded operational state; no historical snapshots are appended."""
        from src.core.data_platform.normalization.birth_dates import birth_date_metadata
        identities = {}
        for player_id, player in (data.get("normalized_players") or {}).items():
            raw = (data.get('players') or {}).get(str(player_id)) or {}
            raw_birth = birth_date_metadata(raw) if str(raw.get('player_id', player_id)) == str(player_id) else {}
            birth = birth_date_metadata(player, raw_birth)
            sleeper_id = (player.get('provider_ids') or {}).get('Sleeper', str(player_id))
            if str(sleeper_id) != str(player_id) or str(player.get('dtos_id', player_id)) != str(player_id):
                birth = {'birth_date_status': 'identity_mismatch'}
            identities[str(player_id)] = {
                "dtos_player_id": str(player_id), "provider": "Sleeper",
                "provider_player_id": str(player_id),
                "display_name": str(player.get("name") or player_id),
                "confidence": 100, "metadata": {
                    "position": player.get("position"),
                    "team": player.get("team"),
                    "provider_ids": player.get("provider_ids") or {},
                    **birth,
                },
            }
        key = str(league_id)
        semantic_inputs = {
            "league": data.get("league") or {}, "teams": data.get("teams") or [],
            'scoring_settings': data.get('scoring_settings'), 'roster_positions': data.get('roster_positions'),
            "players": identities, "projections": data.get("projection_intelligence") or {},
            "valuation": data.get("valuation_intelligence") or {},
            "market": data.get("market_data") or {},
            "transactions": data.get("transactions") or [], "season_transactions": data.get("season_transactions") or {}, "drafts": data.get("drafts") or [],
            "draft_picks": data.get("draft_picks") or [], "traded_picks": data.get("traded_picks") or [],
            "pick_ledger": data.get("pick_ledger"),
            "season_matchups": {k: v for k, v in (data.get('season_matchups') or {}).items()
                                if k != 'observed_at'},
        }
        with self._lock:
            # Merge against the actual latest identity while holding the existing
            # store lock; concurrent league publications cannot erase a date.
            for player_id, identity in identities.items():
                metadata = identity['metadata']
                previous_identity = self._identities.get(player_id)
                if metadata.get('birth_date_status') == 'identity_mismatch' and previous_identity:
                    # Rejected provenance cannot replace a previously accepted
                    # identity or erase its unresolved birth-date candidates.
                    identity = {**previous_identity, 'metadata': {
                        **previous_identity['metadata'],
                        'birth_date_update_status': 'identity_mismatch',
                    }}
                    identities[player_id] = identity
                    metadata = identity['metadata']
                    player = data['normalized_players'][player_id]
                    for field in tuple(player):
                        if field.startswith('birth_date') or field == 'birthdate':
                            player.pop(field)
                    player.update(dtos_id=player_id, name=identity['display_name'],
                                  position=metadata.get('position'), team=metadata.get('team'),
                                  provider_ids=metadata.get('provider_ids') or {'Sleeper': player_id})
                elif metadata.get('birth_date_status') != 'identity_mismatch':
                    previous = (previous_identity or {}).get('metadata') or {}
                    birth = birth_date_metadata(metadata, previous)
                    for field in tuple(metadata):
                        if field.startswith('birth_date') or field == 'birthdate':
                            metadata.pop(field)
                    metadata.update(birth)
                # The existing normalized identity is already part of ordinary
                # league-cache publication. Keep its bounded evidence there so
                # an omitted provider field cannot erase the date on restart.
                player = (data.get('normalized_players') or {})[player_id]
                old_metadata = player.get('metadata') or {}
                player['metadata'] = {
                    **{k: v for k, v in old_metadata.items() if not k.startswith('birth_date') and k != 'birthdate'},
                    **{k: v for k, v in metadata.items() if k.startswith('birth_date')
                       and metadata.get('birth_date_status') != 'missing'},
                }
            semantic = _digest(semantic_inputs)
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
        if family_observed(cached.facts, 'matchups'):
            families.update(('player_week', 'matchup'))
        if family_observed(cached.facts, 'transactions'):
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

    def source_coverage(self, league_id: str, *, season: int | None = None) -> dict[str, Any]:
        """Bounded retained acquisition facts, without provider access or writes."""
        from .recovery import HistoricalCheckpoints
        seasons = []
        selected = [season] if season is not None else sorted(self._cache_index(league_id), reverse=True)
        with self._lock:
            current = self._current.get(str(league_id)) or {}
        current_season = (current.get('league') or {}).get('season')
        if season is None and str(current_season).isdigit() and int(current_season) not in selected:
            selected.insert(0, int(current_season))
        for year in selected:
            cached = sleeper_season_cache.read(league_id, year)
            weeks, context = self._current_matchup_source(current, league_id, year)
            if cached or weeks:
                facts = dict(cached.facts) if cached else {'league': current.get('league') or {}}
                if weeks:
                    facts['matchups'] = {**(facts.get('matchups') or {}), **weeks}
                coverage = season_coverage(facts, year)
                if weeks:
                    coverage['active_matchup_source'] = context
                seasons.append(coverage)
            else:
                checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, year)
                seasons.append({"season": year, "source_league_id": (checkpoint or {}).get('source_league_id'),
                                "state": "compact_checkpoint", "acquisition_periods": "unavailable",
                                "families": (checkpoint or {}).get('families', [])})
        return {"league_id": league_id, "seasons": seasons, "provider_requests": 0,
                "scope": "Retained source periods; unavailable and unacquired periods are not empty history."}

    def historical_availability(self, league_id: str, season: int) -> dict[str, Any]:
        from .recovery import HistoricalCheckpoints
        cached = sleeper_season_cache.read(league_id, season)
        with self._lock:
            current = self._current.get(str(league_id)) or {}
        weeks, _ = self._current_matchup_source(current, league_id, season)
        active_families = {'player_week', 'matchup'} if weeks else set()
        if cached is not None:
            return {'state': 'cached', 'covered_families': sorted(self._supported_families(cached) | active_families)}
        checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
        return {'state': 'partial' if checkpoint or weeks else 'unavailable',
                'covered_families': sorted(set(checkpoint['families'] if checkpoint else []) | active_families),
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
        families = set(checkpoint['families'])
        rows = self._admit_checkpoint_rows(league_id, season, checkpoint)
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

    def _source_player_week_rows(self, league_id, season, week, row, player_filter=None, *, context=None):
        """Shared nullable membership/scoring admission without full-season projection."""
        if not str(row.get("roster_id")).isdigit():
            return []
        rows = []
        points = row.get("players_points") if isinstance(row.get("players_points"), dict) else {}
        raw_starters = row.get('starters')
        known_roles = isinstance(raw_starters, list) and all(isinstance(p, (str, int)) for p in raw_starters)
        players = row.get('players') if isinstance(row.get('players'), list) else []
        membership = {str(p) for p in players if isinstance(p, (str, int))} | set(map(str, raw_starters if known_roles else [])) | set(map(str, points))
        if player_filter is not None:
            membership.intersection_update({str(player_filter)})
        starters = set(map(str, raw_starters)) if known_roles else set()
        roster_id = int(row.get("roster_id") or 0)
        for player_id in sorted(membership - {"0", "", "None"}):
            from .results import number
            score = number(points.get(player_id))
            source_score = score
            if context is not None and not context.get('scoring_settings'):
                score = None
            rows.append(self._record(
                league_id, season, "player_week",
                f"{week}:{roster_id}:{player_id}",
                {"fantasy_points": score, "points": score,
                 "starter": str(player_id) in starters if known_roles else None,
                 "lineup_role_source": "Sleeper explicit starters" if known_roles else "unavailable",
                 "roster_id": roster_id,
                 **({'source_fantasy_points': source_score, **context} if context is not None else {})},
                week=week, player_id=str(player_id),
                franchise_id=f"{league_id}:franchise:{roster_id}",
            ))
        return rows

    @staticmethod
    def _completed_week_limit(league):
        """Completion is a provider fact, never inferred from the calendar."""
        if league.get('status') == 'complete':
            return 18
        last = mapping(league.get('settings')).get('last_scored_leg')
        return last if type(last) is int and 0 <= last <= 18 else 0

    @classmethod
    def _retained_matchups(cls, facts):
        completed = cls._completed_week_limit(facts.get('league') or {})
        return {week: rows for week, rows in readable_buckets(facts, 'matchups').items()
                if 1 <= int(week) <= completed}

    @staticmethod
    def _scoring_context(league, operational=None):
        from .results import number
        scoring = league.get('scoring_settings') or {}
        scoring = scoring if isinstance(scoring, dict) and all(number(v) is not None for v in scoring.values()) else {}
        if operational is not None:
            if operational.get('scoring_settings') is not None and operational['scoring_settings'] != scoring:
                return {}
            if operational.get('roster_positions') is not None and operational['roster_positions'] != league.get('roster_positions'):
                return {}
        return scoring

    def _retained_scoring_context(self, league_id, season, league, source_generation):
        scoring = self._scoring_context(league)
        if not league.get('league_id') or str(league.get('season')) != str(season):
            scoring = {}
        with self._lock:
            current = self._current.get(str(league_id)) or {}
        active = current.get('league') or {}
        if str(active.get('season')) == str(season) and (
                str(active.get('league_id')) != str(league.get('league_id'))
                or self._scoring_context(active, current) != scoring
                or active.get('roster_positions') != league.get('roster_positions')):
            scoring = {}
        return {'source_league_id': league.get('league_id'),
                'scoring_settings': scoring,
                'scoring_context_availability': 'supported' if scoring else 'unavailable_or_incompatible',
                'roster_positions': league.get('roster_positions') or [],
                'evidence_kind': 'completed_week_actual', 'source_generation': source_generation}

    @classmethod
    def _current_matchup_source(cls, data, league_id, season):
        """Read the existing prepared source; future placeholders are not actuals."""
        from services.matchup_season import METHOD
        from src.core.intelligence.season_calendar import season_calendar
        league, prepared = data.get('league') or {}, data.get('season_matchups') or {}
        if (str(league.get('league_id')) != str(league_id)
                or str(league.get('season')) != str(season)
                or prepared.get('league_id') != str(league_id)
                or prepared.get('season') != str(season)
                or prepared.get('methodology') != METHOD
                or prepared.get('calendar_reference') != season_calendar(league)['reference']):
            return {}, {}
        completed = cls._completed_week_limit(league)
        weeks = {str(week): value['rows'] for week, value in (prepared.get('weeks') or {}).items()
                 if str(week).isdigit() and 1 <= int(week) <= min(completed, 18)
                 and isinstance(value, dict) and value.get('availability') == 'available'
                 and isinstance(value.get('rows'), list)}
        scoring = cls._scoring_context(league, data)
        context = {'source_league_id': str(league_id),
                   'scoring_settings': scoring,
                   'scoring_context_availability': 'supported' if scoring else 'unavailable_or_incompatible',
                   'roster_positions': league.get('roster_positions') or [],
                   'evidence_kind': 'completed_week_actual',
                   'source_generation': prepared.get('semantic_generation')}
        return weeks, context

    def _season_records(self, league_id: str, season: int, families: set[str] | None = None, player_filter: str | None = None) -> list[dict[str, Any]]:
        from .results import matchup_result, standing_points
        # Pin facts and provenance to one verified publication. A replacement
        # after this read must not relabel these facts with a newer checksum.
        cached = sleeper_season_cache.read(league_id, season)
        facts = cached.facts if cached else None
        if not facts:
            from .recovery import HistoricalCheckpoints
            checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
            rows = self._admit_checkpoint_rows(league_id, season, checkpoint) if checkpoint else []
            # Earlier compact evidence cannot establish whether a false role
            # came from explicit bench membership or missing starters. Qualify
            # the read; never rewrite the retained checkpoint.
            return [{**row, 'payload': {**row['payload'], 'starter': None,
                                       'lineup_role': 'unknown', 'lineup_role_source': 'legacy_unconfirmed'}}
                    if row['entity_type'] == 'player_week' and row['payload'].get('starter') is False
                    and not row['payload'].get('lineup_role_source') else row for row in rows]
        if families is not None:
            # Project only the requested source families before constructing rows.
            # Event lookups never materialize the player-week universe.
            facts = dict(facts)
            if not families & {'player_week', 'matchup'}:
                facts['matchups'] = {}
            if not families & {'trade', 'transaction'}:
                facts['transactions'] = {}
            if 'draft_pick' not in families:
                facts['draft_picks'] = []
            if 'pick_snapshot' not in families:
                facts['traded_picks'] = []
            if not families & {'playoff_result', 'playoff_bracket'}:
                facts['winners_bracket'] = facts['losers_bracket'] = []
        league = mapping(facts.get("league"))
        context = self._retained_scoring_context(league_id, season, league, cached.checksum)
        rows = [self._record(league_id, season, "league_season", league_id, {
            "sleeper_season_league_id": league.get("league_id"),
            "sleeper_season": league.get("season"),
            "previous_league_id": league.get("previous_league_id"),
            "league_name": league.get("name") or "Sleeper League",
            "status": league.get("status"),
            "total_rosters": league.get("total_rosters"),
            "settings": league.get("settings") or {},
            "scoring_settings": league.get("scoring_settings") or {},
            "roster_positions": league.get("roster_positions") or [],
        })]
        users = {str(row.get("user_id")): row for row in object_rows(facts.get("users"))}
        rosters = object_rows(facts.get("rosters"))
        for roster in rosters:
            if not str(roster.get("roster_id")).isdigit():
                continue
            roster_id = int(roster.get("roster_id") or 0)
            owner_id = str(roster.get("owner_id") or "")
            user = users.get(owner_id, {})
            franchise = f"{league_id}:franchise:{roster_id}"
            rows.append(self._record(league_id, season, "franchise_identity", str(roster_id), {
                "sleeper_roster_id": roster_id, "owner_id": owner_id,
                "co_owners": list(map(str, roster.get("co_owners") or ())),
                "sleeper_username": user.get("display_name") or user.get("username"),
                "dtos_display_name": mapping(user.get("metadata")).get("team_name")
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
            settings = mapping(roster.get("settings"))
            rows.append(self._record(league_id, season, "season_standing", str(roster_id), {
                "roster_id": roster_id, "wins": settings.get("wins"),
                "losses": settings.get("losses"), "ties": settings.get("ties"),
                "points_for": standing_points(settings, "fpts"),
                "points_against": standing_points(settings, "fpts_against"),
                "rank": settings.get("rank"),
            }, franchise_id=franchise))
        for week_key, matchups in self._retained_matchups(facts).items():
            week = int(week_key)
            grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in matchups or []:
                if not str(row.get('roster_id')).isdigit():
                    continue
                # Unpaired/bye rows still supply player evidence, never a
                # fabricated game against another unpaired franchise.
                if str(row.get("matchup_id")).isdigit():
                    grouped[int(row["matchup_id"])].append(row)
                source = {**context, 'source_endpoint': f"/league/{league.get('league_id')}/matchups/{week}"}
                rows.extend(self._source_player_week_rows(league_id, season, week, row, player_filter, context=source))
            for matchup_id, sides in grouped.items():
                rows.append(self._record(league_id, season, "matchup", f"{week}:{matchup_id}", {
                    "matchup_id": matchup_id,
                    **matchup_result(sides, playoff_week=mapping(league.get("settings")).get("playoff_week_start"), week=week),
                }, week=week))
        for week_key, transactions in readable_buckets(facts, "transactions").items():
            week = int(week_key)
            for transaction in transactions or []:
                if not transaction.get('transaction_id'):
                    continue
                transaction_id = str(transaction.get("transaction_id") or _digest(transaction)[:16])
                payload = {**transaction, "source_league_id": league.get("league_id") or league_id}
                payload.setdefault("roster_ids", transaction.get("roster_ids") or [])
                entity = "trade" if transaction.get("type") == "trade" else "transaction"
                occurred_at, timestamp_provenance = canonical_transaction_timestamp(payload)
                rows.append(self._record(
                    league_id, season, entity, transaction_id, payload, week=week,
                    occurred_at=occurred_at,
                    timestamp_provenance=timestamp_provenance,
                ))
        for draft in object_rows(facts.get("drafts")):
            draft_id = str(draft.get("draft_id") or _digest(draft)[:16])
            rows.append(self._record(league_id, season, "draft", draft_id, dict(draft)))
        drafts_by_id = {str(draft.get('draft_id')): draft for draft in object_rows(facts.get('drafts'))
                        if draft.get('draft_id')}
        for pick in object_rows(facts.get("draft_picks")):
            pick = draft_pick(pick, drafts_by_id.get(str(pick.get('draft_id')), {}),
                              str(league.get('league_id') or league_id), season)
            pick_id = pick.get('selection_id') or str(pick.get('pick_id') or _digest(pick)[:16])
            roster_id = pick.get('selecting_roster_id')
            rows.append(self._record(league_id, season, 'draft_pick', pick_id, pick,
                player_id=str(pick.get('player_id') or '') or None,
                franchise_id=f'{league_id}:franchise:{roster_id}' if roster_id is not None else None,
                occurred_at=pick.get('selected_at')))
        for pick in object_rows(facts.get("traded_picks")):
            source_id = str(pick.get("pick_id") or _digest(pick)[:16])
            rows.append(self._record(
                league_id, season, "pick_snapshot", source_id, dict(pick),
            ))
        brackets = []
        from .playoffs import admitted_bracket_row, roster_identity
        roster_ids = {identity for row in object_rows(facts.get('rosters'))
                      if (identity := roster_identity(row.get('roster_id'))) is not None}
        for bracket_name in ("winners_bracket", "losers_bracket"):
            for row in object_rows(facts.get(bracket_name)):
                if not isinstance(row.get('m'), (int, str)):
                    continue
                payload = {**admitted_bracket_row(row, roster_ids or None), "bracket": bracket_name}
                rows.append(self._record(league_id, season, "playoff_bracket", f"{bracket_name}:{row.get('m')}", payload))
                brackets.append(payload)
        winners = [row for row in brackets if row["bracket"] == "winners_bracket"]
        if winners:
            rows.append(self._record(
                league_id, season, "playoff_result", "final", playoff_facts(winners),
            ))
        return rows

    def _admit_checkpoint_rows(self, league_id, season, checkpoint):
        """Requalify existing compact evidence without rewriting its source."""
        rows = checkpoint['records']
        source = next((r['payload'] for r in rows if r['entity_type'] == 'league_season'), {})
        league = {**source, 'league_id': source.get('sleeper_season_league_id'),
                  'season': source.get('sleeper_season')}
        context = self._retained_scoring_context(league_id, season, league, checkpoint['source_checksum'])
        completed = self._completed_week_limit(league)
        admitted = []
        for row in rows:
            if row['entity_type'] not in {'player_week', 'matchup'}:
                admitted.append(row)
                continue
            if type(row.get('week')) is not int or not 1 <= row['week'] <= completed:
                continue
            if row['entity_type'] == 'player_week':
                from .results import number
                payload = row['payload']
                score = number(payload.get('fantasy_points', payload.get('points')))
                supported = (bool(context['scoring_settings'])
                    and payload.get('scoring_context_availability') != 'unavailable_or_incompatible'
                    and all(field not in payload or payload[field] == context[field]
                            for field in ('scoring_settings', 'source_league_id', 'source_generation', 'roster_positions')))
                payload = {**payload, **context,
                           'source_fantasy_points': payload.get('source_fantasy_points', score),
                           'fantasy_points': score if supported else None, 'points': score if supported else None}
                if not supported:
                    payload['scoring_context_availability'] = 'unavailable_or_incompatible'
                row = {**row, 'payload': payload}
            admitted.append(row)
        return admitted

    def _transaction_records(
        self, league_id: str, season: int, entity_type: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        # Borrow both sections together. Eviction/publication must not change
        # the source identity midway through an active transaction reader.
        facts = sleeper_season_cache.sections(league_id, season, ('league', 'transactions'))
        if not facts:
            from .recovery import HistoricalCheckpoints
            checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, season)
            return [row for row in checkpoint['records'] if row['entity_type'] == entity_type] if checkpoint else []
        transactions_by_week = readable_buckets(facts, 'transactions')
        source = facts.get('league') or {}
        processed = 0
        for week_key, transactions in transactions_by_week.items():
            week = int(week_key)
            for transaction in transactions or []:
                if not transaction.get('transaction_id'):
                    continue
                selected = (
                    "trade" if transaction.get("type") == "trade" else "transaction"
                )
                if selected != entity_type:
                    continue
                transaction_id = str(
                    transaction.get("transaction_id") or _digest(transaction)[:16]
                )
                payload = {**transaction, "source_league_id": source.get("league_id") or league_id}
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

    def _current_records(self, league_id: str, season: int, families=None) -> list[dict[str, Any]]:
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
        if families is None or set(families) & {'player_week', 'matchup'}:
            from .results import matchup_result
            weeks, context = self._current_matchup_source(data, league_id, season)
            for week, sides in weeks.items():
                source = {**context, 'source_endpoint': f'/league/{league_id}/matchups/{week}'}
                groups = defaultdict(list)
                for side in sides:
                    if not isinstance(side, dict):
                        continue
                    if str(side.get('matchup_id')).isdigit():
                        groups[str(side['matchup_id'])].append(side)
                    if families is None or 'player_week' in families:
                        records = self._source_player_week_rows(league_id, season, int(week), side, context=source)
                        for record in records:
                            record['observed_at'] = (data.get('season_matchups') or {}).get('observed_at')
                            record['calculation_method'] = 'sleeper_prepared_season_matchups'
                        rows.extend(records)
                if families is None or 'matchup' in families:
                    for matchup_id, group in groups.items():
                        rows.append(self._record(league_id, season, 'matchup', f'{week}:{matchup_id}', {
                            **source, 'matchup_id': int(matchup_id),
                            **matchup_result(group, playoff_week=(league.get('settings') or {}).get('playoff_week_start'), week=int(week)),
                        }, week=int(week)))
        for team in data.get("teams") or ():
            roster_id = int(team.get("roster_id") or 0)
            franchise = f"{league_id}:franchise:{roster_id}"
            player_rows = team.get("players") or ()
            rows.append(self._record(league_id, season, "franchise_identity", str(roster_id), {
                "sleeper_roster_id": roster_id,
                "owner_id": str(team.get("owner_id") or ""),
                "dtos_display_name": team.get("team_name") or team.get("owner"),
                "sleeper_username": team.get("owner"),
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
        drafts = {str(d.get('draft_id')): d for d in data.get('drafts') or ()}
        for draft_id, draft in drafts.items():
            rows.append(self._record(league_id, season, 'draft', draft_id, dict(draft)))
        for raw in data.get('draft_picks') or ():
            pick = draft_pick(raw, drafts.get(str(raw.get('draft_id')), {}), league_id, season)
            if pick['selection_id']:
                rows.append(self._record(league_id, season, 'draft_pick', pick['selection_id'], pick,
                    player_id=str(pick.get('player_id') or '') or None,
                    franchise_id=f"{league_id}:franchise:{pick['selecting_roster_id']}", occurred_at=pick.get('selected_at')))
        buckets = data.get('season_transactions') or {}
        current_transactions = data.get('transactions') or ()
        if isinstance(current_transactions, dict):
            current_transactions = [dict(row, leg=int(week)) for week, bucket in current_transactions.items() for row in bucket or ()]
        transactions = [dict(row, leg=int(week)) for week, bucket in buckets.items() for row in bucket or ()] + list(current_transactions)
        transactions = list({str(row.get('transaction_id') or _digest(row)): row for row in transactions}.values())
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
        return self._read_records(league_id, entity_type, season=season, week=week,
            franchise_id=franchise_id, player_id=player_id, limit=limit, offset=offset)

    def _read_records(
        self, league_id: str, entity_type: str | None, *, season: int | None = None,
        week: int | None = None, franchise_id: str | None = None,
        player_id: str | None = None, limit: int | None = 100, offset: int = 0,
        allow_partial: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        if entity_type == 'player_week' and player_id is not None:
            try:
                _totals, by_player = self._player_week_index(league_id, allow_partial=allow_partial)
            except PlayerWeekIndexLimit:
                return self._record_page(league_id, entity_type, season=season,
                    week=week, franchise_id=franchise_id, player_id=player_id,
                    limit=limit, offset=offset, allow_partial=allow_partial)
            rows = [r for r in by_player.get(str(player_id), ())
                    if (season is None or r['season'] == season)
                    and (week is None or r['week'] == week)
                    and (franchise_id is None or r['franchise_id'] == franchise_id)]
            return len(rows), rows[offset:] if limit is None else rows[offset:offset + limit]
        return self._record_page(league_id, entity_type, season=season, week=week,
            franchise_id=franchise_id, player_id=player_id, limit=limit, offset=offset, allow_partial=allow_partial)

    def optional_records(self, league_id: str, entity_type: str | None, **kwargs):
        return self._read_records(league_id, entity_type, allow_partial=True, **kwargs)

    def _record_page(
        self, league_id: str, entity_type: str | None, *, season: int | None = None,
        week: int | None = None, franchise_id: str | None = None,
        player_id: str | None = None, limit: int | None = 100, offset: int = 0,
        _families: set[str] | None = None,
        allow_partial: bool = False,
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
        with self._lock:
            current = self._current.get(str(league_id)) or {}
        for selected in seasons:
            cached = sleeper_season_cache.read(league_id, selected)
            if cached is not None:
                coverage[selected] = self._supported_families(cached)
            else:
                checkpoint = HistoricalCheckpoints(sleeper_season_cache.root).read(league_id, selected)
                if checkpoint:
                    coverage[selected] = set(checkpoint['families'])
            weeks, _ = self._current_matchup_source(current, league_id, selected)
            if weeks and selected in coverage:
                coverage[selected].update(('player_week', 'matchup'))
            if not allow_partial and selected in coverage and entity_type is not None and entity_type not in coverage[selected]:
                raise HistoricalRecoveryUnavailable('Requested historical family requires source recovery; coverage is partial')
        if entity_type in {"trade", "transaction"}:
            rows = [
                row for selected in seasons
                for row in self._transaction_records(league_id, selected, entity_type)
            ]
        else:
            rows = [
                row for selected in seasons
                for row in self._season_records(league_id, selected, _families or ({entity_type} if entity_type else None), player_filter=player_id if entity_type == 'player_week' else None)
            ]
        rows = [row for row in rows if row['season'] not in coverage
                or row['entity_type'] in coverage[row['season']]]
        for selected in seasons:
            rows.extend(self._current_records(league_id, selected, _families or ({entity_type} if entity_type else None)))
        from .playoffs import admitted_bracket_row, admitted_playoff_result
        rows = [{**row, 'payload': admitted_bracket_row(row['payload'])} if row['entity_type'] == 'playoff_bracket'
                else {**row, 'payload': admitted_playoff_result(row['payload'])} if row['entity_type'] == 'playoff_result'
                else row for row in rows]
        # Numeric observations sharing a canonical key are evidence, not
        # successive corrections. Admit the whole published generation before
        # key deduplication, otherwise row order silently chooses the score.
        player_rows = reconcile_player_weeks([r for r in rows if r['entity_type'] == 'player_week'])
        rows = list({str(row["record_key"]): row for row in rows
                     if row['entity_type'] != 'player_week'}.values()) + player_rows
        rows = [row for row in rows if (
            (entity_type is None or row["entity_type"] == entity_type)
            and (_families is None or row["entity_type"] in _families)
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
            context = self._retained_scoring_context(league_id, season, cached.facts.get('league') or {}, cached.checksum)
            rows = reconcile_player_weeks([
                record for week, matchups in self._retained_matchups(cached.facts).items()
                for matchup in matchups
                for record in self._source_player_week_rows(league_id, season, int(week), matchup,
                    context={**context, 'source_endpoint': f"/league/{context['source_league_id']}/matchups/{week}"})
            ])
            rows = reconcile_player_weeks(rows + [row for row in self._current_records(league_id, season, {'player_week'})
                                                  if row['entity_type'] == 'player_week'])
            count = len(rows)
        else:
            count, rows = self.optional_records(league_id, 'player_week', season=season, limit=100_000)
        for row in rows:
            score = row['payload'].get('fantasy_points')
            if score is not None:
                totals[str(row['player_id'])] += score
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
        return future_pick_id(payload, season, selection=bool(payload.get('selection_id') or payload.get('player_id')))

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
        families, _index = self._event_index(league_id)
        return next((row for kind in ('trade', 'transaction') for row in families[kind]
                     if str(row['source_record_id']) == str(transaction_id)), None)

    def _event_index(self, league_id: str):
        """Two resident generations; no player-week universe retained in this index."""
        key = (str(league_id), self.dataset_version(league_id))
        with self._lock:
            if key in self._event_indexes:
                self._event_indexes.move_to_end(key)
                return self._event_indexes[key]
        kinds = ('draft_pick', 'transaction', 'trade', 'pick_snapshot', 'weekly_roster', 'draft', 'roster_snapshot')
        _, rows = self._record_page(league_id, None, limit=100_001, _families=set(kinds))
        if len(rows) > 100_000:
            raise ValueError('Historical event preparation exceeds bounded record limit')
        kinds = ('draft_pick', 'transaction', 'trade', 'pick_snapshot', 'weekly_roster', 'draft', 'roster_snapshot')
        families = {kind: [] for kind in kinds}
        assets = defaultdict(list)
        for row in rows:
            kind, payload = row['entity_type'], row['payload']
            if kind not in families:
                continue
            families[kind].append(row)
            ids = set()
            if kind == 'draft_pick':
                if row.get('player_id'):
                    ids.add('DTOS-P-' + str(row['player_id']))
                ids.add(payload.get('selection_id'))
                ids.add(self._canonical_pick_id(payload, row['season']))
            elif kind in ('transaction', 'trade'):
                ids.update('DTOS-P-' + str(player) for player in {*(payload.get('adds') or {}), *(payload.get('drops') or {})})
                ids.update(self._canonical_pick_id(p, row['season']) for p in payload.get('draft_picks') or ())
            elif kind == 'pick_snapshot':
                ids.add(self._canonical_pick_id(payload, row['season']))
            elif kind in ('weekly_roster', 'roster_snapshot'):
                ids.update('DTOS-P-' + str(p) for p in payload.get('players') or ())
            for identity in ids - {None}:
                assets[identity].append(row)
        result = families, dict(assets)
        with self._lock:
            self._event_indexes[key] = result
            while len(self._event_indexes) > 2:
                self._event_indexes.popitem(last=False)
        return result

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
        families, assets = self._event_index(league_id)
        result = {kind: [] for kind in families}
        for row in assets.get(asset_id, ()):
            result[row['entity_type']].append(row)
        result['draft'] = list(families['draft'])
        return result

    def player_week_totals(self, league_id: str) -> dict[int, dict[str, float]]:
        return self._player_week_index(league_id)[0]

    def _player_week_index(self, league_id: str, *, allow_partial: bool = False):
        """One generation of reconciled rows, shared by totals and targeted reads."""
        key = (str(league_id), self.dataset_version(league_id))
        with self._lock:
            if self._player_index_cache and self._player_index_cache[0] == key:
                if self._player_index_cache[1] is None:
                    raise PlayerWeekIndexLimit('Historical player-week comparison exceeds bounded preparation')
                if not allow_partial and len(self._player_index_cache) > 3 and self._player_index_cache[3]:
                    from .recovery import HistoricalRecoveryUnavailable
                    raise HistoricalRecoveryUnavailable('Requested historical scoring family is partial')
                return self._player_index_cache[1:3]
            count, rows = self._record_page(league_id, 'player_week', limit=100_001, allow_partial=allow_partial)
            if count > 100_000:
                self._player_index_cache = (key, None, None)
                raise PlayerWeekIndexLimit('Historical player-week comparison exceeds bounded preparation')
            totals, by_player = {}, defaultdict(list)
            for row in reconcile_player_weeks(rows):
                player = str(row['player_id'])
                by_player[player].append(row)
                points = row['payload'].get('fantasy_points')
                if points is not None:
                    season = totals.setdefault(int(row['season']), {})
                    season[player] = season.get(player, 0) + float(points)
            missing_family = any('player_week' not in self.historical_availability(league_id, season)['covered_families']
                                 for season in self._cache_index(league_id))
            self._player_index_cache = (key, totals, dict(by_player), missing_family)
            return self._player_index_cache[1:3]

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
                    append_event_id(row, "selection:" + str(row["player_id"]))
                    if self._canonical_pick_id(payload, row["season"]):
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
                elif row["entity_type"] in {"weekly_roster", "roster_snapshot"}:
                    players = dict.fromkeys([
                        *(payload.get("players") or []),
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
