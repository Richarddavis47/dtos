"""Captured Sleeper -> active canonical history -> reconstruction/HTTP controls."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
import multiprocessing
import sqlite3
from time import perf_counter
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.history import create_history_router
from services.history import player_career
from services.matchup_season import prepare_season_matchups
from src.core.data_platform.normalization.identity import PlayerIdentityResolver
from src.core.historical_franchise_state import HistoricalBoundary, HistoricalFranchiseStateService
from src.core.historical_intelligence import HistoricalIntelligenceService
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore
from src.core.fois.process_execution import compact_fois_input

SOURCE = Path(__file__).parent / 'fixtures/historical_player_week_sources.json'
DAY, ARK = '1313066632158924800', '1319750579458686976'


def spawned_evidence(data, cache_root, result):
    with patch('src.core.history_context.store.sleeper_season_cache', SleeperSeasonCache(Path(cache_root))):
        store = CanonicalHistoryStore()
        store.update_current(DAY, data)
        count, _ = store.records(DAY, 'player_week', season=2026, limit=None)
        result.put((count, store.identity_for_provider_id('11563')['metadata']))


def active_source(index=0):
    captured = json.loads(SOURCE.read_text())
    source = captured['leagues'][index]
    league = source['league']
    async def fetch(path):
        if path.endswith('/matchups/5'):
            return deepcopy(source['week5'])
        raise OSError('Controlled unavailable source period')
    # Existing real publisher: other periods unavailable, future scores supplied
    # deliberately to prove their values cannot be admitted as completed actuals.
    future = deepcopy(source['week5'])
    for row in future:
        row['players_points'] = {key: 999 for key in row['players_points']}
    prepared = asyncio.run(prepare_season_matchups(
        league, 6, future, fetch, observed_at=captured['captured_at']))
    resolver = PlayerIdentityResolver(captured['players'])
    return {'league': deepcopy(league), 'week': 6, 'season_matchups': prepared,
            'scoring_settings': deepcopy(league['scoring_settings']),
            'roster_positions': list(league['roster_positions']),
            'players': captured['players'],
            'normalized_players': {key: asdict(resolver.resolve(key)) for key in captured['players']},
            'teams': [{'roster_id': row['roster_id'], 'owner_id': f"fixture-{row['roster_id']}",
                       'players': [{'id': pid} for pid in row.get('players') or []]}
                      for row in source['week5']]}, source


class HistoricalPlayerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = SleeperSeasonCache(Path(self.temp.name) / 'seasons')
        cache_patch = patch('src.core.history_context.store.sleeper_season_cache', self.cache)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)
        self.store = CanonicalHistoryStore()
        service_patch = patch('services.history.historical_store', self.store)
        service_patch.start()
        self.addCleanup(service_patch.stop)

    def publish(self, index=0):
        data, source = active_source(index)
        league = str(data['league']['league_id'])
        self.store.update_current(league, data)
        return data, source

    def test_captured_week5_counts_exact_scores_roles_and_league_identity(self):
        for index, expected in ((0, 285), (1, 273)):
            data, source = self.publish(index)
            league = data['league']['league_id']
            count, rows = self.store.records(league, 'player_week', season=2026, limit=None)
            self.assertEqual(count, expected)
            lookup = {(str(row['roster_id']), pid): points for row in source['week5']
                      for pid, points in row['players_points'].items()}
            for row in rows:
                payload = row['payload']
                self.assertEqual(row['week'], 5)
                self.assertEqual(row['league_id'], league)
                self.assertEqual(row['provider'], 'Sleeper')
                self.assertEqual(payload['fantasy_points'], lookup[(str(payload['roster_id']), row['player_id'])])
                self.assertEqual(row['franchise_id'], f"{league}:franchise:{payload['roster_id']}")
                self.assertEqual(payload['scoring_settings'], source['league']['scoring_settings'])
                self.assertEqual(payload['evidence_kind'], 'completed_week_actual')
                self.assertTrue(payload['source_endpoint'].endswith('/matchups/5'))
                self.assertEqual(row['observed_at'], data['season_matchups']['observed_at'])
                original = next(r for r in source['week5'] if r['roster_id'] == payload['roster_id'])
                self.assertEqual(payload['starter'], row['player_id'] in original['starters'])
            self.assertTrue(any(row['payload']['fantasy_points'] == 0 for row in rows))
            self.assertTrue(any(row['payload']['starter'] is False for row in rows))

    def test_birthdate_survives_actual_normalization_and_missing_refresh(self):
        data, _ = self.publish()
        pid = next(iter(data['players']))
        expected = data['players'][pid]['birth_date']
        self.assertEqual(self.store.identity_for_provider_id(pid)['metadata']['birth_date'], expected)
        data['normalized_players'][pid] = {'name': 'Updated name', 'position': 'WR'}
        self.store.update_current(DAY, data)
        identity = self.store.identity_for_provider_id(pid)
        self.assertEqual(identity['metadata']['birth_date'], expected)
        self.assertEqual(identity['display_name'], 'Updated name')
        # Ordinary existing cache serialization/reload, with no second archive.
        restored = CanonicalHistoryStore()
        restored.update_current(DAY, json.loads(json.dumps(data)))
        self.assertEqual(restored.identity_for_provider_id(pid)['metadata']['birth_date'], expected)

    def test_age_uses_decision_date_with_timezone_and_never_current_age(self):
        self.store.update_current(DAY, {'league': {'season': '2026'}, 'normalized_players': {
            'p': {'name': 'Player', 'position': 'WR', 'age': 99, 'birth_date': '2000-10-10'}}})
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
        before = service._market_assets(['p'], '2020-10-10T12:00:00Z')[0][0]
        after = service._market_assets(['p'], '2025-10-10T12:00:00+00:00')[0][0]
        self.assertEqual(before.age_as_of, 20)
        self.assertEqual(after.age_as_of, 25)
        self.assertIsNone(service._market_assets(['p'], '1999-01-01T00:00:00Z')[0][0].age_as_of)

    def test_generation_and_completed_week_boundary(self):
        data, _ = self.publish()
        generation = self.store.dataset_version(DAY)
        count, _ = self.store.records(DAY, 'player_week', player_id='8137', limit=None)
        self.assertGreater(count, 0)
        data['season_matchups']['observed_at'] = '2026-10-17T23:59:59Z'
        self.store.update_current(DAY, data)
        self.assertEqual(self.store.dataset_version(DAY), generation)
        data['league']['settings']['last_scored_leg'] = 4
        self.store.update_current(DAY, data)
        self.assertNotEqual(self.store.dataset_version(DAY), generation)
        self.assertEqual(self.store.records(DAY, 'player_week', limit=None)[0], 0)

    def test_http_career_and_historical_decision_cutoff(self):
        data, source = self.publish()
        side = source['week5'][0]
        pid = next(pid for pid, value in side['players_points'].items() if value > 0)
        app = FastAPI()
        app.include_router(create_history_router(league_id=DAY, require_data=lambda: data,
                           page=lambda title, body: HTMLResponse(body)))
        with TestClient(app) as client:
            response = client.get(f'/history/player/{pid}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(str(side['players_points'][pid]), response.text)
        career = player_career(DAY, pid)
        self.assertEqual(career['weekly_record_count'], 1)
        self.assertEqual(career['seasons']['2026']['season_total'], side['players_points'][pid])
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
        franchise = f"{DAY}:franchise:{side['roster_id']}"
        players = set(side['players'])
        _, before = service._lineup_and_production(DAY, franchise,
            HistoricalBoundary(2026, week=5, occurred_at='2026-10-06T00:00:00Z'), players, ('QB',))
        _, after = service._lineup_and_production(DAY, franchise,
            HistoricalBoundary(2026, week=6, occurred_at='2026-10-13T00:00:00Z'), players, ('QB',))
        self.assertEqual(before, {})
        self.assertEqual(after[pid], side['players_points'][pid])

    def test_settled_reads_do_not_persist_sources_or_solve_lineups(self):
        data, _ = self.publish()
        root = Path(self.temp.name)
        def files():
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob('*') if p.is_file()}
        baseline = files()
        def rows():
            with sqlite3.connect(self.store.path) as db:
                tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                return {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
        before_rows = rows()
        start = perf_counter()
        with patch('src.core.historical_franchise_state.service.optimal_legal_lineup', side_effect=AssertionError('solver')):
            for _ in range(15):
                self.assertEqual(self.store.records(DAY, 'player_week', limit=None)[0], 285)
                self.store.update_current(DAY, data)
        self.assertEqual(files(), baseline)
        self.assertEqual(rows(), before_rows)
        print({'settled_reads': 15, 'files_before_after': len(baseline), 'metadata_rows_before_after': before_rows,
               'all_hashes_unchanged': True, 'elapsed_ms': round((perf_counter() - start) * 1000, 3)})

    def test_missing_invalid_conflicting_and_identity_mismatched_birth_dates(self):
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
        cases = ({}, {'birth_date': 'invalid'},
                 {'birth_date': '2000-01-01', 'birthdate': '2001-01-01'},
                 {'birth_date': '2000-01-01', 'provider_ids': {'Sleeper': 'another-player'}})
        for index, fields in enumerate(cases):
            pid = str(index)
            self.store.update_current(DAY, {'league': {'season': '2026'}, 'normalized_players': {pid: fields}})
            asset = service._market_assets([pid], '2026-10-17T00:00:00Z')[0][0]
            self.assertIsNone(asset.age_as_of)
            self.assertTrue(asset.age_reason_codes)
        for value in ('2000-01-01', '2001-01-01'):
            self.store.update_current(DAY, {'normalized_players': {'p': {'birth_date': value}}})
        metadata = self.store.identity_for_provider_id('p')['metadata']
        self.assertEqual(metadata['birth_date_status'], 'conflicting')
        self.assertNotIn('birth_date', metadata)
        self.assertIsNone(service._market_assets(['p'], '2026-10-17T00:00:00Z')[0][0].age_as_of)

    def test_iso_datetime_birthdate_and_provider_resolution(self):
        resolver = PlayerIdentityResolver({'123': {'player_id': '123', 'birth_date': '2000-01-01T00:00:00Z',
                                                  'gsis_id': 'supported-gsis'}})
        self.assertIs(resolver.resolve('supported-gsis', 'GSIS'), resolver.resolve('123'))
        self.assertIsNone(resolver.resolve('123', 'GSIS'))
        self.store.update_current(DAY, {'normalized_players': {'123': asdict(resolver.resolve('supported-gsis', 'GSIS'))}})
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
        self.assertEqual(service._market_assets(['123'], '2025-01-01T00:00:00Z')[0][0].age_as_of, 25)

    def test_raw_existing_identity_recovers_without_new_provider_request(self):
        data, _ = self.publish()
        data['normalized_players']['11563'].pop('metadata')
        store = CanonicalHistoryStore()
        store.update_current(DAY, data)
        self.assertEqual(store.identity_for_provider_id('11563')['metadata']['birth_date'], data['players']['11563']['birth_date'])

    def test_missing_score_and_unknown_role_are_not_zero_or_starter(self):
        data, _ = self.publish()
        row = data['season_matchups']['weeks']['5']['rows'][0]
        pid = next(iter(row['players_points']))
        row['players_points'].pop(pid)
        row['starters'] = None
        self.store.update_current(DAY, data)
        found = next(r for r in self.store.records(DAY, 'player_week', limit=None)[1] if r['player_id'] == pid)
        self.assertIsNone(found['payload']['fantasy_points'])
        self.assertIsNone(found['payload']['starter'])
        self.assertEqual(found['payload']['lineup_role'], 'unknown')

    def test_invalid_or_mismatched_scoring_preserves_source_but_withholds_numeric_admission(self):
        for scoring in ({}, {'rec': None}, {'rec': True}):
            data, _ = active_source()
            data['league']['scoring_settings'] = scoring
            data['scoring_settings'] = scoring
            self.store.update_current(DAY, data)
            count, rows = self.store.records(DAY, 'player_week', limit=None)
            self.assertEqual(count, 285)
            self.assertTrue(all(r['payload']['fantasy_points'] is None for r in rows))
            self.assertTrue(any(r['payload']['source_fantasy_points'] > 0 for r in rows))
        data, _ = active_source()
        data['scoring_settings'] = {'rec': 999}
        self.store.update_current(DAY, data)
        self.assertTrue(all(r['payload']['fantasy_points'] is None for r in self.store.records(DAY, 'player_week', limit=None)[1]))
        compact = CanonicalHistoryStore()
        compact.update_current(DAY, compact_fois_input(data))
        self.assertTrue(all(r['payload']['fantasy_points'] is None for r in compact.records(DAY, 'player_week', limit=None)[1]))

    def test_source_identity_mismatch_and_uncompleted_periods_are_withheld(self):
        for key, value in (('league_id', ARK), ('season', '2025'), ('calendar_reference', 'foreign'), ('methodology', 'unknown')):
            data, _ = active_source()
            data['season_matchups'][key] = value
            self.store.update_current(DAY, data)
            self.assertEqual(self.store.records(DAY, 'player_week', limit=None)[0], 0)
        data, _ = active_source()
        data['league']['settings'].pop('last_scored_leg')
        self.store.update_current(DAY, data)
        self.assertEqual(self.store.records(DAY, 'player_week', limit=None)[0], 0)

    def test_source_revision_recovers_warm_player_index_and_league_isolation(self):
        day, _ = self.publish()
        self.publish(1)
        pid = '11563'
        original = player_career(DAY, pid)
        ark = player_career(ARK, pid)
        side = next(r for r in day['season_matchups']['weeks']['5']['rows'] if pid in r['players_points'])
        side['players_points'][pid] = 0
        self.store.update_current(DAY, day)
        changed = player_career(DAY, pid)
        self.assertNotEqual(original, changed)
        self.assertEqual(changed['seasons']['2026']['season_total'], 0)
        self.assertEqual(player_career(ARK, pid), ark)

    def test_actual_starter_total_excludes_bench_and_uses_legal_league_slots(self):
        for index in (0, 1):
            data, source = self.publish(index)
            league = data['league']['league_id']
            side = source['week5'][0]
            service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
            lineup, production = service._lineup_and_production(league,
                f"{league}:franchise:{side['roster_id']}", HistoricalBoundary(2026, week=6),
                set(side['players']), tuple(data['roster_positions']))
            self.assertEqual(lineup.actual_points, sum(side['players_points'][pid] for pid in side['starters'] if pid != '0'))
            self.assertEqual(set(lineup.actual_starters), set(side['starters']) - {'0'})
            self.assertIsNotNone(lineup.optimal_points)
            self.assertGreaterEqual(lineup.optimal_points, lineup.actual_points)
            self.assertEqual(len(set(lineup.optimal_starters)), len(lineup.optimal_starters))
            self.assertTrue(any(pid not in lineup.actual_starters and pid in production for pid in side['players']))

    def test_partial_week_coverage_is_not_complete_and_early_boundary_has_no_future_knowledge(self):
        data, source = self.publish()
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
        state = service.reconstruct(DAY, str(source['week5'][0]['roster_id']), HistoricalBoundary(2026, week=6))
        self.assertEqual(state.coverage['production'].availability.value, 'partial')
        self.assertLessEqual(state.coverage['production'].confidence, 40)
        coverage = self.store.source_coverage(DAY)['seasons'][0]['matchups']
        self.assertEqual(coverage['acquired'], [5])
        self.assertIn(1, coverage['unacquired'])
        self.assertFalse(coverage['complete_acquisition'])
        early = service.reconstruct(DAY, str(source['week5'][0]['roster_id']), HistoricalBoundary(2026, week=5, occurred_at='2026-10-08T00:00:00Z'))
        self.assertTrue(all(p.season_to_date_points is None for p in early.players))

    def test_prepared_rows_not_materialized_for_ordinary_identity_or_trade_reads(self):
        self.publish()
        with patch.object(self.store, '_source_player_week_rows', side_effect=AssertionError('irrelevant weekly projection')):
            self.store.records(DAY, 'franchise_identity', limit=None)
            self.store.records(DAY, 'trade', limit=None)

    def test_retained_and_active_consumer_counts_are_reconciled_once(self):
        data, source = self.publish()
        facts = {'league': data['league'], 'matchups': {'5': source['week5']}}
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        self.assertEqual(self.store.optional_records(DAY, 'player_week', season=2026, limit=None)[0], 285)
        self.assertEqual(self.store.season_player_leaders(DAY, 2026)[0], 285)

    def test_partial_retained_family_cannot_hide_valid_active_week(self):
        data, _ = self.publish()
        self.cache.write(self.cache.normalize(DAY, 2026, {'league': data['league']}))
        self.assertEqual(self.store.records(DAY, 'player_week', player_id='11563')[0], 1)
        self.assertIn('player_week', self.store.historical_availability(DAY, 2026)['covered_families'])

    def test_retained_future_placeholders_cannot_restore_excluded_actuals(self):
        data, source = self.publish()
        future = data['season_matchups']['weeks']['6']['rows']
        self.cache.write(self.cache.normalize(DAY, 2026, {'league': data['league'],
                         'matchups': {'5': source['week5'], '6': future}}))
        count, rows = self.store.records(DAY, 'player_week', season=2026, limit=None)
        self.assertEqual(count, 285)
        self.assertEqual({r['week'] for r in rows}, {5})
        self.assertEqual(self.store.season_player_leaders(DAY, 2026)[0], 285)

    def test_compact_and_real_spawn_preserve_active_production_and_birth_evidence(self):
        data, _ = self.publish()
        compact = compact_fois_input(data)
        self.assertIs(compact['season_matchups'], data['season_matchups'])
        context = multiprocessing.get_context('spawn')
        result = context.Queue()
        worker = context.Process(target=spawned_evidence, args=(compact, self.temp.name, result))
        start = perf_counter()
        worker.start()
        try:
            count, metadata = result.get(timeout=30)
            worker.join(10)
            self.assertEqual(worker.exitcode, 0)
            self.assertEqual(count, 285)
            self.assertEqual(metadata['birth_date'], data['players']['11563']['birth_date'])
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
            result.close()
            result.join_thread()
        self.assertFalse(worker.is_alive())
        print({'active_week_spawn_seconds': round(perf_counter() - start, 3), 'records': count,
               'birth_date_preserved': True, 'worker_reaped': True, 'fois_regeneration': False})
