"""Retained-source negative controls use actual publishers and history consumers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from time import perf_counter
import unittest

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.history import create_history_router
from services.history import player_career
from src.core.data_platform.normalization.birth_dates import historical_age
from src.core.historical_franchise_state import HistoricalBoundary, HistoricalFranchiseStateService
from src.core.historical_intelligence import HistoricalIntelligenceService
from src.core.history_context.assets import reconcile_player_weeks
from src.core.history_context.store import CanonicalHistoryStore
from src.core.history_context.recovery import HistoricalCheckpoints
from tests import test_historical_player_evidence as evidence


class HistoricalRetainedAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = evidence.HistoricalPlayerEvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.cache = self.fixture.store, self.fixture.cache

    def retained(self, data, source, *, future=False):
        weeks = {'5': deepcopy(source['week5'])}
        if future:
            weeks['6'] = deepcopy(data['season_matchups']['weeks']['6']['rows'])
        facts = {'league': deepcopy(data['league']), 'matchups': weeks}
        self.cache.write(self.cache.normalize(data['league']['league_id'], 2026, facts))
        return facts

    def test_missing_malformed_noninteger_completion_cannot_admit_retained_future_actuals(self):
        for marker in (None, '5', 'invalid', 5.0, 5.5, True, {}, [], -1, 99):
            with self.subTest(marker=marker):
                data, source = evidence.active_source()
                data['league']['settings']['last_scored_leg'] = marker
                self.store.update_current(evidence.DAY, data)
                self.retained(data, source, future=True)
                count, rows = self.store.optional_records(evidence.DAY, 'player_week', season=2026, limit=None)
                self.assertEqual(count, 0, [(r['week'], r['payload']['fantasy_points']) for r in rows[:2]])
                self.assertEqual(player_career(evidence.DAY, '11563')['weekly_record_count'], 0)
                self.assertEqual(self.store.season_player_leaders(evidence.DAY, 2026)[1], [])
                self.assertEqual(self.store.records(evidence.DAY, 'matchup', season=2026, limit=None)[0], 0)

    def test_supported_completion_preserves_exact_actuals_but_not_future_999(self):
        for index, expected in ((0, 285), (1, 273)):
            data, source = self.fixture.publish(index)
            league = data['league']['league_id']
            self.retained(data, source, future=True)
            count, rows = self.store.records(league, 'player_week', season=2026, limit=None)
            self.assertEqual(count, expected)
            self.assertEqual({r['week'] for r in rows}, {5})
            self.assertTrue(any(r['payload']['fantasy_points'] == 0 for r in rows))
            self.assertTrue(any(r['payload']['starter'] is False for r in rows))
            self.assertTrue(all(r['payload']['scoring_settings'] == source['league']['scoring_settings'] for r in rows))
            self.assertTrue(all(r['payload']['source_league_id'] == league for r in rows))
            self.assertTrue(all(r['payload']['source_generation'] for r in rows))
            self.assertEqual(self.store.season_player_leaders(league, 2026)[0], expected)
            actual = next(r['players_points']['11563'] for r in source['week5'] if '11563' in r['players_points'])
            self.assertEqual(player_career(league, '11563')['seasons']['2026']['season_total'], actual)

    def test_missing_or_incompatible_active_scoring_cannot_be_restored_from_retained_numbers(self):
        for case in ('missing', 'invalid', 'mismatched', 'lineup_mismatch'):
            with self.subTest(case=case):
                data, source = evidence.active_source()
                self.retained(data, source)
                if case == 'missing':
                    data['league']['scoring_settings'] = {}
                    data['scoring_settings'] = {}
                elif case == 'invalid':
                    data['league']['scoring_settings'] = {'rec': True}
                    data['scoring_settings'] = {'rec': True}
                elif case == 'mismatched':
                    data['scoring_settings'] = {'rec': 999}
                else:
                    data['roster_positions'] = ['QB']
                self.store.update_current(evidence.DAY, data)
                count, rows = self.store.records(evidence.DAY, 'player_week', season=2026, limit=None)
                self.assertEqual(count, 285)
                self.assertTrue(all(r['payload']['fantasy_points'] is None for r in rows))
                self.assertTrue(all(r['payload']['scoring_context_availability'] == 'unavailable_or_incompatible' for r in rows))
                self.assertTrue(any(r['payload']['source_fantasy_points'] > 0 for r in rows))
                self.assertEqual(self.store.season_player_leaders(evidence.DAY, 2026)[1], [])
                self.assertIsNone(player_career(evidence.DAY, '11563')['seasons']['2026']['season_total'])
                service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
                side = next(r for r in source['week5'] if '11563' in r['players_points'])
                _, production = service._lineup_and_production(evidence.DAY,
                    f"{evidence.DAY}:franchise:{side['roster_id']}", HistoricalBoundary(2026, week=6),
                    set(side['players']), tuple(source['league']['roster_positions']))
                self.assertEqual(production, {})

    def test_retained_only_scoring_and_source_identity_are_required(self):
        for case in ('missing_scoring', 'invalid_scoring', 'missing_source', 'wrong_season'):
            with self.subTest(case=case):
                data, source = evidence.active_source()
                if case == 'missing_scoring':
                    data['league'].pop('scoring_settings')
                elif case == 'invalid_scoring':
                    data['league']['scoring_settings'] = {'rec': None}
                elif case == 'missing_source':
                    data['league'].pop('league_id')
                else:
                    data['league']['season'] = '2025'
                facts = {'league': data['league'], 'matchups': {'5': source['week5']}}
                self.cache.write(self.cache.normalize(evidence.DAY, 2026, facts))
                rows = self.store.optional_records(evidence.DAY, 'player_week', season=2026, limit=None)[1]
                self.assertTrue(all(r['payload']['fantasy_points'] is None for r in rows))
                self.assertEqual(self.store.season_player_leaders(evidence.DAY, 2026)[1], [])

    def test_retained_scoring_conflict_with_same_season_cannot_select_one_context(self):
        data, source = self.fixture.publish()
        data = deepcopy(data)
        data['league']['scoring_settings']['rec'] += 1
        self.retained(data, source)
        rows = self.store.records(evidence.DAY, 'player_week', season=2026, limit=None)[1]
        self.assertTrue(all(r['payload']['fantasy_points'] is None for r in rows))
        self.assertEqual(self.store.season_player_leaders(evidence.DAY, 2026)[1], [])

    def test_reconciliation_keeps_unavailable_scoring_qualification(self):
        data, _ = self.fixture.publish()
        row = self.store.records(evidence.DAY, 'player_week', season=2026, limit=None)[1][0]
        bad = deepcopy(row)
        bad['payload'].update(fantasy_points=None, points=None, scoring_context_availability='unavailable_or_incompatible')
        for values in ([row, bad], [bad, row]):
            merged = reconcile_player_weeks(values)[0]
            self.assertIsNone(merged['payload']['fantasy_points'])
            self.assertEqual(merged['payload']['scoring_context_availability'], 'unavailable_or_incompatible')
            self.assertIsNone(reconcile_player_weeks([merged])[0]['payload']['fantasy_points'])

    def test_conflict_survives_rejected_identity_then_single_date_and_restart(self):
        def update(date, **extra):
            data = {'league': {'league_id': evidence.DAY, 'season': '2026'}, 'normalized_players': {
                'p': {'name': 'Supported Player', 'provider_ids': {'Sleeper': 'p'}, 'birth_date': date, **extra}}}
            self.store.update_current(evidence.DAY, data)
            return data
        update('2000-01-01')
        update('2001-01-01')
        original = deepcopy(self.store.identity_for_provider_id('p')['metadata'])
        rejected = update('1999-01-01', provider_ids={'Sleeper': 'foreign-player'})
        metadata = self.store.identity_for_provider_id('p')['metadata']
        self.assertEqual(metadata['birth_date_status'], 'conflicting')
        self.assertEqual(metadata['birth_date_candidates'], original['birth_date_candidates'])
        self.assertNotIn('1999-01-01', json.dumps(rejected['normalized_players']['p']))
        self.assertIsNone(historical_age(metadata, '2026-10-17T00:00:00Z')[0])
        restarted = CanonicalHistoryStore()
        restarted.update_current(evidence.DAY, json.loads(json.dumps(rejected)))
        restarted.update_current(evidence.DAY, {'normalized_players': {'p': {'birth_date': '2000-01-01'}}})
        self.assertEqual(restarted.identity_for_provider_id('p')['metadata']['birth_date_status'], 'conflicting')
        update('2000-01-01')
        self.assertEqual(self.store.identity_for_provider_id('p')['metadata']['birth_date_status'], 'conflicting')

    def test_correct_identity_without_conflict_retains_historical_age(self):
        data, _ = self.fixture.publish()
        meta = self.store.identity_for_provider_id('11563')['metadata']
        self.assertEqual(historical_age(meta, '2026-10-14T00:00:00Z')[0], 26.63)
        self.store.update_current(evidence.DAY, {'normalized_players': {'11563': {'birth_date': meta['birth_date']}}})
        self.assertEqual(self.store.identity_for_provider_id('11563')['metadata']['birth_date_status'], 'supported')

    def test_completed_historical_season_uses_its_own_supported_scoring(self):
        for index, expected in ((0, 285), (1, 273)):
            data, source = evidence.active_source(index)
            league = data['league']['league_id']
            historical = deepcopy(data['league'])
            historical.update(league_id=f'historical-{league}', season='2025', status='complete')
            historical['settings'].pop('last_scored_leg')
            self.cache.write(self.cache.normalize(league, 2025, {'league': historical, 'matchups': {'5': source['week5']}}))
            # Different current-season scoring does not replace historical rules.
            data['scoring_settings'] = data['league']['scoring_settings'] = {'rec': 999}
            self.store.update_current(league, data)
            rows = self.store.records(league, 'player_week', season=2025, limit=None)[1]
            self.assertEqual(len(rows), expected)
            self.assertTrue(all(r['payload']['fantasy_points'] is not None for r in rows))
            self.assertTrue(all(r['payload']['source_league_id'] == historical['league_id'] for r in rows))
            self.assertTrue(all(r['payload']['scoring_settings'] == historical['scoring_settings'] for r in rows))

    def test_legacy_checkpoint_cannot_bypass_completion_or_scoring(self):
        for season, case in ((2023, 'completion'), (2024, 'scoring'), (2025, 'supported')):
            data, source = evidence.active_source()
            league = deepcopy(data['league'])
            league.update(season=str(season), status='in_season')
            if case == 'completion':
                league['settings'].pop('last_scored_leg')
            if case == 'scoring':
                league['scoring_settings'] = {}
            payload = {'sleeper_season_league_id': league['league_id'], 'sleeper_season': league['season'],
                       'settings': league['settings'], 'status': league['status'],
                       'scoring_settings': league['scoring_settings'], 'roster_positions': league['roster_positions']}
            rows = [self.store._record(evidence.DAY, season, 'league_season', evidence.DAY, payload)]
            side = source['week5'][0]
            rows += self.store._source_player_week_rows(evidence.DAY, season, 5, side)
            HistoricalCheckpoints(self.cache.root).preserve(league=evidence.DAY, season=season,
                source_league=evidence.DAY, source_checksum=f'legacy-{case}', records=rows,
                families={'league_season', 'player_week'})
            count, admitted = self.store.optional_records(evidence.DAY, 'player_week', season=season, limit=None)
            if case == 'completion':
                self.assertEqual(count, 0)
            elif case == 'scoring':
                self.assertTrue(all(r['payload']['fantasy_points'] is None for r in admitted))
                self.assertEqual(self.store.season_player_leaders(evidence.DAY, season)[1], [])
            else:
                self.assertEqual(count, len(side['players_points']))
                self.assertTrue(any(r['payload']['fantasy_points'] > 0 for r in admitted))

    def test_actual_history_http_omits_unverified_future_total(self):
        data, source = evidence.active_source()
        data['league']['settings'].pop('last_scored_leg')
        self.store.update_current(evidence.DAY, data)
        self.retained(data, source, future=True)
        app = FastAPI()
        app.include_router(create_history_router(league_id=evidence.DAY, require_data=lambda: data,
                           page=lambda title, body: HTMLResponse(body)))
        with TestClient(app) as client:
            response = client.get('/history/player/11563')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('999', response.text)
        self.assertEqual(player_career(evidence.DAY, '11563')['weekly_record_count'], 0)

    def test_checkpoint_record_cannot_disagree_with_its_retained_context(self):
        data, source = evidence.active_source()
        facts = self.retained(data, source)
        rows = self.store._season_records(evidence.DAY, 2026)
        checksum = self.cache.read(evidence.DAY, 2026).checksum
        checkpoint = {'records': rows, 'source_checksum': checksum}
        for field, value in (('scoring_settings', {'rec': 999}), ('source_league_id', evidence.ARK),
                             ('source_generation', 'unrelated-publication'), ('roster_positions', ['QB'])):
            with self.subTest(field=field):
                changed = deepcopy(checkpoint)
                for row in changed['records']:
                    if row['entity_type'] == 'player_week':
                        row['payload'][field] = value
                admitted = self.store._admit_checkpoint_rows(evidence.DAY, 2026, changed)
                self.assertTrue(all(row['payload']['fantasy_points'] is None
                                    for row in admitted if row['entity_type'] == 'player_week'))
        self.assertEqual(facts['league']['league_id'], evidence.DAY)

    def test_source_replacement_recovers_warm_cache_without_read_writes(self):
        data, source = self.fixture.publish()
        self.retained(data, source, future=True)
        self.assertEqual(player_career(evidence.DAY, '11563')['weekly_record_count'], 1)
        data['league']['settings']['last_scored_leg'] = 'unverified'
        self.store.update_current(evidence.DAY, data)
        self.retained(data, source, future=True)
        self.assertEqual(player_career(evidence.DAY, '11563')['weekly_record_count'], 0)
        data['league']['settings']['last_scored_leg'] = 5
        self.store.update_current(evidence.DAY, data)
        self.retained(data, source, future=True)
        root = Path(self.fixture.temp.name)
        def files():
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        player_career(evidence.DAY, '11563')
        before = files()
        before_bytes = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
        def database_rows():
            with sqlite3.connect(self.store.path) as connection:
                tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                return {name: connection.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                        for name in tables}
        before_rows = database_rows()
        started = perf_counter()
        for _ in range(20):
            self.assertEqual(player_career(evidence.DAY, '11563')['weekly_record_count'], 1)
            self.store.season_player_leaders(evidence.DAY, 2026)
        self.assertEqual(files(), before)
        self.assertEqual(database_rows(), before_rows)
        self.assertEqual(sum(p.stat().st_size for p in root.rglob('*') if p.is_file()), before_bytes)
        print({'retained_settled_reads': 40, 'source_files_before_after': len(before),
               'source_bytes_before_after': before_bytes, 'database_rows_before_after': before_rows,
               'all_hashes_unchanged': True, 'elapsed_ms': round((perf_counter() - started) * 1000, 3)})
