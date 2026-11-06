"""Retained native scores bind before either cache path exposes consumers."""
from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from services import league_preparation, sleeper
from src.core.league_runtime import LeagueRuntime
from src.core.player_value_projection.canonical_production import prepared_production_context
from tests import test_current_production_coverage as views


class ActualRestorationTests(unittest.TestCase):
    def fixture(self):
        f = views.ProductionViewFixture(self)
        data = copy.deepcopy(f.f.data)
        data['canonical_player_production'].pop('sleeper_actuals')
        old = asdict(prepared_production_context(data['canonical_player_production'],
            league_id=data['league']['league_id'], player_id='1', data=data))
        data['valuation_intelligence']['assets']['player:1']['canonical_production'] = old
        return f, data

    def write(self, data):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        path = Path(directory)/'cache.json'
        path.write_text(json.dumps({'data':data, 'last_sync':datetime.now(timezone.utc).isoformat()}))
        return path

    def restore(self, data, *, default=False, publish=None):
        path = self.write(data)
        lid = str(data['league']['league_id'])
        if default:
            state = {}
            with patch.object(sleeper, 'league_cache_file', return_value=path):
                sleeper.load_cache(state=state, league_id=lid)
            return state['data']
        runtime = LeagueRuntime(lid)
        with patch.object(league_preparation, 'league_cache_file', return_value=path):
            self.assertTrue(league_preparation.restore_cached_runtime(runtime, publish or Mock(),
                expected_season=int(data['league']['season'])))
        return runtime.state['data']

    def profile(self, data):
        return prepared_production_context(data['canonical_player_production'],
            league_id=data['league']['league_id'], player_id='1', data=data)

    def render(self, f, data):
        f.f.data = data
        f.f.state['data'] = data
        f.f.cache.clear()
        f.f.market = f.f.cache.get(data, f.f.state, f.f.history, str(data['league']['league_id']))
        return [f.f.client.get(path) for path in ('/players/1?front_office=4',
            '/market?selected=player%3A1', '/api/market/assets/player:1')]

    def test_matched_default_and_connected_restoration_reach_rendered_consumers(self):
        f, data = self.fixture()
        expected = data['season_matchups']['weeks']['1']['rows'][0]['players_points']['1']
        snapshots = []
        for default in (True, False):
            with self.subTest(default=default):
                restored = self.restore(data, default=default)
                context = self.profile(restored)
                self.assertTrue(context.observations, context.limitations)
                self.assertEqual(context.observations[0]['points'], expected)
                snapshots.append(asdict(context))
                dossier, market, api = self.render(f, restored)
                for response in (dossier, market, api):
                    self.assertEqual(response.status_code, 200, response.text[:800])
                for response in (dossier, market):
                    self.assertIn('18.00 fantasy points per score observation', response.text)
                    self.assertNotIn('Compatible Sleeper actual results are not prepared', response.text)
                actual = api.json()['valuation']['canonical_production']
                self.assertEqual(actual['observations'][0]['points'], expected)
                self.assertEqual(actual['source_generation'], data['season_matchups']['semantic_generation'])
        if len(snapshots) == 2:
            self.assertEqual(*snapshots)

    def test_missing_preparation_and_pre_adapter_cache_bind_native_rows_only(self):
        for legacy in (False, True, 'empty'):
            for default in (False, True):
                with self.subTest(legacy=legacy, default=default):
                    f, data = self.fixture()
                    data.pop('canonical_player_production')
                    if legacy == 'empty':
                        data['canonical_player_production'] = {}
                    elif legacy:
                        data['season_matchups'].pop('scoring_fingerprint')
                    restored = self.restore(data, default=default)
                    profile = self.profile(restored)
                    self.assertEqual(profile.observations[0]['points'], data['season_matchups']['weeks']['1']['rows'][0]['players_points']['1'])
                    dossier, market, api = self.render(f, restored)
                    self.assertEqual(api.status_code, 200)
                    self.assertEqual(api.json()['valuation']['canonical_production']['windows'][3]['fantasy_points'], 18)
                    self.assertIn('18.00 fantasy points per score observation', dossier.text)
                    self.assertIn('18.00 fantasy points per score observation', market.text)
                    if legacy is True:
                        self.assertIn('same retained league cache', ' '.join(profile.limitations))

    def test_binding_precedes_publication_and_runs_once_per_source_path(self):
        import services.player_evidence as evidence
        f, data = self.fixture()
        seen = []
        def capture(runtime):
            seen.append(self.profile(runtime.state['data']).observations[0]['points'])
        with patch.object(evidence, 'attach_sleeper_actuals', wraps=evidence.attach_sleeper_actuals) as attach:
            self.restore(data, publish=capture)
            self.assertEqual(attach.call_count, 1)
            self.restore(data, default=True)
            self.assertEqual(attach.call_count, 2)
            fresh = copy.deepcopy(data)
            fresh.pop('canonical_player_production')
            result = evidence.prepare_player_production(fresh, expected_league_id=fresh['league']['league_id'],
                as_of='2026-11-01T00:00:00Z', path=f.f.root/'no-global-evidence.sqlite3')
            self.assertEqual(attach.call_count, 3)
        self.assertEqual(seen, [18])
        self.assertEqual(result['sleeper_actuals']['source_generation'], data['season_matchups']['semantic_generation'])
        self.assertEqual(result['sleeper_actuals']['players']['1'][0]['points'], 18)

    def test_invalid_source_scope_calendar_or_generation_stays_unavailable(self):
        for key, value in (('league_id','foreign'),('season','2025'),('scoring_fingerprint','foreign'),
                           ('calendar_reference','foreign'),('semantic_generation',None)):
            for default in (False, True):
                with self.subTest(key=key, default=default):
                    f, data = self.fixture()
                    data['season_matchups'][key] = value
                    restored = self.restore(data, default=default)
                    profile = self.profile(restored)
                    self.assertFalse(profile.observations)
                    self.assertTrue(all(w.fantasy_points is None for w in profile.windows))
                    for response in self.render(f, restored)[:2]:
                        self.assertNotIn('18.00 fantasy points per score observation', response.text)

    def test_foreign_prepared_analysis_is_not_relabelled_or_overwritten(self):
        from services.player_evidence import bind_retained_actuals
        for key, value in (('league_id','foreign'),('season',2025),('scoring_fingerprint','foreign')):
            with self.subTest(key=key):
                _, data = self.fixture()
                data['canonical_player_production'][key] = value
                original = copy.deepcopy(data['canonical_player_production'])
                bind_retained_actuals(data, expected_league_id=data['league']['league_id'])
                self.assertEqual(data['canonical_player_production'], original)
                self.assertNotIn('sleeper_actuals', data['canonical_player_production'])

    def test_zero_negative_conflict_and_partial_periods_survive_restore_to_screen(self):
        for kind in ('zero','negative','conflict','missing_week'):
            with self.subTest(kind=kind):
                f, data = self.fixture()
                if kind in ('zero','negative'):
                    value = 0 if kind == 'zero' else -2.125
                    for week in data['season_matchups']['weeks'].values():
                        for row in week['rows']:
                            row['players_points']['1'] = value
                            row['starters_points'] = [value]
                elif kind == 'conflict':
                    data['season_matchups']['weeks']['1']['rows'][0]['starters_points'] = [999]
                else:
                    data['season_matchups']['weeks']['1'].update(availability='unavailable', rows=[], reason='SOURCE_WEEK_UNAVAILABLE')
                # Controlled source mutation has an explicit new publication ID;
                # expected scores always come from the retained rows, not scorer math.
                import hashlib
                data['season_matchups']['semantic_generation'] = hashlib.sha256(json.dumps(data['season_matchups']['weeks'],sort_keys=True).encode()).hexdigest()
                restored = self.restore(data)
                dossier, market, api = self.render(f, restored)
                actual = api.json()['valuation']['canonical_production']
                if kind in ('zero','negative'):
                    self.assertEqual(actual['observations'][0]['points'], value)
                    self.assertEqual(actual['windows'][3]['fantasy_points'], value)
                    text = '0.00' if value == 0 else '-2.13'
                    for response in (dossier, market):
                        self.assertIn(text+' fantasy points per score observation', response.text)
                elif kind == 'conflict':
                    self.assertIsNone(actual['windows'][3]['fantasy_points'])
                    self.assertEqual(actual['windows'][3]['scored_count'], 7)
                    self.assertIn('Sleeper score records disagree', dossier.text)
                else:
                    self.assertEqual(actual['windows'][3]['observation_count'], 7)
                    self.assertEqual(actual['periods']['1']['reason'], 'SOURCE_WEEK_UNAVAILABLE')

    def test_source_clocks_reference_values_and_cached_decisions_are_preserved(self):
        _, data = self.fixture()
        original = json.loads(json.dumps(data))
        restored = self.restore(data)
        actuals = restored['canonical_player_production']['sleeper_actuals']
        self.assertEqual(actuals['observed_at'], original['season_matchups']['observed_at'])
        self.assertEqual(actuals['retrieved_at'], original['season_matchups'].get('retrieved_at'))
        self.assertEqual(restored['canonical_player_production']['reference_generation'], original['canonical_player_production']['reference_generation'])
        self.assertEqual(restored['canonical_player_production']['players'], original['canonical_player_production']['players'])
        before, after = original['valuation_intelligence']['assets']['player:1'], copy.deepcopy(restored['valuation_intelligence']['assets']['player:1'])
        before.pop('canonical_production')
        after.pop('canonical_production')
        self.assertEqual(before, after)
        self.assertEqual(restored['season_matchups'], original['season_matchups'])

    def test_source_generation_change_withholds_until_explicit_rebinding(self):
        from services.player_evidence import bind_retained_actuals
        _, data = self.fixture()
        restored = self.restore(data)
        old = restored['canonical_player_production']['sleeper_actuals']['source_generation']
        restored['season_matchups']['semantic_generation'] = old+'-new'
        self.assertFalse(self.profile(restored).observations)
        bind_retained_actuals(restored, expected_league_id=restored['league']['league_id'])
        self.assertEqual(self.profile(restored).source_generation, old+'-new')

    def test_reads_do_not_rebind_or_acquire_after_publication(self):
        f, data = self.fixture()
        restored = self.restore(data)
        with patch('services.player_evidence.bind_retained_actuals', side_effect=AssertionError('no preparation on read')), \
             patch('services.sleeper.sleeper_get', side_effect=AssertionError('no provider read')):
            self.assertTrue(all(r.status_code == 200 for r in self.render(f, restored)))

    def test_real_canonical_publication_and_eviction_reopening_capture_bound_scores(self):
        import asyncio
        import dtos_app
        from src.core.history_context.store import CanonicalHistoryStore
        from src.core.valuation.universe import ValuationUniverse
        from services.trade_decision import selected_player_facts
        from types import SimpleNamespace
        f, data = self.fixture()
        path = self.write(data)
        history = CanonicalHistoryStore()
        generations = []
        projection = Mock()
        projection.snapshot.return_value = {}
        def publish(runtime):
            context = dtos_app._publish_runtime_context(runtime, projection)
            profile = context.brain.asset('player:1')['canonical_production']
            generations.append(profile['source_generation'])
            self.assertEqual(profile['observations'][0]['points'], 18)
            self.assertEqual(ValuationUniverse(runtime.state['data'], runtime.state).by_id['player:1']['canonical_production']['observations'][0]['points'], 18)
            with patch('services.player_projection_view.player_projection_views', return_value={'1':{'value':None,'availability':'unavailable'}}):
                facts = selected_player_facts(runtime.state['data'], [SimpleNamespace(kind='player',asset_id='1',label='Fixture QB',age=None,position='QB',trade_value=None,market_fact={},positional_rank=None)],
                    SimpleNamespace(snapshot=lambda:{},refresh_evidence=lambda _:{}), scoring_supported=True)
            self.assertEqual(facts['1']['production']['points_per_observation'], 18)
        with patch.object(league_preparation, 'league_cache_file', return_value=path), \
             patch.object(dtos_app, 'canonical_history_store', history), \
             patch.object(dtos_app.fois_service.repository, 'league', return_value=[]):
            for _ in range(2):
                runtime = LeagueRuntime(data['league']['league_id'])
                runtime.market_context = f.f.cache
                self.assertTrue(league_preparation.restore_cached_runtime(runtime,publish,expected_season=2026))
                self.assertTrue(all(r.status_code == 200 for r in self.render(f, runtime.state['data'])))
                asyncio.run(runtime.close())
                self.assertEqual(runtime.state['data'], {})
                self.assertIsNone(runtime.canonical_context)
        self.assertEqual(generations, [data['season_matchups']['semantic_generation']]*2)

    def test_memory_deferral_does_not_start_actual_binding(self):
        from src.platform.lifecycle import HeavyWorkDeferred
        _, data = self.fixture()
        path = self.write(data)
        with patch.object(league_preparation,'league_cache_file',return_value=path), \
             patch.object(league_preparation,'memory_snapshot',return_value={}), \
             patch('services.player_evidence.bind_retained_actuals',side_effect=AssertionError('must not bind before admission')) as binding:
            with self.assertRaises(HeavyWorkDeferred):
                league_preparation.restore_cached_runtime(LeagueRuntime(data['league']['league_id']),Mock())
            binding.assert_not_called()

    def test_isolated_leagues_and_scoring_do_not_share_restored_actuals(self):
        from tests.test_sleeper_actual_results import actual_data
        from services.player_evidence import bind_retained_actuals
        contexts = []
        for lid,value,scoring in [('100',0,{'rec':1}),('200',-2.125,{'rec':.5})]:
            data = actual_data(lid,player='1',scores=(value,),scoring=scoring)
            data['teams'] = [{'roster_id':4}]
            if lid == '200':
                data['league']['roster_positions'].append('SUPER_FLEX')
            restored = self.restore(data)
            self.assertEqual(self.profile(restored).observations[0]['points'], value)
            contexts.append(restored)
        with self.assertRaises(ValueError):
            bind_retained_actuals(contexts[0],expected_league_id='200')
        self.assertEqual(self.profile(contexts[1]).observations[0]['points'], -2.125)
        self.assertNotEqual(contexts[0]['canonical_player_production']['generation'],contexts[1]['canonical_player_production']['generation'])
