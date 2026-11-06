"""Existing factual timeline integration; retained replay plus disposable variants."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.accounts import create_accounts_router
from routes.navigation import create_navigation_router
from routes.history import create_history_router
from routes.historical_assets import create_historical_assets_router
from routes.transactions import create_transactions_router
from src.core.accounts import AccountStore, AccountService
from src.platform.account_context import AccountContextMiddleware, current_account
from tests import test_historical_tracker_phase2 as source
from tests import test_current_season_franchise_history as current

ROOT, PICK, LATER = source.ROOT, source.PICK, '1414718106177122304'


class FollowThroughFixture:
    """Real routers, account/session authorization and existing prepared evidence."""
    def __init__(self, case):
        import dtos_app
        self.source = source.TrackerPhase2Tests()
        self.source.setUp()
        case.addCleanup(self.source.tearDown)
        self.data = self.source.fixture.data
        facts = deepcopy(self.source.fixture.sources[0])
        # Pagination-only disposable waivers; never represented as live events.
        facts['transactions']['5'].extend(dict(transaction_id=str(1800000000000000000+i),
            type='waiver', status='complete', created=1792000000000+i,
            roster_ids=[4], adds={str(99000+i):4}, drops={}, draft_picks=[])
            for i in range(26))
        self.source.publish(facts)
        self.facts = facts
        self.accounts = AccountStore(Path(self.source.fixture.temp.name)/'accounts.sqlite3')
        self.service = AccountService(self.accounts)
        self.sessions = {}
        for account, leagues in (('account-a', (source.DAY, source.ARK)), ('account-b', (source.ARK,))):
            self.accounts.create_account(account, account, account, 'fixture-hash', [])
            self.accounts.link_sleeper(account, sleeper_user_id=account, username=account, display_name=account)
            for league in leagues:
                self.accounts.upsert_membership(account, self.data[league]['league'], account,
                    4 if league == source.DAY else 1, 'Fixture franchise', 'active')
            self.accounts.activate(account, leagues[0])
            self.sessions[account] = self.service.new_session(account)[0]
        case.enterContext(patch.object(dtos_app, 'account_store', self.accounts))
        case.enterContext(patch('services.sleeper.sleeper_get', side_effect=AssertionError('No provider acquisition on history render')))
        case.enterContext(patch('src.core.fois.service.FOISService._generate_sync', side_effect=AssertionError('No FOIS generation')))
        def league():
            return str(current_account().membership.league_id)
        def data():
            return self.data[league()]
        common = dict(league_id=source.DAY, league_resolver=league, page=dtos_app.page, require_data=data)
        app = FastAPI()
        app.include_router(create_navigation_router())
        app.include_router(create_history_router(**common))
        app.include_router(create_historical_assets_router(**common))
        app.include_router(create_transactions_router(ensure_fresh=AsyncMock(),
            refresh_transactions=AsyncMock(), require_data=data, state={}, page=dtos_app.page))
        app.include_router(create_accounts_router(service=self.service, runtime_manager=SimpleNamespace(get=AsyncMock())))
        app.add_middleware(AccountContextMiddleware, service=self.service, required=True)
        self.client = TestClient(app, raise_server_exceptions=False)
        case.addCleanup(self.client.close)
        self.client.cookies.set('dtos_session', self.sessions['account-a'])
        self.static = TestClient(dtos_app.app)
        case.addCleanup(self.static.close)
        self.before = deepcopy(self.data)

    def graph(self, league=source.DAY):
        from src.core.historical_memory.graph import HistoricalAssetGraph
        return HistoricalAssetGraph(self.source.fixture.store, league, self.data[league], self.source.fixture.memory)


class HistoryFollowThroughTests(unittest.TestCase):
    def setUp(self):
        self.f = FollowThroughFixture(self)

    def test_franchise_original_pick_conversion_player_and_later_package_reuse_canonical_evidence(self):
        history = self.f.client.get('/history/team/'+source.DAY+':franchise:4?events_page=2')
        self.assertEqual(history.status_code, 200)
        self.assertIn('href="/trades/history/'+ROOT+'"', history.text)
        original = self.f.client.get('/api/trades/history/'+ROOT).json()
        timeline = original['timeline']
        branch = next(b for b in timeline['branches'] if b['asset_id']==PICK)
        self.assertGreater(len(timeline['branches']), 2)
        self.assertEqual(branch['converted_asset']['player_id'], 'DTOS-P-13346')
        self.assertTrue(any(e['source_record_id']==LATER for e in branch['events']))
        self.assertTrue(any('Package relationship only' in (e.get('package_note') or '') for e in branch['events']))
        self.assertNotIn('descendant_value', timeline)
        pick = self.f.client.get('/api/picks/'+PICK).json()
        self.assertEqual((pick['season'], pick['round'], pick['original_franchise_id']), ('2026', '2', source.DAY+':franchise:7'))
        for path in ['/picks/'+PICK, '/players/13346', '/history/player/13346', '/trades/history/'+LATER]:
            response = self.f.client.get(path+'?from_trade='+ROOT)
            self.assertEqual(response.status_code, 200, (path, response.text[:300]))
            self.assertIn('href="/trades/history/'+ROOT+'"', response.text)
            self.assertIn('Back to original trade timeline', response.text)
        player = self.f.client.get('/players/13346?from_trade='+ROOT).text
        self.assertIn('Current values are never backdated', player)
        self.assertIn('uninterrupted ownership', player)
        self.assertEqual(self.f.data, self.f.before)

    def test_real_sessions_selected_leagues_and_foreign_origins_remain_isolated(self):
        first = self.f.client.get('/api/account/navigation-context').json()['scope']
        foreign = 'TRADE-'+source.ARK+'-'+ROOT
        page = self.f.client.get('/picks/'+PICK+'?from_trade='+foreign)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('Back to original trade timeline', page.text)
        self.f.client.cookies.set('dtos_session', self.f.sessions['account-b'])
        second = self.f.client.get('/api/account/navigation-context').json()['scope']
        self.assertNotEqual(first, second)
        self.assertEqual(self.f.client.get('/history/team/'+source.DAY+':franchise:4').status_code, 404)
        self.assertEqual(self.f.client.get('/trades/history/'+ROOT).status_code, 404)
        self.assertEqual(self.f.client.get('/history/team/'+source.ARK+':franchise:1').status_code, 200)
        # Real membership switch, confined to this disposable account.
        self.f.accounts.activate('account-a', source.ARK)
        self.f.client.cookies.set('dtos_session', self.f.sessions['account-a'])
        self.assertNotEqual(first, self.f.client.get('/api/account/navigation-context').json()['scope'])
        self.assertEqual(self.f.client.get('/trades/history/'+ROOT).status_code, 404)
        self.assertEqual(self.f.data, self.f.before)

    def test_missing_chronology_preserves_original_exchange_but_withholds_continuation(self):
        facts = deepcopy(self.f.facts)
        row = next(r for r in facts['transactions']['1'] if r['transaction_id']==ROOT)
        row['created'], row['status_updated'] = None, None
        self.f.source.publish(facts)
        response = self.f.client.get('/trades/history/'+ROOT)
        self.assertEqual(response.status_code, 200)
        result = self.f.client.get('/api/trades/history/'+ROOT).json()['timeline']
        self.assertTrue(result['branches'])
        self.assertTrue(all(not b['events'] for b in result['branches']))
        self.assertIn('Missing event clocks', response.text)
        self.assertIn('No later event admitted', response.text)
        self.assertIn('not proof of no movement', response.text)
        self.assertIn('NOT REVALIDATED', response.text)

    def test_pending_and_rejected_records_never_open_as_completed_trade_movements(self):
        facts = deepcopy(self.f.facts)
        original = next(r for r in facts['transactions']['1'] if r['transaction_id']==ROOT)
        for status in ['pending', 'failed']:
            facts['transactions']['5'].append({**deepcopy(original), 'transaction_id':'170000000000000000'+('3' if status=='pending' else '4'), 'status':status})
        self.f.source.publish(facts)
        for status in ['pending', 'failed']:
            identity='170000000000000000'+('3' if status=='pending' else '4')
            self.assertEqual(self.f.client.get('/api/trades/history/'+identity).json()['status'],status)
            self.assertEqual(self.f.client.get('/trades/history/'+identity).status_code, 404)
        page = self.f.client.get('/history/team/'+source.DAY+':franchise:4').text
        self.assertIn('no asset movement is inferred', page)
        self.assertNotIn('href="/trades/history/1700000000000000003',page)
        self.assertNotIn('href="/trades/history/1700000000000000004',page)


class CurrentHistoryFollowThroughTests(unittest.IsolatedAsyncioTestCase):
    setUp = current.CurrentSeasonRuntimeHistoryTests.setUp

    def prepare(self):
        from src.core.intelligence_memory.store import IntelligenceCheckpointStore
        self.enterContext(patch('src.core.intelligence_memory.intelligence_checkpoint_store', IntelligenceCheckpointStore(self.folder/'memory.sqlite3')))
        self.enterContext(patch('routes.historical_assets.historical_store',self.store))
        self.client.app.include_router(create_historical_assets_router(league_id=self.runtime.league_id,
            require_data=lambda:self.runtime.state['data'], page=lambda title, body: self.app_module.HTMLResponse(body)))
        self.data['league']['season'] = '2026'
        self.data['season'] = '2026'
        self.data['players'] = {'101': {'full_name':'Fixture Receiver', 'position':'WR'}}
        self.data['normalized_players'] = {'101': {'name':'Fixture Receiver', 'position':'WR'}}
        self.data['season_transactions']['2'] = [dict(transaction_id='1700000000000000001', type='trade',
            status='complete', created=1772330838497, roster_ids=[1,2], adds={'101':1}, drops={'101':2},
            draft_picks=[dict(season='2027',round=1,roster_id=2,previous_owner_id=2,owner_id=1)])]
        self.data['season_transactions']['3'] = [dict(transaction_id='1700000000000000002', type='trade',
            status='complete', created=1773000000000, roster_ids=[1,2], adds={'101':2}, drops={'101':1},draft_picks=[])]

    def check_journey(self):
        page=self.client.get('/history/team/'+self.runtime.league_id+':franchise:1')
        self.assertEqual(page.status_code,200)
        self.assertIn('8 of 19 supported source weeks retrieved',page.text)
        self.assertIn('href="/trades/history/1700000000000000001"',page.text)
        trade=self.client.get('/trades/history/1700000000000000001')
        self.assertEqual(trade.status_code,200)
        self.assertIn('/trades/history/1700000000000000002?from_trade=1700000000000000001',trade.text)
        self.assertIn('2027 Round 1',trade.text)
        self.assertIn('NOT REVALIDATED',trade.text)
        later=self.client.get('/trades/history/1700000000000000002?from_trade=1700000000000000001')
        self.assertEqual(later.status_code,200)
        self.assertIn('href="/trades/history/1700000000000000001"',later.text)
        self.sync.assert_not_called()

    async def test_current_fresh_owned_publication_preserves_followthrough(self):
        self.prepare()
        self.runtime.apply_data(self.data)
        self.app_module._publish_runtime_context(self.runtime,self.projection)
        self.check_journey()
        await self.runtime.close()
        self.assertNotIn(self.runtime.league_id,self.store._current)

    async def test_current_cache_restore_and_eviction_reopening_preserve_followthrough(self):
        from src.core.league_runtime import LeagueRuntime
        self.prepare()
        await current.CurrentSeasonRuntimeHistoryTests.restore(self)
        self.check_journey()
        await self.runtime.close()
        self.assertNotIn(self.runtime.league_id,self.store._current)
        self.runtime=LeagueRuntime(self.data['league']['league_id'])
        await current.CurrentSeasonRuntimeHistoryTests.restore(self)
        self.check_journey()
        await self.runtime.close()
