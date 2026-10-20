"""Source-produced rollover, checkpoint clocks and actual FOIS profile controls."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.fois import create_fois_router
from services.sleeper import selected_league_week
from src.core.intelligence.team_strength import compatible_profile, prepare_for_data
from src.core.intelligence_memory.models import CheckpointTrigger, EvidenceCompleteness, ProvenanceType
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.projection_intelligence.service import ProjectionService
from src.platform.observability import RequestObservabilityMiddleware
from tests.test_market_observation_producer_identity import checkpoint, prepared
from tests import test_fois_presentation as presentation
from tests.test_trade_intelligence import fixture_data


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def strength_source(self, league_id='A'):
        data = fixture_data()
        data['league'].update(league_id=league_id, season='2026', sport='nfl', status='in_season',
            settings={'leg': 6, 'last_scored_leg': 6, 'start_week': 1, 'playoff_week_start': 14,
                      'playoff_teams': 6, 'playoff_round_type': 1, 'playoff_type': 0})
        data['nfl_state'] = {'season': '2026', 'week': 7, 'season_type': 'regular'}
        data['week'] = selected_league_week(data['league'], data['nfl_state'])
        players = [p for team in data['teams'] for p in team['players']]
        data['players'] = {p['id']: p for p in players}
        payloads = {w: [{'player_id': p['id'], 'season': 2026, 'week': w,
                        'player': {'position': p['position']}, 'stats': {'pass_yd': 100}}
                       for p in players] for w in range(7, 19)}
        service = ProjectionService(self.root / (league_id + '.sqlite3'), league_id=league_id)
        service.publish_horizon(payloads, data=data, league_id=league_id, season=2026, current_week=7)
        return service, data

    def test_real_publisher_rollover_and_independent_leagues(self):
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            for league in ('1313066632158924800', '1319750579458686976'):
                service, data = self.strength_source(league)
                profile = prepare_for_data(service, data)
                self.assertEqual(profile['current_week'], 7)
                self.assertEqual(profile['league_id'], league)
                self.assertEqual(data['league']['settings']['leg'], 6)
                self.assertIs(compatible_profile(data, service.snapshot()), profile)
                self.assertEqual(profile['calendar']['availability'], 'supported')

    def test_mismatched_week_scoring_generation_and_missing_clock_withheld(self):
        service, data = self.strength_source()
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            profile = prepare_for_data(service, data)
            for mode in ('week', 'clock', 'scoring', 'generation', 'league', 'season'):
                changed = deepcopy(data)
                if mode == 'week':
                    changed['week'] = 8
                elif mode == 'clock':
                    changed.pop('nfl_state')
                elif mode == 'scoring':
                    changed['scoring_settings'] = {'rec': 42}
                elif mode == 'generation':
                    changed['team_strength']['projection_generation'] = 'old'
                elif mode == 'league':
                    changed['league']['league_id'] = 'foreign'
                else:
                    changed['league']['season'] = '2027'
                self.assertIsNone(compatible_profile(changed, service.snapshot()), mode)
                if mode in ('week', 'clock', 'scoring'):
                    with self.assertRaises(ValueError):
                        prepare_for_data(service, changed)
            self.assertEqual(profile['projection_generation'], service.snapshot()['horizon_generation'])
            for override in ({'week': 8}, {'season': 2027}, {'horizon_generation': None},
                             {'scoring_profile_id': 'foreign'}):
                self.assertIsNone(compatible_profile(data, {**service.snapshot(), **override}), override)

    def test_one_projection_publication_is_pinned_during_preparation(self):
        service, data = self.strength_source()
        original = service.snapshot()
        with patch.object(service, 'snapshot', side_effect=[original, None]), \
                patch('services.global_evidence.retained_global_evidence', return_value=None):
            profile = prepare_for_data(service, data)
        self.assertEqual(profile['projection_generation'], original['horizon_generation'])

    def test_scheduled_real_market_zero_uses_observation_time_not_week_label(self):
        data, _ = prepared(0)
        data['league'] = {'league_id': 'A', 'season': '2026', 'status': 'in_season',
                          'settings': {'playoff_week_start': 15}}
        data['week'] = 7
        data['relevant_player_universe'] = {'members': [{'player_id': '1', 'reason_codes': ['current_roster']}]}
        store = IntelligenceCheckpointStore(self.root / 'checkpoints.sqlite3')
        pipeline = CheckpointPipeline(IntelligenceMemoryService(store))
        pipeline.ingest_scheduled(data, observed_at='2026-09-01T14:00:00+02:00')
        rows = store.checkpoints(asset_id='player:1')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].timestamp, '2026-09-01T12:00:00+00:00')
        self.assertEqual(rows[0].market_value, 0)
        self.assertEqual(rows[0].week, 7)
        pipeline.ingest_scheduled(data, observed_at='2026-09-02T12:00:00Z')
        self.assertEqual(len(store.checkpoints(asset_id='player:1')), 1)

    def test_bad_checkpoint_is_skipped_without_losing_adjacent_good_event(self):
        pipeline = CheckpointPipeline(IntelligenceMemoryService(IntelligenceCheckpointStore(self.root / 'safe.db')))
        for n, time in enumerate((None, '2026-W07', 'broken', '2026-09-01T12:00:00', {}, True)):
            pipeline._capture(CheckpointTrigger.MIDSEASON, asset_id='player:1', asset_type='player',
                timestamp=time, season=2026, provenance=ProvenanceType.LIVE_CAPTURED, event_id=str(n))
        pipeline._capture(CheckpointTrigger.MIDSEASON, asset_id='player:1', asset_type='player',
            timestamp='2026-09-01T12:00:00Z', season=2026, provenance=ProvenanceType.LIVE_CAPTURED,
            event_id='valid', market_value=0, completeness=EvidenceCompleteness.COMPLETE)
        self.assertEqual(len(pipeline.service.store.checkpoints(asset_id='player:1')), 1)
        self.assertEqual(pipeline.health()['invalid_timestamp_skips'], 6)

    def test_store_cannot_compare_provider_time_with_unsupported_week_label(self):
        data, _ = prepared()
        evidence = CheckpointPipeline._market_observations(data, 'player:1')
        store = IntelligenceCheckpointStore(self.root / 'direct.db')
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            store.put_sparse(checkpoint('bad', 9000, '2026-W07'), market_context_id='same', provider_evidence=evidence)
        self.assertEqual(store.checkpoints(asset_id='player:1'), [])

    def test_quote_cutoff_is_typed_not_lexical_and_invalid_quotes_are_unavailable(self):
        data, _ = prepared()
        evidence = CheckpointPipeline._market_observations(data, 'player:1')
        service = IntelligenceMemoryService(IntelligenceCheckpointStore(self.root / 'cutoff.db'))
        for n, quote in enumerate(('2026-09-01T12:00:00.1Z', 'malformed', None, '2026-09-01T12:00:00')):
            rows = tuple(replace(row, observed_at=quote) for row in evidence)
            result = service.capture_detailed(asset_id='player:1', asset_type='player',
                timestamp='2026-09-01T12:00:00Z', season=2026, trigger=CheckpointTrigger.MIDSEASON,
                provenance=ProvenanceType.LIVE_CAPTURED, market_value=0, event_id=str(n),
                market_observations=rows)
            self.assertIsNone(result.checkpoint.market_value, quote)

    def test_valid_retained_timestamp_identity_reuses_resolution_without_provider_calls(self):
        from tests import test_sparse_historical_market as sparse
        store = IntelligenceCheckpointStore(self.root / 'resolution.db')
        for i, stamp in enumerate(('2023-10-03T00:00:00Z', '2023-10-03T00:00:00+00:00')):
            provider = sparse.Provider((sparse.source(value=0),))
            resolver = sparse.HistoricalMarketResolver(store, (provider,))
            original = replace(sparse.checkpoint(event_id='same-format-' + str(i)), timestamp=stamp)
            context = sparse.market_context_id(asset_type='player', scoring_profile_id=None)
            _, stored, _, _ = resolver.resolve_checkpoint(original, market_context_id=context,
                persistence=sparse.PersistenceContext('trade_execution'))
            self.assertEqual(stored.timestamp, stamp)
            before = store.path.read_bytes()
            # A new resolver has no in-memory provider cache to mask a miss.
            provider = sparse.Provider()
            again = sparse.HistoricalMarketResolver(store, (provider,))
            result, stored, created, _ = again.resolve_checkpoint(original, market_context_id=context,
                persistence=sparse.PersistenceContext('trade_execution'))
            self.assertEqual(provider.calls, 0)
            self.assertEqual(result.selection.value, 0)
            self.assertFalse(created)
            self.assertEqual(store.path.read_bytes(), before)


class ProfileTraceTests(unittest.TestCase):
    def test_actual_profile_stages_without_computation_or_private_trace_payload(self):
        fixture = presentation.FOISPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        score, = fixture._persist_profiles('active-league', 1)
        app = FastAPI()
        app.add_middleware(RequestObservabilityMiddleware)
        app.include_router(create_fois_router(service=fixture.service, require_data=lambda: fixture.data))
        with patch.object(fixture.service, 'generate', side_effect=AssertionError('read must not compute')), \
                self.assertLogs('dtos.attribution', level='INFO') as captured, TestClient(app) as client:
            response = client.get('/fois/gms/' + score.gm_id,
                headers={'X-Request-ID': 'profile-control', 'X-DTOS-Diagnostics': '1'})
        self.assertEqual(response.status_code, 200)
        rows = [r.diagnostic for r in captured.records if hasattr(r, 'diagnostic')]
        for name in ('fois_profile', 'fois_profile_context', 'fois_profile_lookup',
                     'fois_profile_validation', 'fois_profile_history', 'fois_profile_aggregation', 'fois_profile_render'):
            self.assertTrue(any(r['name'] == name and r['boundary'] == 'finished' for r in rows), name)
        self.assertNotIn(score.gm_id, json.dumps(rows))
        self.assertTrue(all(r.request_id == 'profile-control' for r in captured.records))

    def test_lookup_delay_is_attributed_and_reads_do_not_write(self):
        fixture = presentation.FOISPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        score, = fixture._persist_profiles('active-league', 1)
        before = fixture.repository.path.read_bytes()
        entered, release = threading.Event(), threading.Event()
        original = fixture.repository.score_for_gm

        def blocked(*args):
            entered.set()
            if not release.wait(5):
                raise AssertionError('controlled lookup was not released')
            return original(*args)

        app = FastAPI()
        app.add_middleware(RequestObservabilityMiddleware)
        app.include_router(create_fois_router(service=fixture.service, require_data=lambda: fixture.data))
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool, \
                patch.object(fixture.repository, 'score_for_gm', side_effect=blocked), \
                self.assertLogs('dtos.attribution', level='INFO') as captured:
            future = pool.submit(client.get, '/fois/gms/' + score.gm_id,
                headers={'X-Request-ID': 'blocked-profile', 'X-DTOS-Diagnostics': '1'})
            try:
                self.assertTrue(entered.wait(3))
                self.assertFalse(future.done())
                self.assertFalse(any(getattr(r, 'diagnostic', {}).get('name') == 'fois_profile_lookup'
                    and r.diagnostic.get('boundary') == 'finished' for r in captured.records))
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5).status_code, 200)
        rows = [r.diagnostic for r in captured.records if hasattr(r, 'diagnostic')]
        lookup = next(r for r in rows if r['name'] == 'fois_profile_lookup' and r['boundary'] == 'finished')
        total = next(r for r in rows if r['name'] == 'fois_profile' and r['boundary'] == 'finished')
        self.assertGreaterEqual(total['duration_ms'], lookup['duration_ms'])
        self.assertEqual(lookup['parent_span_id'], total['span_id'])
        self.assertEqual(fixture.repository.path.read_bytes(), before)


class ProfilePhoneTests(unittest.TestCase):
    def test_authenticated_profile_phone_geometry_and_read_only_storage(self):
        from dataclasses import replace
        from src.core.accounts import AccountService, AccountStore
        from src.platform.account_context import AccountContextMiddleware
        from src.core.fois.models import FOIS_EVIDENCE_INTEGRITY_VERSION
        from tests import test_public_readiness as onboarding
        import dtos_app
        fixture = presentation.FOISPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        score, = fixture._persist_profiles('active-league', 1)
        fixture.repository.save(replace(score, evidence_integrity_version=FOIS_EVIDENCE_INTEGRITY_VERSION), 'qualified')
        store = AccountStore(Path(fixture.directory.name) / 'accounts.db')
        service = AccountService(store)
        account, _ = service.create_account('profile-fixture', 'Profile fixture', 'isolated fixture password')
        store.link_sleeper(account, sleeper_user_id='profile-user', username='profile-fixture', display_name='Profile fixture')
        store.upsert_membership(account, {'league_id': 'active-league', 'name': 'Profile league', 'season': '2026'},
                                'profile-user', 1, 'Profile franchise', 'active')
        store.activate(account, 'active-league')
        token, _ = service.new_session(account)
        self.app = FastAPI()
        self.app.add_middleware(AccountContextMiddleware, service=service, required=True)
        self.app.include_router(create_fois_router(service=fixture.service, require_data=lambda: fixture.data, page=dtos_app.page))
        from fastapi.staticfiles import StaticFiles
        self.app.mount('/static', StaticFiles(directory=Path('static')), name='static')
        self.token = token
        before = fixture.repository.path.read_bytes()
        measurements = []
        with patch.object(fixture.service, 'generate', side_effect=AssertionError('profiles cannot regenerate')):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                with onboarding.PublicOnboardingTests.browser(self, width, height) as page:
                    response = page.goto(self.origin + '/fois/gms/' + score.gm_id, wait_until='networkidle')
                    self.assertEqual(response.status, 200)
                    self.assertIn('Executive 1', page.inner_text('body'))
                    geometry = page.evaluate('''() => ({width:innerWidth, scroll:document.documentElement.scrollWidth,
                        profile:document.querySelector('.fois-profile').getBoundingClientRect().toJSON(),
                        firstAction:document.querySelector('.fois-profile a').getBoundingClientRect().toJSON()})''')
                    self.assertLessEqual(geometry['scroll'], width + 1)
                    control = page.get_by_text('Supporting evidence and limitations', exact=True)
                    control.focus()
                    page.keyboard.press('Enter')
                    self.assertTrue(control.evaluate('e=>e.parentElement.open'))
                    self.assertNotEqual(control.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                    geometry.update(height=height, disclosure_open=True)
                    measurements.append(geometry)
        self.assertEqual(fixture.repository.path.read_bytes(), before)
        import os
        output = os.environ.get('DTOS_PREPARATION_BROWSER_EVIDENCE')
        if output:
            Path(output).write_text(json.dumps(measurements, indent=2))


if __name__ == '__main__':
    unittest.main()
