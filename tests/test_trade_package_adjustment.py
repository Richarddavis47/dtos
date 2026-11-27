"""Screenshot-shaped disposable replay through prepared Trade Center evidence."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.core.trade_intelligence.models import TradeProposal

from services.trade_intelligence import assist_trade_request, evaluate_trade_request, generate_trade_workflow
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

    def burrow_construction(self, active, partner, outgoing, incoming, **options):
        # Pin only construction so the exact offer reaches the real shared gates.
        sent, received = {a.asset_id: a for a in outgoing}, {a.asset_id: a for a in incoming}
        self.assertEqual(options['required_received_asset_id'], 'burrow')
        send, receive = getattr(self, 'pinned_offer', (('nix', 'young', PICK), ('burrow', 'skattebo')))
        return (TradeProposal(active, partner, tuple(sent[key] for key in send),
                              tuple(received[key] for key in receive), f'{len(send)}-for-{len(receive)}'),)

    def search(self):
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.projections), \
                patch('services.trade_intelligence.generate_proposals', side_effect=self.burrow_construction):
            return generate_trade_workflow(self.data, {
                'workflow': 'trade_for', 'asset_id': 'burrow', 'active_roster_id': 1,
                'strategy': 'WIN NOW'})

    def change_player(self, key, *, value=None, points=None):
        label, pos, old_value, selected_week, later = self.players[key]
        self.players[key] = (label, pos, old_value if value is None else value,
                             selected_week if points is None else points, later if points is None else points)

    def revision_request(self, **changes):
        return dict(repair_mode='BETTER_OFFER', origin_workflow='trade_for', origin_asset_id='burrow',
                    active_roster_id=1, partner_roster_id=2, strategy='WIN NOW',
                    assets_sent=['nix', 'young', PICK], assets_received=['burrow', 'skattebo']) | changes

    def revise(self, **changes):
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.projections):
            return assist_trade_request(self.data, self.revision_request(**changes))

    def prepare_rebuild_revision_control(self):
        # The larger original return costs the rebuild team too much Market
        # value. Either narrower deal can compensate their real lineup loss.
        self.data['teams'][1]['strategy'] = 'REBUILD'
        self.change_player('nix', value=400)
        self.change_player('young', value=290)
        self.publish()

    def test_published_burrow_revisions_need_supported_partner_compensation(self):
        original = self.evaluate()
        self.assertEqual(original['values'], {'sent': 1166, 'received': 1166, 'ratio': 1})
        self.assertFalse(original['generated_trade_eligible'])
        self.assertEqual(self.search()['count'], 0)
        for send, receive, sent_total, received_total in (
            (('nix', 'young', PICK, 'active-rb'), ('burrow', 'skattebo'), 1266, 1166),
            (('nix', 'young', PICK), ('burrow',), 1166, 776),
        ):
            with self.subTest(send=send, receive=receive):
                self.pinned_offer = (send, receive)
                evaluation = self.evaluate(send, receive)
                self.assertEqual((evaluation['values']['sent'], evaluation['values']['received']),
                                 (sent_total, received_total))
                self.assertTrue(evaluation['legal'])
                self.assertEqual(evaluation['decision_context']['final_decision']['headline'], 'COUNTERPARTY LIMITED')
                self.assertFalse(evaluation['generated_trade_eligible'])
                partner = evaluation['package_adjustment']['partner']
                self.assertTrue(partner['blocks_recommendation'])
                self.assertIn('projected lineup points', partner['explanation'])
                self.assertIn('draft capital and a Market premium', partner['explanation'])
                self.assertAlmostEqual(evaluation['lineup_impact']['partner']['delta'], -17.1)
                self.assertAlmostEqual(evaluation['dimensions']['strategic_fit']['partner']['production_evidence']['mean_weekly_delta'], -11.31)
                searched = self.search()
                self.assertEqual(searched['search_evidence']['full_evaluations'], 1)
                self.assertEqual(searched['count'], 0)
                miss, = searched['near_misses']
                self.assertEqual(miss['evaluation']['package_adjustment']['partner'], partner)
        del self.pinned_offer
        result = self.revise()
        self.assertTrue(result['preview_only'])
        self.assertEqual(result['original_proposal']['assets_sent'], ['nix', 'young', PICK])
        self.assertEqual(result['original_proposal']['assets_received'], ['burrow', 'skattebo'])
        self.assertEqual(result['count'], 0)
        self.assertIn('projected lineup loss', result['quiet_state'])
        evidence = result['search_evidence']
        self.assertGreater(evidence['full_evaluations'], 0)
        self.assertLessEqual(evidence['full_evaluations'], evidence['evaluation_budget'])

        self.prepare_rebuild_revision_control()
        result = self.revise()
        self.assertEqual(result['count'], 2)
        signatures = set()
        for row in result['results']:
            proposal, e = row['proposal'], row['evaluation']
            signatures.add((frozenset(proposal['assets_sent']), frozenset(proposal['assets_received'])))
            self.assertIn('burrow', proposal['assets_received'])
            self.assertIn(PICK, proposal['assets_sent'])
            self.assertTrue(e['generated_trade_eligible'])
            self.assertEqual(e['package_adjustment']['partner']['assessment'], 'COMPENSATED')
            self.assertGreater(e['lineup_impact']['partner']['delta'], original['lineup_impact']['partner']['delta'])
            self.assertEqual(e['dimensions']['strategic_fit']['active']['manager_strategy']['strategy'], 'WIN NOW')
            self.assertEqual(row['revision_evidence']['partner_comparison_weeks'], [12, 13, 14, 15])
            self.assertGreater(row['revision_evidence']['partner_mean_after'], row['revision_evidence']['partner_mean_before'])
        self.assertEqual(len(signatures), 2)
        self.assertEqual(self.evaluate()['values']['sent'], 901)
        from services.trade_intelligence import build_trade_workspace
        prices = {a.asset_id: a.trade_value for pool in build_trade_workspace(self.data, 1)['pools'].values() for a in pool}
        custom = self.revise(_personal_context={'mode': 'custom', 'revision': 1,
            'method': 'absolute_slot', 'neutral_values': prices, 'values': {**prices, 'burrow': 800},
            'preferences': {'active-rb': {'protect': True}}})
        self.assertGreater(custom['count'], 0)
        for row in custom['results']:
            e = row['evaluation']
            self.assertNotIn('active-rb', row['proposal']['assets_sent'])
            self.assertAlmostEqual(e['personal_value_evidence']['received']['total'] - e['market_evidence']['received']['total'], 24)
            self.assertEqual(e['package_adjustment']['partner']['assessment'], 'COMPENSATED')

    def test_positive_revision_uses_each_leagues_qb_rules(self):
        for name, slots, best_ball in [('Superflex', ['QB', 'SUPER_FLEX', 'RB'], 0), ('1-QB', ['QB', 'RB'], 0)]:
            with self.subTest(name=name):
                self.data['league'].update(roster_positions=[*slots, 'BN', 'BN', 'BN', 'BN'])
                self.data['league']['settings']['best_ball'] = best_ball
                self.prepare_rebuild_revision_control()
                result = self.revise(protected_assets=['active-rb'])
                self.assertGreater(result['count'], 0)
                for row in result['results']:
                    self.assertNotIn('active-rb', row['proposal']['assets_sent'])
                    self.assertIn(PICK, row['proposal']['assets_sent'])
                    self.assertEqual(row['evaluation']['package_adjustment']['partner']['extra_qb_slot'], name == 'Superflex')
                    self.assertTrue(row['evaluation']['generated_trade_eligible'])

    def test_revisions_preserve_target_protections_and_name_missing_market(self):
        result = self.revise(protected_assets=[PICK, 'active-rb'])
        self.assertFalse(result['results'])
        self.assertIn('projected lineup loss', result['quiet_state'])
        conflict = self.revise(excluded_assets=['burrow'])
        self.assertEqual(conflict['state'], 'CONSTRAINT_CONFLICT')
        self.assertEqual(conflict['search_evidence']['full_evaluations'], 0)
        self.data['market_data']['providers']['FantasyCalc'].pop('nix')
        missing = self.revise()
        self.assertEqual(missing['state'], 'MISSING_REQUIRED_EVIDENCE')
        self.assertIn('canonical Market', missing['quiet_state'])

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

        # The screenshot only establishes the two-QB subtotal. A comparable
        # incoming quarterback must not make the same documented cost vanish.
        self.change_player('nix', value=700)
        self.change_player('young', value=255)
        self.publish()
        other_split = self.evaluate()
        self.assertEqual(other_split['market_evidence'], report['market_evidence'])
        self.assertFalse(other_split['package_adjustment']['partner']['major_top_player_gap'])
        self.assertFalse(other_split['generated_trade_eligible'])
        self.assertIn('direction is unconfirmed', other_split['package_adjustment']['partner']['explanation'])
        self.assertEqual(self.search()['count'], 0)

    def test_supported_rebuild_can_give_up_production_at_equal_market(self):
        self.data['teams'][1]['strategy'] = 'REBUILD'
        report = self.evaluate()
        self.assertTrue(report['generated_trade_eligible'])
        self.assertEqual(report['package_adjustment']['partner']['assessment'], 'COMPENSATED')
        self.assertAlmostEqual(report['lineup_impact']['partner']['delta'], -20.05)
        self.assertEqual(report['market_evidence']['difference'], 0)
        self.assertIn('supported rebuild direction', report['package_adjustment']['partner']['explanation'])
        search = self.search()
        rows = [row for row in search['results'] if set(row['proposal']['assets_sent']) == {'nix', 'young', PICK}
                and set(row['proposal']['assets_received']) == {'burrow', 'skattebo'}]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['evaluation']['package_adjustment'], report['package_adjustment'])
        self.assertEqual(rows[0]['evaluation']['dimensions']['counterparty_plausibility'], report['dimensions']['counterparty_plausibility'])

    def test_supported_later_lineup_gain_can_justify_a_selected_week_loss(self):
        self.players['burrow'] = ('Joe Burrow', 'QB', 776, 21, 5)
        self.publish()
        report = self.evaluate()
        partner = report['dimensions']['strategic_fit']['partner']
        self.assertIsNone(partner['manager_strategy']['strategy'])
        self.assertAlmostEqual(report['lineup_impact']['partner']['delta'], -5.95)
        self.assertEqual(partner['production_evidence']['weeks_counted_once'], [12, 13, 14, 15])
        self.assertAlmostEqual(partner['production_evidence']['mean_weekly_delta'], 4.5125)
        self.assertEqual(report['dimensions']['counterparty_plausibility']['assessment'], 'PLAUSIBLE')
        self.assertIn('all compared weeks', report['package_adjustment']['partner']['explanation'])
        self.assertFalse(report['generated_trade_eligible'], 'The user still needs a supported benefit')

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
        import json
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from urllib.parse import urlsplit
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from fastapi.testclient import TestClient
        from playwright.sync_api import expect, sync_playwright
        import dtos_app
        from routes.trades import create_trades_router
        from tools.validation.browser_runtime import launch_chromium

        app = FastAPI()
        app.include_router(create_trades_router(ensure_fresh=AsyncMock(), require_data=lambda: self.data,
                                               page=dtos_app.page))
        app.mount('/static', StaticFiles(directory='static'), name='static')
        account = SimpleNamespace(account_id='fixture', session_id='research', csrf_token='fixture-only',
            display_name='Manager', membership=SimpleNamespace(league_id='league-1', roster_id=1,
                league_name='Dynasty Best Ball', franchise_name='The tankers'))
        navigation = {'scope': 'b' * 64, 'team': '/teams/1'}

        @app.get('/api/account/navigation-context')
        def navigation_context():
            return navigation

        @app.get('/players/burrow')
        def player_origin():
            return dtos_app.page('Player details', '<a href="/trades/trade-for?asset_id=burrow&amp;front_office=1">Trade For Joe Burrow</a>')

        def fully_reachable(locator):
            locator.evaluate("e=>e.scrollIntoView({block:'center'})")
            return locator.evaluate('''e => {
                const r = e.getBoundingClientRect();
                const nav = document.querySelector('.manager-nav').getBoundingClientRect();
                return r.height >= 44 && r.top >= 0 && r.bottom <= Math.min(innerHeight, nav.top)
                    && e.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
            }''')

        with TestClient(app) as client, patch('src.core.projection_intelligence.projection_service', self.projections), \
                patch('dtos_app.current_account', return_value=account), \
                patch.object(dtos_app.account_store, 'memberships', return_value=[]), \
                patch('routes.trades.current_account', return_value=account), \
                patch('services.trade_workspace_context.current_account', return_value=account), \
                patch('services.contextual_navigation.navigation_context', return_value=navigation), \
                sync_playwright() as engine:
            for width, rebuild in ((320, False), (390, False), (1280, False),
                                   (320, True), (390, True), (1280, True)):
                with self.subTest(width=width, rebuild=rebuild):
                    if rebuild:
                        self.prepare_rebuild_revision_control()
                    browser = launch_chromium(engine, headless=True)
                    try:
                        page = browser.new_page(viewport={'width': width, 'height': 432 if width == 320 else 844}, has_touch=width < 600)
                        page.set_default_timeout(8000)
                        assessments = []
                        requests = []
                        generated = []

                        def route(intercept):
                            request = intercept.request
                            url = urlsplit(request.url)
                            if url.netloc != 'dtos.test':
                                return intercept.abort()
                            if url.path == '/api/trades/assist':
                                requests.append((json.loads(request.post_data), None))
                                if width == 320 and len(requests) == 1:
                                    return intercept.fulfill(status=503, json={'detail': {'code': 'trade_capacity_deferred', 'message': 'The Trade workspace is at capacity. Try again.'}})
                            pinned = patch('services.trade_intelligence.generate_proposals', side_effect=self.burrow_construction)
                            with pinned if url.path == '/api/trades/generate' else nullcontext():
                                response = client.request(request.method, url.path + '?' + url.query,
                                    content=request.post_data, headers={k: v for k, v in request.headers.items()
                                                                       if k == 'content-type'})
                            if url.path == '/api/trades/evaluate':
                                assessments.append((response.status_code, response.json()))
                            if url.path == '/api/trades/generate':
                                generated.append(response.json())
                            if url.path == '/api/trades/assist':
                                requests[-1] = (requests[-1][0], response.json())
                            intercept.fulfill(status=response.status_code, headers=dict(response.headers),
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
                        self.assertIn('projected lineup points', section.inner_text())
                        if not rebuild:
                            self.assertIn('Negotiation option · partner benefit unconfirmed', section.inner_text())
                        gauge = '265 Market points' if rebuild else '0 Market points'
                        self.assertIn(gauge, result.locator('.tw-valuation-gauge').inner_text())
                        self.assertIn('COUNTERPARTY LIMITED', result.inner_text())
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        if not rebuild and (directory := os.environ.get('DTOS_PACKAGE_ADJUSTMENT_EVIDENCE')):
                            folder = Path(directory)
                            folder.mkdir(parents=True, exist_ok=True)
                            result.screenshot(path=str(folder / f'package-review-{width}.png'))
                        button = result.get_by_role('button', name='Show me a better offer')
                        expect(button).to_be_visible()
                        expect(result.locator('.tw-review-verdict')).to_have_text('COUNTERPARTY LIMITED')
                        self.assertTrue(result.locator('.tw-review-verdict').evaluate("e=>e.compareDocumentPosition(e.parentElement.querySelector('.tw-valuation-gauge')) & Node.DOCUMENT_POSITION_FOLLOWING"))
                        self.assertFalse(requests)
                        if width < 600:
                            self.assertTrue(fully_reachable(button))
                        if width == 320:
                            button.tap()
                            expect(result.locator('.tw-better-offer')).to_have_attribute('data-state', 'deferred')
                            expect(result.locator('.tw-valuation-gauge')).to_contain_text(gauge)
                        button.press('Enter')
                        state = 'complete' if rebuild else 'MISSING_REQUIRED_EVIDENCE'
                        expect(result.locator('.tw-better-offer')).to_have_attribute('data-state', state, timeout=12000)
                        self.assertEqual(requests[-1][0]['assets_sent'], ['nix', 'young', PICK])
                        self.assertEqual(requests[-1][0]['assets_received'], ['burrow', 'skattebo'])
                        self.assertEqual(requests[-1][0]['strategy'], 'WIN NOW')
                        revisions = result.locator('.tw-revision-grid article')
                        expect(revisions).to_have_count(2 if rebuild else 0)
                        if rebuild:
                            first_box, second_box = [row.bounding_box() for row in revisions.all()]
                            if width < 600:
                                self.assertGreater(second_box['y'], first_box['y'] + first_box['height'])
                            else:
                                self.assertGreater(second_box['x'], first_box['x'] + first_box['width'])
                            expect(result.locator('.tw-revision-grid')).to_contain_text('Why it may help them')
                            expect(result.locator('.tw-revision-grid')).to_contain_text('Your cost or risk')
                            expect(result.locator('.tw-revision-grid')).to_contain_text('The tankers')
                        else:
                            expect(result.locator('.tw-better-offer')).to_contain_text('projected lineup loss')
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        last = result.get_by_role('button', name='Use revision 2 in my draft')
                        if rebuild and width < 600:
                            self.assertTrue(fully_reachable(last))
                        # Reviews alone only update UI. A foreign workspace ID
                        # cannot be replayed even with otherwise identical IDs.
                        bad = {**requests[-1][0], 'workspace_context': {**requests[-1][0]['workspace_context'], 'league_id': 'other-league'}}
                        invalid = client.post('/api/trades/assist', json=bad)
                        self.assertEqual(invalid.json()['detail']['code'], 'workspace_context_changed')
                        if directory := os.environ.get('DTOS_BETTER_OFFER_EVIDENCE'):
                            folder = Path(directory)
                            folder.mkdir(parents=True, exist_ok=True)
                            view = 'revisions' if rebuild else 'no-revisions'
                            result.screenshot(path=str(folder / f'{view}-{width}.png'))
                            if width == 390:
                                (folder/f'burrow-{view}-decision-trace.json').write_text(json.dumps({
                                    'scope': 'Disposable prepared fixture, with synthetic prices where the source screenshot did not show them',
                                    'original': assessments[0][1], 'revisions': requests[-1][1],
                                }, indent=2))
                        if width == 320:
                            page.reload()
                            expect(page.locator('#trade-sent-board')).to_be_attached()
                            expect(page.locator('#calculator-sent')).to_contain_text('Bo Nix')
                            expect(page.locator('#calculator-received')).to_contain_text('Cam Skattebo')
                            self.assertEqual(len(requests), 2)
                        if width == 390 and rebuild:
                            revisions.filter(has=page.get_by_text('You receive: Joe Burrow', exact=True)).get_by_role(
                                'button', name='Use revision').tap()
                            expect(page.locator('#calculator-received')).not_to_contain_text('Cam Skattebo')
                        if width == 1280 and not rebuild:
                            page.goto('https://dtos.test/players/burrow?week=12')
                            page.get_by_role('link', name='Trade For Joe Burrow').click()
                            page.wait_for_url('**/trades/trade-for?*')
                            self.assertEqual(len(requests), 1)
                            if page.get_by_label('Trade strategy', exact=True).input_value() != 'WIN NOW':
                                page.get_by_label('Trade strategy', exact=True).select_option('WIN NOW')
                                page.locator('#trade-find').click()
                            near = page.locator('.tw-near-misses')
                            try:
                                expect(near.locator(':scope > summary')).to_be_visible()
                            except AssertionError as exc:
                                self.fail(f"{exc}\nResult: {result.inner_text()[:1200]}; search count and state: "
                                          f"{[(body.get('count'), body.get('result_state'), len(body.get('near_misses', []))) for body in generated]}")
                            near.locator(':scope > summary').click()
                            near.get_by_role('button', name='Review trade').click()
                            expect(result.locator('.tw-valuation-gauge')).to_contain_text('0 Market points')
                            result.get_by_role('button', name='Show me a better offer').click()
                            expect(result.locator('.tw-better-offer')).to_have_attribute('data-state', 'MISSING_REQUIRED_EVIDENCE', timeout=12000)
                            self.assertEqual(requests[-1][0]['origin_workflow'], 'trade_for')
                            self.assertEqual(requests[-1][0]['origin_asset_id'], 'burrow')
                            self.assertEqual(requests[-1][0]['assets_received'], ['burrow', 'skattebo'])
                            page.locator('#dtos-back').click()
                            page.wait_for_url('**/players/burrow?week=12')
                    finally:
                        self.data['teams'][1].pop('strategy', None)
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
