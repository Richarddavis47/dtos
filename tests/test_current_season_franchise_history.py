"""Actual cached runtime publication through canonical, rendered history.

Source-compatible disposable leagues; no live owner data or source requests.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from routes.history import create_history_router
from services import league_preparation
from src.core.history_context import store as history_module
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.league_runtime import LeagueRuntime, LeagueRuntimeManager
from tests.test_league_runtime import league_data


def publication(league='2100000000000000001', season=2032, week=8):
    data = league_data(league)
    data['league'].update(season=str(season), status='in_season', settings={'leg': week})
    data.update(week=week, normalized_players={}, players={}, traded_picks=[],
                season_transactions={str(w): [] for w in range(1, week+1)}, transactions=[])
    data['teams'] = [dict(roster_id=i, owner_id=f'owner-{league}-{i}',
                          team_name=f'Franchise {i}', players=[]) for i in (1, 2)]
    data['season_transactions']['2'] = [dict(transaction_id='observed-trade',
        type='trade', status='complete', roster_ids=[1, 2], adds={'player-one': 1},
        drops={'player-one': 2}, draft_picks=[])]
    return data


class CurrentSeasonRuntimeHistoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import dtos_app
        self.app_module = dtos_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = CanonicalHistoryStore()
        self.cache = SleeperSeasonCache(self.folder/'seasons')
        self.enterContext(patch.object(history_module, 'sleeper_season_cache', self.cache))
        self.enterContext(patch.object(dtos_app, 'canonical_history_store', self.store))
        self.enterContext(patch('services.history.historical_store', self.store))
        self.enterContext(patch('src.core.historical_memory.read_model.historical_read_model_cache', HistoricalReadModelCache()))
        self.enterContext(patch('services.league_maintenance.ensure_periodic_refresh'))
        self.sync = self.enterContext(patch.object(dtos_app, 'sync_sleeper_league', side_effect=AssertionError('No source refresh on restore')))
        self.projection = Mock()
        self.projection.snapshot.return_value = None
        self.projection.begin_external_refresh.return_value = False
        self.enterContext(patch.object(dtos_app, 'ProjectionService', return_value=self.projection))
        self.enterContext(patch.object(dtos_app, 'AssetMarketCache', return_value=Mock()))
        self.data = publication()
        self.runtime = LeagueRuntime(self.data['league']['league_id'])
        self.path = self.folder/'cache.json'
        self.enterContext(patch.object(league_preparation, 'league_cache_file', return_value=self.path))
        app = FastAPI()
        def render(title,body):
            renderer = getattr(self,'renderer',None)
            return renderer(title,body) if renderer else HTMLResponse(body)
        app.include_router(create_history_router(league_id=self.runtime.league_id,
            league_resolver=lambda:self.runtime.league_id,
            require_data=lambda:self.runtime.state['data'],
            page=render))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    async def restore(self):
        self.path.write_text(json.dumps(dict(data=self.data,last_sync=datetime.now(timezone.utc).isoformat())))
        await self.app_module._hydrate_league_runtime(self.runtime)

    def page(self):
        response = self.client.get('/history/team/'+self.runtime.league_id+':franchise:1')
        self.assertEqual(response.status_code,200,response.text[:300])
        return response.text

    async def test_restored_weekly_buckets_are_registered_and_rendered(self):
        await self.restore()
        self.sync.assert_not_called()
        html = self.page()
        self.assertIn('2032 · Partial transaction coverage',html)
        self.assertIn('8 of 19 supported source weeks retrieved',html)
        self.assertIn('observed-trade',html)
        self.assertIs(self.store._current[self.runtime.league_id],self.runtime.state['data'])
        self.assertEqual(self.runtime.canonical_context.history_state,'partial')

    async def test_eviction_releases_history_reference_and_reopening_registers_again(self):
        await self.restore()
        first = self.runtime.state['data']
        self.assertIs(self.store._current.get(self.runtime.league_id),first)
        await self.runtime.close()
        self.assertNotIn(self.runtime.league_id,self.store._current)
        self.runtime = LeagueRuntime(self.data['league']['league_id'])
        await self.restore()
        self.assertIn('observed-trade',self.page())
        self.assertIsNot(self.runtime.state['data'],first)

    async def test_manager_admission_eviction_and_reopening_recover_current_history(self):
        self.path.write_text(json.dumps(dict(data=self.data,last_sync=datetime.now(timezone.utc).isoformat())))
        manager=LeagueRuntimeManager(max_warm=1,hydrator=self.app_module._hydrate_league_runtime)
        try:
            self.runtime=await manager.get(self.data['league']['league_id'])
            first=self.runtime
            self.assertIn('observed-trade',self.page())
            self.assertTrue(await manager.evict(self.runtime.league_id))
            self.assertNotIn(self.runtime.league_id,self.store._current)
            self.runtime=await manager.get(self.data['league']['league_id'])
            self.assertIsNot(self.runtime,first)
            self.assertIn('observed-trade',self.page())
            self.sync.assert_not_called()
        finally:
            await manager.shutdown()
        self.assertNotIn(self.runtime.league_id,self.store._current)

    async def test_configured_cached_startup_publication_registers_current_history(self):
        from services import sleeper
        self.path.write_text(json.dumps(dict(data=self.data,last_sync=datetime.now(timezone.utc).isoformat())))
        self.runtime.owns_state = False
        with patch.object(sleeper,'league_cache_file',return_value=self.path):
            sleeper.load_cache(state=self.runtime.state,league_id=self.runtime.league_id)
        self.runtime.apply_data(self.runtime.state['data'])
        self.app_module._publish_runtime_context(self.runtime,self.projection)
        self.assertIs(self.store._current[self.runtime.league_id],self.runtime.state['data'])
        self.assertIn('observed-trade',self.page())

    async def test_old_flat_activity_is_retained_without_inventing_acquired_weeks(self):
        self.data['transactions'] = self.data.pop('season_transactions')['2']
        await self.restore()
        html = self.page()
        self.assertIn('observed-trade',html)
        self.assertIn('0 of 19 supported source weeks retrieved',html)
        self.assertNotIn('No completed transaction activity in the fully acquired',html)

    async def test_ongoing_season_without_acquired_history_stays_unknown(self):
        self.data.pop('season_transactions')
        self.data['transactions']=[]
        await self.restore()
        html=self.page()
        self.assertIn('2032 · Unknown transaction coverage',html)
        self.assertNotIn('2032 · Partial transaction coverage',html)
        self.assertIn('0 of 19 supported source weeks retrieved',html)
        self.assertNotIn('No completed transaction activity in the fully acquired',html)

    async def test_explicit_empty_retrieved_weeks_do_not_establish_empty_missing_weeks(self):
        self.data['season_transactions']={str(w):[] for w in range(1,9)}
        await self.restore()
        html=self.page()
        self.assertIn('2032 · Partial transaction coverage',html)
        self.assertIn('Observed-empty retrieved weeks: 1, 2, 3, 4, 5, 6, 7, 8',html)
        self.assertIn('Not retrieved: weeks 0',html)
        self.assertNotIn('No completed transaction activity in the fully acquired',html)

    async def test_stale_context_close_cannot_release_newer_publication(self):
        await self.restore()
        first = self.runtime
        self.runtime = LeagueRuntime(self.data['league']['league_id'])
        self.data['week'] = 9
        await self.restore()
        await first.close()
        self.assertIs(self.store._current[self.runtime.league_id],self.runtime.state['data'])
        self.assertIn('observed-trade',self.page())

    async def test_foreign_league_or_season_cache_is_rejected_before_registration(self):
        for mutate in (lambda d:d['league'].update(league_id='2100000000000000002'),
                       lambda d:d.update(season=2031)):
            original = deepcopy(self.data)
            mutate(self.data)
            self.path.write_text(json.dumps(dict(data=self.data,last_sync=datetime.now(timezone.utc).isoformat())))
            published = Mock()
            self.assertFalse(league_preparation.restore_cached_runtime(self.runtime,published,expected_season=2032))
            published.assert_not_called()
            self.assertNotIn(self.runtime.league_id,self.store._current)
            self.data = original

    async def test_two_owned_leagues_keep_season_periods_and_pages_isolated(self):
        await self.restore()
        first = self.runtime
        self.data = publication('2100000000000000002',2031,5)
        self.data['season_transactions']['2'][0]['transaction_id'] = 'second-league-trade'
        self.runtime = LeagueRuntime(self.data['league']['league_id'])
        await self.restore()
        self.assertIn('second-league-trade',self.page())
        foreign = self.client.get('/history/team/'+first.league_id+':franchise:1')
        self.assertEqual(foreign.status_code,404)
        self.runtime = first
        html = self.page()
        self.assertIn('observed-trade',html)
        self.assertNotIn('second-league-trade',html)


class CurrentSeasonAcquisitionTests(unittest.IsolatedAsyncioTestCase):
    """Network responses only are controlled; acquisition and rendering are real."""
    setUp = CurrentSeasonRuntimeHistoryTests.setUp
    restore = CurrentSeasonRuntimeHistoryTests.restore
    page = CurrentSeasonRuntimeHistoryTests.page

    async def prepare(self, outcomes, previous=None):
        from src.core.history_context.transaction_periods import acquire_previous_periods
        calls = []
        async def fetch(path):
            calls.append(path)
            value = outcomes.get(int(path.rsplit('/',1)[-1]),[])
            if isinstance(value,Exception):
                raise value
            return value
        buckets,meta = await acquire_previous_periods(self.data['league'],self.data['week'],[],
            previous or {},fetch,observed_at='2032-10-20T12:00:00+00:00')
        self.data.update(season_transactions=buckets,transactions=[],transaction_acquisition=meta)
        if self.runtime.state.get('data'):
            await self.runtime.close()
            self.runtime = LeagueRuntime(self.data['league']['league_id'])
        await self.restore()
        return calls

    async def test_empty_failed_unavailable_and_unacquired_are_distinct(self):
        trade = self.data['season_transactions']['2']
        calls = await self.prepare({0:RuntimeError('private provider text'),2:trade,4:None,5:RuntimeError('private failure')})
        html = self.page()
        self.assertEqual(len(calls),8)
        self.assertEqual(len(set(calls)),8)
        self.assertIn('Refresh failed: weeks 0, 5',html)
        self.assertIn('Source unavailable: weeks 0, 4, 5',html)
        self.assertIn('Observed-empty retrieved weeks: 1, 3, 6, 7, 8',html)
        self.assertIn('2032-10-20T12:00:00Z',html)
        self.assertNotIn('private provider text',html)
        self.assertIn('observed-trade',html)
        self.assertNotIn('Complete transaction coverage',html)

    async def test_failed_refresh_retains_exact_prior_period_and_retrieval_time(self):
        from src.core.history_context.transaction_periods import current_period_metadata
        previous = deepcopy(self.data)
        previous['transaction_acquisition'] = current_period_metadata(previous,2,previous['season_transactions']['2'],'2032-10-15T09:00:00+00:00')
        await self.prepare({2:RuntimeError('failed refresh')},previous)
        html = self.page()
        self.assertIn('observed-trade',html)
        self.assertIn('2032-10-15T09:00:00Z',html)
        self.assertIn('Refresh failed: weeks 2',html)
        self.assertIn('showing last-valid evidence',html)
        self.assertIn('unsuccessful refresh: 2',html)
        self.assertEqual(self.runtime.state['data']['season_transactions']['2'],previous['season_transactions']['2'])

    async def test_prior_bucket_cannot_cross_league_or_season(self):
        original = deepcopy(self.data)
        for key,value in [('league_id','other-league'),('season','2031')]:
            self.data = deepcopy(original)
            previous = deepcopy(self.data)
            previous['league'][key]=value
            await self.prepare({2:RuntimeError('failed')},previous)
            self.assertNotIn('observed-trade',self.page())
            self.assertIsNone(self.runtime.state['data']['season_transactions']['2'])

    async def test_legacy_retained_bucket_does_not_receive_a_guessed_retrieval_time(self):
        previous = deepcopy(self.data)
        await self.prepare({2:RuntimeError('failed')},previous)
        html = self.page()
        self.assertIn('Week 2: retrieved at an unrecorded time; showing last-valid evidence',html)
        self.assertIsNone(self.runtime.state['data']['transaction_acquisition']['periods']['2']['retrieved_at'])

    async def test_foreign_acquisition_metadata_cannot_supply_dates_or_failures(self):
        from src.core.history_context.transaction_periods import current_period_metadata
        self.data['transaction_acquisition'] = current_period_metadata(self.data,2,[], '2032-10-15T09:00:00+00:00')
        self.data['transaction_acquisition']['league_id'] = 'foreign'
        await self.restore()
        html=self.page()
        self.assertNotIn('2032-10-15T09:00:00Z',html)
        self.assertIn('retrieved at an unrecorded time',html)
        self.assertIn('observed-trade',html)

    async def test_unsupported_week_is_rejected_before_fetch(self):
        from src.core.history_context.transaction_periods import acquire_previous_periods
        fetch = Mock()
        for week in (-1,19,100000,True):
            with self.assertRaises(ValueError):
                await acquire_previous_periods(self.data['league'],week,[],{},fetch,observed_at='unrecorded')
        fetch.assert_not_called()

    async def test_acquisition_metadata_is_bounded_and_unknown_dates_stay_unknown(self):
        from src.core.history_context.transaction_periods import SCHEMA, admitted_metadata
        self.data['transaction_acquisition'] = dict(schema=SCHEMA,league_id=self.runtime.league_id,season=2032,
            through_week=8,periods={str(w):dict(state='observed',retrieved_at='not a timestamp',
                last_attempt_at='unrecorded') for w in range(1000)})
        original = deepcopy(self.data)
        meta = admitted_metadata(self.data,self.runtime.league_id,2032)
        self.assertEqual(len(meta['periods']),19)
        self.assertTrue(all(r['retrieved_at'] is None for r in meta['periods'].values()))
        self.assertEqual(self.data,original)


class CurrentSeasonFreshSyncTests(unittest.IsolatedAsyncioTestCase):
    setUp = CurrentSeasonRuntimeHistoryTests.setUp
    page = CurrentSeasonRuntimeHistoryTests.page

    async def test_actual_sync_save_evict_restore_and_render_keep_current_periods(self):
        from services import sleeper
        from contextlib import ExitStack
        league = deepcopy(self.data['league'])
        league.update(total_rosters=2,settings={'leg':8,'draft_rounds':3})
        trade = self.data['season_transactions']['2']
        calls = []
        async def get(_client,path):
            calls.append(path)
            if path == '/league/'+self.runtime.league_id:
                return league
            if path.endswith('/users'):
                return [dict(user_id=f'owner-{i}',display_name=f'Owner {i}') for i in (1,2)]
            if path.endswith('/rosters'):
                return [dict(roster_id=i,owner_id=f'owner-{i}',players=[],starters=[],settings={}) for i in (1,2)]
            if path == '/state/nfl':
                return dict(season='2032',week=8,season_type='regular')
            if '/transactions/' in path:
                week=int(path.rsplit('/',1)[-1])
                if week==4:
                    raise RuntimeError('disposable source failure')
                return trade if week==2 else []
            return {} if path=='/players/nfl' else []
        self.runtime.state['data'] = {}
        with ExitStack() as stack:
            stack.enter_context(patch.object(sleeper,'sleeper_get',side_effect=get))
            stack.enter_context(patch.object(sleeper,'league_cache_file',return_value=self.path))
            stack.enter_context(patch('src.core.history_context.canonical_history_store',self.store))
            stack.enter_context(patch.object(sleeper,'refresh_public_market',return_value={'provider_status':{}}))
            stack.enter_context(patch.object(sleeper,'player_history_evidence_batch',return_value={}))
            for name in ('src.core.valuation.normalization.prepare_market_normalization',
                         'src.core.intelligence.pick_context.prepare_pick_context',
                         'src.core.relevant_players.apply_relevant_player_filter',
                         'src.core.intelligence.team_strength.prepare_for_data',
                         'src.core.intelligence.strength_history.record_strength_history',
                         'services.player_evidence.prepare_player_production',
                         'src.core.intelligence_memory.checkpoint_pipeline.ingest_runtime'):
                stack.enter_context(patch(name,return_value={}))
            stack.enter_context(patch('src.core.valuation.ranking.prepare_global_player_ranks',return_value={'players':{}}))
            stack.enter_context(patch('src.core.relevant_players.build_relevant_player_universe',return_value={'member_ids':[]}))
            for name in ('build_provider_network','build_valuation_intelligence','audit_market_calibration'):
                stack.enter_context(patch.object(sleeper,name))
            await sleeper.sync_sleeper_league(self.runtime.league_id,self.runtime.state,
                projections=self.projection,publish_data=self.runtime.publish_source)
        self.assertIsNone(self.runtime.state['last_error'])
        self.assertEqual(self.runtime.state['preparation_state'],'ready')
        self.app_module._publish_runtime_context(self.runtime,self.projection)
        before = self.page()
        self.assertIn('observed-trade',before)
        self.assertIn('Refresh failed: weeks 4',before)
        self.assertEqual(sorted(int(p.rsplit('/',1)[-1]) for p in calls if '/transactions/' in p),list(range(9)))
        metadata = deepcopy(self.runtime.state['data']['transaction_acquisition'])
        await self.runtime.close()
        self.runtime = LeagueRuntime(league['league_id'])
        await self.app_module._hydrate_league_runtime(self.runtime)
        self.assertEqual(self.runtime.state['data']['transaction_acquisition'],metadata)
        self.assertIn('observed-trade',self.page())
        self.assertIn('Refresh failed: weeks 4',self.page())
        self.sync.assert_not_called()

    async def test_transaction_only_refresh_updates_metadata_under_existing_publication_lock(self):
        from services import sleeper
        await CurrentSeasonRuntimeHistoryTests.restore(self)
        data = self.runtime.state['data']
        state = self.runtime.state
        with patch.object(sleeper,'sleeper_get',return_value=[]), \
                patch('src.core.history_context.canonical_history_store',self.store), \
                patch.object(sleeper,'league_cache_file',return_value=self.path), \
                patch('src.core.intelligence_memory.checkpoint_pipeline.ingest_transactions'):
            result=await sleeper.sync_transactions(state=state,league_id=self.runtime.league_id,
                publish_data=self.runtime.publish_transactions)
        self.assertTrue(result)
        self.assertIs(state['data'],data)
        self.assertEqual(data['transaction_acquisition']['periods']['8']['state'],'observed_empty')
        self.assertEqual(data['season_transactions']['2'][0]['transaction_id'],'observed-trade')
        self.assertIn('observed-trade',self.page())
        self.assertEqual(self.store.transaction_coverage(self.runtime.league_id)['seasons'][0]['transaction_acquisition']['periods']['8']['state'],'observed_empty')

    async def test_failed_transaction_only_refresh_preserves_source_and_safe_warning(self):
        from services import sleeper
        await CurrentSeasonRuntimeHistoryTests.restore(self)
        before=deepcopy(self.runtime.state['data'])
        with patch.object(sleeper,'sleeper_get',side_effect=RuntimeError('private exception')):
            result=await sleeper.sync_transactions(state=self.runtime.state,league_id=self.runtime.league_id,
                publish_data=self.runtime.publish_transactions)
        self.assertFalse(result)
        self.assertEqual(self.runtime.state['data'],before)
        self.assertIn('could not be refreshed',self.runtime.state['transactions_last_error'])
        self.assertNotIn('private exception',self.runtime.state['transactions_last_error'])
        self.assertIn('observed-trade',self.page())

    async def test_granite_day_and_arkham_shapes_retain_independent_source_rules(self):
        configurations=[('Granite-shaped',['QB','RB','RB','WR','WR','TE','FLEX','FLEX','K','DEF'],{'rec':1}),
            ('Day-shaped',['QB','RB','WR','TE','FLEX','SUPER_FLEX'],{'rec':0.5}),
            ('Arkham-shaped',['QB','RB','WR','FLEX','SUPER_FLEX'],{'rec':1,'pass_td':6})]
        for index,(name,slots,scoring) in enumerate(configurations,1):
            self.data=publication('220000000000000000'+str(index),2030+index,8)
            self.data['league'].update(name=name,roster_positions=slots,scoring_settings=scoring)
            self.data.update(roster_positions=slots,scoring_settings=scoring)
            self.runtime=LeagueRuntime(self.data['league']['league_id'])
            await CurrentSeasonRuntimeHistoryTests.restore(self)
            html=self.page()
            self.assertIn('Retrieved weeks: 1, 2, 3, 4, 5, 6, 7, 8',html)
            self.assertIn('observed-trade',html)
            self.assertEqual(self.runtime.state['data']['roster_positions'],slots)
            self.assertEqual(self.runtime.state['data']['scoring_settings'],scoring)
            await self.runtime.close()
