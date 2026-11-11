"""Real prepared producer -> bounded offer cache -> authenticated HTTP."""
from contextlib import ExitStack
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from tests import test_roster_diagnostic_http as fixtures


class FrontOfficeBriefHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DiagnosticHTTPTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.publish(datetime.now(timezone.utc).isoformat())
        self.client = self.f.f.f.client
        self.data = self.f.f.f.data

    def read(self):
        r = self.client.get('/api/trades/home-opportunities?front_office=1')
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_real_eligible_proposal_exact_token_and_prepared_hq_capital(self):
        self.f.f.seed()
        self.assertEqual(self.client.get('/teams/1').status_code, 200)
        meta = self.read()
        self.assertIn('owned future first-round', meta['brief_html'])
        self.assertIn('2028', meta['brief_html'])
        self.assertIn('Explore / Edit', meta['brief_html'])
        self.assertIn(self.f.f.token, meta['brief_html'])
        original = self.client.get('/api/trades/home-opportunities', params={'front_office':1,'offer':self.f.f.token}).json()
        self.assertEqual(original['proposal']['assets_received'], ['2028-R1-4'])
        self.assertEqual(original['evaluation']['recommendation'], 'WORTH PURSUING')
        self.assertTrue(original['evaluation']['generated_trade_eligible'])

    def test_navigation_zero_added_expensive_calls_and_unchanged_durable_records(self):
        self.client.get('/teams/1')
        self.read()
        root = Path(self.f.f.f.folder.name)
        def hashes():
            return {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        before = hashes()
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(target, side_effect=AssertionError(target))) for target in (
                'services.sleeper.sleeper_get', 'routes.trades.generate_trade_workflow',
                'services.team_headquarters.build_team_headquarters',
                'src.core.intelligence.orchestrator.IntelligenceOrchestrator.analyze',
                'src.core.intelligence.roster_diagnostics._compute',
                'src.core.trade_intelligence.lineup.optimal_legal_lineup',
                'src.core.intelligence.team_strength.prepare_for_data',
                'src.core.fois.service.FOISService._generate_sync',
                'src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct',
                'src.core.market_trends.service.MarketTrendService.trend_for_asset')]
            for _ in range(10):
                response = self.client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertLess(response.text.index('Front Office Brief'), response.text.index('League Trade News'))
                self.read()
            for spy in spies:
                spy.assert_not_called()
        self.assertEqual(hashes(), before)

    def test_missing_market_does_not_hide_prepared_capital_or_allow_find_promotion(self):
        self.client.get('/teams/1')
        with patch('services.home_trade_opportunities.source_identity', return_value=None):
            meta = self.read()
        self.assertIsNone(meta['source_identity'])
        self.assertIn('owned future first-round', meta['brief_html'])
        self.assertIn('Current pick pricing is unconfirmed', meta['brief_html'])
        self.assertNotIn('RECOMMENDED TRADE', meta['brief_html'])

    def test_source_changes_during_prepared_read_returns_retryable_response(self):
        from services.front_office_brief import select_insights
        def change(*args):
            result = select_insights(*args)
            self.data['week'] = 3
            return result
        with patch('services.front_office_brief.select_insights', side_effect=change):
            response = self.client.get('/api/trades/home-opportunities?front_office=1')
        self.assertEqual(response.status_code, 409)
        self.assertIn('draft is unchanged', response.text)

    def test_source_transition_after_final_fingerprint_cannot_relabel_old_facts(self):
        from services import home_trade_opportunities
        original = home_trade_opportunities.cache_key
        calls = []
        def transition(*args, **kwargs):
            key = original(*args, **kwargs)
            calls.append(key)
            if len(calls) == 2:
                self.data['week'] = 3
            return key
        with patch('services.home_trade_opportunities.cache_key', side_effect=transition):
            response = self.client.get('/api/trades/home-opportunities?front_office=1')
        self.assertEqual(len(calls), 2)
        self.assertEqual(response.status_code, 409)

    def test_account_and_franchise_scope_stays_with_authenticated_owner(self):
        response = self.client.get('/api/trades/home-opportunities?front_office=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['workspace_context']['roster_id'], 1)
        self.assertNotIn('/teams/2', response.json()['brief_html'])

    def test_home_reuses_current_my_team_need_and_destination_requalifies_it(self):
        for team in self.data['teams']:
            for player in team['players']:
                player['status'] = 'Active'
                self.data['players'][player['id']]['status'] = 'Active'
        self.f.f.source.points = {key: 40 - value for key, value in self.f.f.source.points.items()}
        self.f.publish(datetime.now(timezone.utc).isoformat())
        context = self.client.get('/api/trades/workspace?front_office=1').json()['workspace_context']
        saved = self.client.post('/account/franchise-goal', data={
            'strategy': 'WIN NOW', 'expected_revision': '0', 'league_id': context['league_id'],
            'roster_id': '1', 'csrf_token': self.f.f.f.csrf, 'strategy_scope': context['strategy_scope'],
        }, follow_redirects=False)
        self.assertEqual(saved.status_code, 303, saved.text)
        team = self.client.get('/teams/1')
        match = re.search(r'id="my-team-trade-need"[^>]*href="([^"]+)"', team.text)
        self.assertIsNotNone(match)
        href = unescape(match[1])
        from services.front_office_brief import prepared_need
        with patch('services.front_office_brief.prepared_need', wraps=prepared_need) as admission:
            meta = self.read()
        admission.assert_called_once()
        self.assertEqual(meta['strategy'], 'WIN NOW')
        self.assertIn('Explore QB trades', meta['brief_html'])
        self.assertIn(match[1], meta['brief_html'])
        self.assertIn('Cost and uncertainty', meta['brief_html'])
        destination = self.client.get(href)
        self.assertEqual(destination.status_code, 200)
        self.assertIn('&quot;kind&quot;: &quot;starter&quot;', destination.text)
        self.assertIn('Incoming player position', destination.text)
        # Source degradation invalidates the hint; the underlying Depth remains readable.
        self.f.publish('2020-01-01T00:00:00+00:00')
        expired = self.client.get(href)
        self.assertIn('No roster-need filter was applied', expired.text)
        self.assertNotIn('Explore QB trades', self.read()['brief_html'])
