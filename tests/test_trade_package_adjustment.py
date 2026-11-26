"""Screenshot-shaped disposable replay through prepared Trade Center evidence."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.core.trade_intelligence.models import TradeProposal

from services.trade_intelligence import evaluate_trade_request, generate_trade_workflow
from src.core.intelligence.team_strength import prepare_for_data
from src.core.projection_intelligence.service import ProjectionService
from src.core.valuation.config import NORMALIZATION_VERSION
from tests.test_trade_intelligence import fixture_data

PICK = '2028-R3-1'


class TradePackageAdjustmentTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.projections = ProjectionService(Path(temp.name) / 'projections.sqlite3')
        self.data = fixture_data()
        self.data['teams'] = self.data['teams'][:2]
        self.data['week'] = 12
        self.data['league'].update(
            season=2026, sport='nfl',
            roster_positions=['QB', 'SUPER_FLEX', 'RB', 'BN', 'BN', 'BN'],
            scoring_settings={'pass_yd': 1}, settings={'leg': 12, 'last_scored_leg': 11,
                'start_week': 1, 'playoff_week_start': 14, 'playoff_teams': 4,
                'playoff_round_type': 0, 'playoff_type': 0, 'best_ball': 1})
        self.data['players'] = {}
        # The screenshots do not identify the split of the 955 combined points.
        # These two prices and all unshown source fields are synthetic.
        self.players = {
            'nix': ('Bo Nix', 'QB', 480, 18, 18),
            'young': ('Bryce Young', 'QB', 475, 15, 15),
            'active-qb': ('Fixture QB A', 'QB', 100, 13, 13),
            'active-rb': ('Fixture RB A', 'RB', 100, 10, 10),
            'burrow': ('Joe Burrow', 'QB', 776, 35.10, 27.38),
            'skattebo': ('Cam Skattebo', 'RB', 390, 10, 10),
            'partner-qb': ('Fixture QB B', 'QB', 100, 19, 19),
            'partner-rb': ('Fixture RB B', 'RB', 100, 7.05, 7.05),
        }
        team_names = ('The tankers', 'Crayon Eaters')
        for i, team in enumerate(self.data['teams']):
            team.update(team_name=team_names[i], players=[], picks_owned=[])
            for key in tuple(self.players)[i * 4:(i + 1) * 4]:
                name, position, *_ = self.players[key]
                player = dict(name=name, full_name=name, position=position, status='Active')
                self.data['players'][key] = player
                team['players'].append(dict(player, id=key, roster_slot='Bench'))
        self.data['teams'][0]['picks_owned'] = [
            {'year': 2028, 'round': 3, 'original_roster_id': 1, 'current_owner_id': 1}]
        self.publish()

    def publish(self, *, fresh=False):
        now = datetime.now(timezone.utc).isoformat()
        self.data['market_data'] = {'providers': {'FantasyCalc': {
                key: {'value': row[2] * 12, 'confidence': 90, 'retrieved_at': now}
                for key, row in self.players.items()
            }}, 'pick_quotes': {'FantasyCalc': [
                {'provider': 'FantasyCalc', 'market_format': 'fc:12:2qb:ppr',
                 'year': 2028, 'round': 3, 'pick_type': 'generic_round',
                 'availability': 'current', 'retrieved_at': now, 'value': 211 * 12,
                 'confidence': 80, 'normalization_reference': {
                     'provider': 'FantasyCalc', 'raw_value': float(211 * 12),
                     'normalized_value': 211, 'version': NORMALIZATION_VERSION,
                     'generation': 'disposable-package', 'method': 'provider_range_linear'}}
            ]}}
        payloads = {week: [{'player_id': key, 'season': 2026, 'week': week,
                           'stats': {'pass_yd': row[3 if week == 12 else 4]},
                           'player': {'position': row[1], 'status': 'Active'},
                           **({'updated_at': now} if fresh else {})}
                           for key, row in self.players.items()]
                    for week in (12, 13, 14, 15)}
        self.projections.publish_horizon(payloads, data=self.data, league_id='league-1',
                                         season=2026, current_week=12)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.projections, self.data)

    def evaluate(self, assets_sent=('nix', 'young', PICK), assets_received=('burrow', 'skattebo')):
        return evaluate_trade_request(self.data, {
            'active_roster_id': 1, 'partner_roster_id': 2, 'strategy': 'WIN NOW',
            'assets_sent': list(assets_sent), 'assets_received': list(assets_received)
        }, projection_reader=self.projections)['evaluation']

    def search(self):
        # Pin only construction to make sure the same exact candidate is actually
        # evaluated. Search admission, classification, ranking, and DTOs are real.
        def construction(active, partner, outgoing, incoming, **options):
            sent, received = {a.asset_id: a for a in outgoing}, {a.asset_id: a for a in incoming}
            self.assertEqual(options['required_received_asset_id'], 'burrow')
            return (TradeProposal(active, partner, (sent['nix'], sent['young'], sent[PICK]),
                                  (received['burrow'], received['skattebo']), '3-for-2'),)

        with patch('services.trade_intelligence._trade_projection_service', return_value=self.projections), \
                patch('services.trade_intelligence.generate_proposals', side_effect=construction):
            return generate_trade_workflow(self.data, {
                'workflow': 'trade_for', 'asset_id': 'burrow', 'active_roster_id': 1,
                'strategy': 'WIN NOW'})

    def change_player(self, key, *, value=None, points=None):
        label, pos, old_value, selected_week, later = self.players[key]
        self.players[key] = (label, pos, old_value if value is None else value,
                             selected_week if points is None else points, later if points is None else points)

    def test_burrow_package_remains_evaluable_but_cannot_rank_as_recommended(self):
        report = self.evaluate()
        self.assertEqual(report['values'], {'sent': 1166, 'received': 1166, 'ratio': 1})
        self.assertEqual(report['market_evidence']['difference'], 0)
        self.assertAlmostEqual(report['lineup_impact']['active']['delta'], 15.10)
        self.assertAlmostEqual(report['lineup_impact']['partner']['delta'], -20.05)
        dimensions = report['dimensions']
        self.assertAlmostEqual(dimensions['strategic_fit']['partner']['production_evidence']['mean_weekly_delta'], -14.26)
        self.assertEqual(dimensions['strategic_fit']['partner']['future_capital']['assessment']['net_market_value'], 211)
        self.assertEqual(dimensions['counterparty_plausibility']['reason_codes'], ['COUNTERPARTY_PACKAGE_COMPENSATION_UNESTABLISHED'])
        self.assertEqual(report['decision_context']['final_decision']['headline'], 'COUNTERPARTY LIMITED')
        self.assertFalse(report['generated_trade_eligible'])
        search = self.search()
        self.assertEqual(search['search_evidence']['full_evaluations'], 1)
        miss, = search['near_misses']
        self.assertIn('COUNTERPARTY_PACKAGE_COMPENSATION_UNESTABLISHED', miss['blockers'])
        self.assertEqual(miss['evaluation']['package_adjustment'], report['package_adjustment'])
        self.assertEqual(search['count'], 0)
        self.assertFalse(any(row['evaluation']['package_adjustment']['partner']['blocks_recommendation'] for row in search['results']))
        self.assertFalse(any(set(row['proposal']['assets_sent']) == {'nix', 'young', PICK}
                             and set(row['proposal']['assets_received']) == {'burrow', 'skattebo'} for row in search['results']))

    def test_premium_and_exact_capital_can_compensate_seller(self):
        self.change_player('young', value=575)
        self.publish()
        report = self.evaluate()
        self.assertTrue(report['generated_trade_eligible'])
        self.assertEqual(report['package_adjustment']['partner']['assessment'], 'COMPENSATED')
        self.assertAlmostEqual(report['lineup_impact']['partner']['delta'], -20.05)
        self.assertEqual(report['market_evidence']['difference'], -100)
        self.assertIn('Market premium', report['package_adjustment']['partner']['explanation'])
        search = self.search()
        rows = [row for row in search['results'] if set(row['proposal']['assets_sent']) == {'nix', 'young', PICK}
                and set(row['proposal']['assets_received']) == {'burrow', 'skattebo'}]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['evaluation']['package_adjustment'], report['package_adjustment'])
        self.assertEqual(rows[0]['evaluation']['dimensions']['counterparty_plausibility'], report['dimensions']['counterparty_plausibility'])

    def test_balanced_star_for_star_has_no_package_penalty(self):
        self.change_player('nix', value=776, points=25)
        self.change_player('burrow', points=25)
        self.publish()
        report = self.evaluate(assets_sent=('nix',), assets_received=('burrow',))
        self.assertEqual(report['values']['sent'], report['values']['received'])
        self.assertEqual(report['recommendation'], 'FAIR / OPTIONAL')
        self.assertFalse(report['generated_trade_eligible'])
        for row in report['package_adjustment'].values():
            self.assertEqual(row['assessment'], 'COMPARABLE')
            self.assertFalse(row['blocks_recommendation'])

    def test_distinct_best_ball_depth_is_supported_without_pricing_it(self):
        for key, points in {'nix': 20, 'young': 17, 'burrow': 20, 'active-qb': 16, 'active-rb': 5, 'partner-rb': 10}.items():
            self.change_player(key, points=points)
        self.publish(fresh=True)
        report = self.evaluate()
        self.assertEqual(report['market_evidence']['difference'], 0)
        partner = report['package_adjustment']['partner']
        self.assertEqual(partner['distinct_incoming_roles'], 2, report['dimensions']['package_quality']['partner'])
        self.assertEqual(partner['assessment'], 'COMPENSATED')
        self.assertIn('distinct useful roles', partner['explanation'])
        self.assertTrue(report['generated_trade_eligible'])
        self.publish()
        stale = self.evaluate()
        self.assertEqual(stale['package_adjustment']['partner']['assessment'], 'LIMITED')
        self.assertFalse(stale['generated_trade_eligible'])

    def test_review_keeps_equal_market_gauge_and_explains_why_the_package_is_limited(self):
        import os
        from unittest.mock import AsyncMock
        from urllib.parse import urlsplit
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from playwright.sync_api import sync_playwright
        from routes.trades import create_trades_router
        from tools.validation.browser_runtime import launch_chromium

        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: self.data,
                                               page=lambda title, body: body))
        with TestClient(app) as client, patch('src.core.projection_intelligence.projection_service', self.projections), \
                sync_playwright() as engine:
            for width in (320, 390, 1280):
                with self.subTest(width=width):
                    browser = launch_chromium(engine, headless=True)
                    try:
                        page = browser.new_page(viewport={'width': width, 'height': 844})
                        page.set_default_timeout(8000)
                        assessments = []

                        def route(intercept):
                            request = intercept.request
                            url = urlsplit(request.url)
                            if url.netloc != 'dtos.test':
                                return intercept.abort()
                            response = client.request(request.method, url.path + '?' + url.query,
                                content=request.post_data, headers={k: v for k, v in request.headers.items()
                                                                   if k == 'content-type'})
                            if url.path == '/api/trades/evaluate':
                                assessments.append((response.status_code, response.json()))
                            intercept.fulfill(status=response.status_code, content_type=response.headers.get('content-type'),
                                              body=response.content)

                        page.route('**/*', route)
                        page.goto('https://dtos.test/trades/create?front_office=1')
                        page.get_by_label('Trade partner', exact=True).select_option('2')
                        page.get_by_label('Trade strategy', exact=True).select_option('WIN NOW')
                        if width < 760:
                            page.get_by_role('button', name='My assets', exact=True).click()
                        for key in ('nix', 'young', PICK):
                            page.locator(f'#trade-sent-board button[data-asset-id="{key}"]').click()
                        if width < 760:
                            page.get_by_role('button', name='Their assets', exact=True).click()
                        for key in ('burrow', 'skattebo'):
                            page.locator(f'#trade-received-board button[data-asset-id="{key}"]').click()
                        page.get_by_role('button', name='Evaluate Trade', exact=True).click()
                        result = page.locator('#trade-result')
                        section = result.locator('.tw-valuation-gauge + section')
                        section.wait_for()
                        self.assertEqual(assessments[0][0], 200, assessments[0][1])
                        self.assertIn('Package adjustment', section.inner_text())
                        self.assertIn('Gives up Joe Burrow', section.inner_text())
                        self.assertIn('They lose projected lineup points', section.inner_text())
                        self.assertIn('0 Market points', result.locator('.tw-valuation-gauge').inner_text())
                        self.assertIn('COUNTERPARTY LIMITED', result.inner_text())
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        if directory := os.environ.get('DTOS_PACKAGE_ADJUSTMENT_EVIDENCE'):
                            folder = Path(directory)
                            folder.mkdir(parents=True, exist_ok=True)
                            result.screenshot(path=str(folder / f'package-review-{width}.png'))
                    finally:
                        browser.close()

    def test_adjustment_changes_order_and_keeps_roster_space_and_severe_loss_guards(self):
        from copy import deepcopy
        from services.trade_search_policy import rank_key

        self.change_player('young', value=575)
        self.publish()
        compensated = self.evaluate()
        comparable = deepcopy(compensated)
        comparable['package_adjustment']['partner']['assessment'] = 'COMPARABLE'
        self.assertLess(rank_key({'evaluation': comparable}), rank_key({'evaluation': compensated}))
        self.data['league']['roster_positions'] = ['QB', 'SUPER_FLEX', 'RB', 'BN']
        self.publish()
        capacity = self.evaluate(assets_received=('burrow',))
        self.assertEqual(capacity['package_adjustment']['partner']['spots_to_resolve'], 1)
        self.assertFalse(capacity['generated_trade_eligible'])
        self.change_player('burrow', value=100)
        self.change_player('skattebo', value=100)
        self.publish()
        severe = self.evaluate()
        self.assertIn('SEVERE_MARKET_LOSS', severe['reason_codes'])
        self.assertFalse(severe['generated_trade_eligible'])
