"""Source disclosures are scoped observations, never new calculation inputs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.data_platform.defaults import build_data_platform
from src.core.data_platform.provider_activation import provider_catalog
from tests import test_sleeper_actual_results as native


class ScopedSourceHealthTests(unittest.TestCase):
    def setUp(self):
        self.data = native.actual_data()
        self.data['players']['4984'] = {'full_name': 'Fixture Quarterback', 'position': 'QB', 'team': 'BUF'}
        native.publish(self.data)
        self.data['market_data'] = {'provider_status': provider_catalog()}
        stamp = datetime.now(timezone.utc).isoformat()
        self.data['projection_intelligence'] = {
            'league_id': 'A', 'season': 2026, 'week': 9, 'projection_snapshot_id': 'leaf-a',
            'scoring_settings': self.data['scoring_settings'], 'generated_at': stamp,
            'players': {'4984': {'provider': 'Sleeper', 'canonical_projection': 20.424,
                'weekly_projected_points': 20.424, 'source_timestamp': stamp}}}
        self.platform = build_data_platform()

    def report(self, **kwargs):
        return self.platform.player_report('4984', self.data, **kwargs)

    def test_prepared_projection_and_actuals_do_not_claim_disabled_or_waiting(self):
        before = deepcopy(self.data)
        report = self.report()
        health = report['provider_health']
        self.assertEqual(report['player_context']['projection_evidence']['value'], 20.424)
        self.assertEqual(health['Projections']['status'], 'available')
        self.assertEqual(health['Projections']['prepared_observations'], 1)
        self.assertEqual(health['Projections']['scope']['player_id'], '4984')
        self.assertIsNone(health['Projections']['records_retrieved'])
        self.assertEqual(health['Production']['prepared_observations'], 8)
        self.assertEqual(health['Production']['status'], 'available')
        self.assertIn('observed sample', health['Production']['reason'])
        self.assertEqual(self.data, before)

    def test_capability_without_context_has_unknown_coverage_and_no_invented_clock(self):
        for name in ('Projections', 'Production', 'Usage'):
            row = provider_catalog()[name]
            self.assertTrue(row['enabled'])
            self.assertEqual(row['status'], 'unknown')
            self.assertIsNone(row['last_refresh'])
            self.assertIsNone(row['records_retrieved'])

    def test_one_supported_player_never_marks_another_player_or_catalog_complete(self):
        self.data['players']['other'] = {'full_name':'Other Fixture', 'position':'RB'}
        report = self.platform.player_report('other', self.data)
        for family in ('Projections','Production','Usage'):
            self.assertEqual(report['provider_health'][family]['status'],'unavailable')
            self.assertEqual(report['provider_health'][family]['prepared_observations'],0)
            self.assertEqual(report['provider_health'][family]['scope']['player_id'],'other')
        self.assertEqual(self.report()['provider_health']['Projections']['status'],'available')

    def test_default_and_connected_restore_report_same_native_result_coverage(self):
        from tests import test_sleeper_actual_restoration as fixtures
        f = fixtures.ActualRestorationTests()
        self.addCleanup(f.doCleanups)
        _, data = f.fixture()
        reports = []
        for default in (True,False):
            restored = f.restore(deepcopy(data),default=default)
            report = self.platform.player_report('1',restored)
            health = report['provider_health']['Production']
            self.assertEqual(health['status'],'available')
            self.assertEqual(health['prepared_observations'],8)
            reports.append(health)
        self.assertEqual(reports[0],reports[1])

    def test_zero_negative_missing_and_placeholder_only_projection_remain_distinct(self):
        row = self.data['projection_intelligence']['players']['4984']
        for value in (0, -2.125, None):
            row.update(canonical_projection=value, weekly_projected_points=value)
            report = self.report()
            self.assertEqual(report['player_context']['projection_evidence']['value'], value)
            self.assertEqual(report['provider_health']['Projections']['status'], 'unavailable' if value is None else 'available')
        row.update(projected_stats={'adp_dynasty': 8}, missing_projection_reason='NO_SCORING_STATISTICS')
        self.assertIsNone(self.report()['player_context']['projection_evidence']['value'])
        row.update(canonical_projection=0, weekly_projected_points=1)
        self.assertEqual(self.report()['provider_health']['Projections']['status'], 'unavailable')

    def test_aging_and_failed_refresh_preserve_value_and_original_clocks(self):
        row = self.data['projection_intelligence']['players']['4984']
        row['source_timestamp'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        service = Mock()
        service.refresh_evidence.return_value = {'retained_publication': True, 'failed_at': '2026-11-15T00:00:00Z'}
        report = self.report(projection_service=service)
        self.assertEqual(report['provider_health']['Projections']['freshness'], 'Stale')
        self.assertTrue(report['provider_health']['Projections']['refresh_failure']['retained_publication'])
        self.assertEqual(report['player_context']['projection_evidence']['value'], 20.424)
        self.assertEqual(report['provider_health']['Projections']['source_updated_at'], row['source_timestamp'])

    def test_foreign_league_season_scoring_and_generation_are_not_admitted(self):
        original = deepcopy(self.data)
        for field, value in (('league_id', 'B'), ('season', 2025), ('week', 10),
                             ('scoring_settings', {'rec': 99}), ('projection_snapshot_id', None)):
            self.data = deepcopy(original)
            self.data['projection_intelligence'][field] = value
            report = self.report()
            self.assertIsNone(report['player_context']['projection_evidence']['value'])
            self.assertEqual(report['provider_health']['Projections']['status'], 'unavailable')
        self.data = deepcopy(original)
        self.data['canonical_player_production']['league_id'] = 'B'
        self.assertEqual(self.report()['provider_health']['Production']['status'], 'unavailable')

    def test_partial_native_scores_and_auxiliary_usage_remain_independent(self):
        self.data = native.actual_data(scores=(0, -2.125, None))
        self.data['players']['4984'] = {'full_name': 'Fixture Quarterback', 'position': 'QB'}
        production = native.publish(self.data)
        production['players']['4984'] = {'non_sleeper_analysis': {
            'updated_at': native.STAMP, 'windows': [{'label': 'Season Average',
            'observation_count': 3, 'targets': 0, 'carries': 2, 'fantasy_points': None}]}}
        production['source_checks'] = {'2026': {'status': 'failed', 'checked_at': native.STAMP}}
        health = self.report()['provider_health']
        self.assertEqual(health['Production']['status'], 'partial')
        self.assertEqual(health['Production']['prepared_observations'], 2)
        self.assertEqual(health['Usage']['status'], 'available')
        self.assertEqual(health['Usage']['refresh_failure']['status'], 'failed')
        self.assertIn('not fantasy results', health['Usage']['configured_capability'])
        self.assertEqual(health['Usage']['observation_boundary'], native.STAMP)

    def test_rendered_api_uses_same_scoped_health_without_refresh_or_mutation(self):
        from routes.api import create_api_router
        app = FastAPI()
        ensure, sync = AsyncMock(), AsyncMock(side_effect=AssertionError('No sync on read'))
        app.include_router(create_api_router(ensure_fresh=ensure, require_data=lambda:self.data,
            sync_sleeper=sync, state={'data':self.data}, league_id='A'))
        before = deepcopy(self.data)
        with patch('routes.api.data_platform', self.platform), patch('services.global_evidence.canonical_player_evidence', return_value={}):
            with TestClient(app) as client:
                payload = client.get('/api/players/4984/intelligence').json()
                self.assertEqual(payload['player_context']['projection_evidence']['value'], 20.424)
                self.assertEqual(payload['provider_health']['Projections']['status'], 'available')
                self.assertEqual(payload['provider_health']['Production']['prepared_observations'], 8)
                self.data['league']['league_id'] = 'B'
                self.assertEqual(client.get('/api/players/4984/intelligence').status_code, 503)
        sync.assert_not_called()
        self.data['league']['league_id'] = 'A'
        self.assertEqual(self.data, before)

    def test_rendered_dossier_preserves_supported_actual_results(self):
        from tests import test_current_production_coverage as fixtures
        f = fixtures.ProductionViewFixture(self)
        response = f.f.client.get('/players/1?front_office=4')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('this legacy context does not attach a production window', response.text)
        self.assertIn('18.00 fantasy points per score observation', response.text)
        self.assertIn('8 of 8 completed-week score observations', response.text)
