"""Prepared Trade evidence: scan, review and return without another operation."""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest

from html.parser import HTMLParser
from services.trade_explanation import render_trade_explanation
from tests import test_trade_lineup_detail as native
from tests import test_trade_for_acquisition_browser as prepared
from tests import test_trade_scout_state_browser as scout


class _Document(HTMLParser):
    """Small structural reader for trusted rendered HTML, with no dependency."""
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = dict(tag='root', attrs={}, children=[])
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = dict(tag=tag, attrs=dict(attrs), children=[])
        self.stack[-1]['children'].append(element)
        if tag not in {'br', 'img', 'input', 'link', 'meta', 'hr', 'source', 'wbr'}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]['tag'] == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, value):
        self.stack[-1]['children'].append(value)


def _elements(element, *, direct=False):
    for child in element['children']:
        if isinstance(child, dict):
            yield child
            if not direct:
                yield from _elements(child)


def _class(element, name, *, direct=False):
    return next((child for child in _elements(element, direct=direct)
                 if name in (child['attrs'].get('class') or '').split()), None)


def _text(element):
    return ''.join(_text(child) if isinstance(child, dict) else child
                   for child in element['children'])


class CustomerTradePresentationTests(unittest.TestCase):
    def fixture(self):
        fixture = native.TradeLineupDetailTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_current_effects_and_principal_risk_lead_without_mutating_results(self):
        fixture = self.fixture()
        result = fixture.evaluate()
        original = deepcopy(result)
        soup = _Document(render_trade_explanation(result, league_id='one-qb')).root
        lead = _class(soup, 'tw-decision')
        self.assertIsNotNone(lead)
        summary = _class(lead, 'tw-team-summary', direct=True)
        self.assertEqual([_text(h) for h in _elements(summary) if h['tag'] == 'h4'], ['Your team', 'Their team'])
        self.assertIn('week 8', _text(summary).lower())
        deeper = _class(lead, 'tw-team-impact-details', direct=True)
        self.assertIsNotNone(deeper)
        self.assertNotIn('open', deeper['attrs'])
        self.assertIn('replacement', _text(deeper).lower())
        self.assertIn(result['decision_context']['main_cost'], _text(lead))
        self.assertEqual(result, original)

    def test_missing_def_remains_incomplete_in_rendered_lineups(self):
        fixture = self.fixture()
        fixture.f.feed = [row for row in fixture.f.feed if row['player_id'] != '1-9']
        fixture.f.publish()
        result = fixture.evaluate()
        original = deepcopy(result)
        soup = _Document(render_trade_explanation(result, league_id='one-qb')).root
        summary = _class(_class(soup, 'tw-decision'), 'tw-team-summary', direct=True)
        sides = [child for child in _elements(summary, direct=True) if child['tag'] == 'section']
        self.assertEqual(len(sides), 2)
        active, partner = map(_text, sides)
        self.assertIn('Your team', active)
        self.assertIn('cannot be verified', active)
        self.assertNotIn('+0.00 projected points', active)
        # The unrelated, independently complete opponent comparison retains its
        # genuine zero rather than becoming unknown because our DEF is missing.
        self.assertIn('Their team', partner)
        self.assertIn('+0.00 projected points', partner)
        comparison = result['decision_context']['partner_lineup_comparisons']['current_week']
        if isinstance(comparison, str):
            comparison = json.loads(comparison)
        self.assertEqual(comparison['delta'], 0)
        self.assertIn('DEF', _text(_class(soup, 'tw-lineup-details')))
        self.assertEqual(result, original)


class CustomerTradeJourneyTests(unittest.TestCase):
    def test_compact_offer_review_compare_and_back_keeps_original_work(self):
        helper = prepared.AcquisitionBrowserTests()
        harness = scout.ScoutWorkspaceStateBrowserTests()
        rows = helper.offer_panel()
        for row in rows:
            row['evaluation']['decision_context'] = {
                'decisive_reason': 'The supported upgrade has a real cost for both teams.',
                'main_cost': 'You spend usable depth.',
                'summary': 'Your supported roster benefit remains conditional.',
                'partner_summary': 'Their assets provide a supported return; willingness is unconfirmed.',
                'qualification': 'Provisional: recorded participation needs review. Not a qualified bilateral recommendation.',
                'lineup_comparisons': {'current_week': {'state': 'provisional', 'weeks': [10], 'delta': 2.25}},
                'partner_lineup_comparisons': {'current_week': {'state': 'supported', 'weeks': [10], 'delta': -1.5}},
                'your_side_summary': 'Your team: Week10 change +2.25.\nUsable replacement-depth coverage is incomplete.',
                'their_side_summary': 'Their team: Week10 change -1.50.\nSupported replacement depth declines.',
            }
            row['evaluation']['explanation_html'] = ('<section class="dtos-explanation"><p>Recorded fixture decision.</p>'
                '<p class="tw-lineup-warning">Your team · Season 2026 · Week 10: Incoming Player — Excluded from usable cover · IR.</p>'
                '<details class="tw-lineup-details"><summary>Before and after · both optimal lineups</summary>'
                '<p>Prepared fixture slot detail: QB, FLEX, K, DEF. Not submitted Sleeper starters.</p></details>'
                '<p>Exact technical source context is retained here.</p></section>')
        original = deepcopy(rows)
        records = []
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            with self.subTest(width=width):
                def api(route, payload):
                    self.assertTrue(route.request.url.endswith('/generate'))
                    route.fulfill(json={'workflow': 'trade_for', 'results': deepcopy(rows), 'count': len(rows)})
                with helper.page(width, api=api) as (page, requests):
                    page.set_viewport_size({'width': width, 'height': height})
                    harness.ready(page, '/trades/trade-for?asset_id=player:x')
                    self.assertEqual(requests, [])
                    page.locator('#trade-find').press('Enter')
                    first = page.locator('#trade-result > article.tw-offer').first
                    first.get_by_role('button', name='Review trade', exact=True).wait_for()
                    count = len(requests)
                    before = harness.proposal(page)
                    text = first.inner_text()
                    for phrase in ('WORTH PURSUING', 'You send:', 'You receive:', 'usable depth', 'Incoming Player', 'IR', 'provisional', 'Your team:', 'Their team:', '+2.25', '-1.50', 'Neutral Market', 'Best-supported fit found'):
                        self.assertIn(phrase, text)
                    self.assertNotIn('Exact technical source context', text)
                    self.assertIn('Not a qualified recommendation for both teams.', text)
                    self.assertNotIn('bilateral', text.lower())
                    self.assertEqual(first.locator('.tw-draft-capital, .tw-lineup-details').count(), 0)
                    self.assertEqual(first.locator('button.primary').count(), 1)
                    self.assertLess(len(text), 2000)
                    metrics = dict(width=width, height=height, default_card_height=first.bounding_box()['height'], default_characters=len(text), fixture='Prepared component fixture; separate native-evaluator visual replay required')
                    if os.getenv('DTOS_CUSTOMER_TRADE_EVIDENCE'):
                        folder = Path(os.environ['DTOS_CUSTOMER_TRADE_EVIDENCE'])
                        folder.mkdir(parents=True, exist_ok=True)
                        first.screenshot(path=str(folder / f'compact-{width}.png'))
                    first.get_by_role('button', name='Review trade', exact=True).press('Enter')
                    review = page.locator('#trade-result > article.tw-offer-review')
                    self.assertIn('Incoming Player', review.inner_text())
                    self.assertIn('inference', review.inner_text())
                    detail = review.locator(':scope > .tw-lineup-details')
                    detail.locator('summary').press('Enter')
                    self.assertIn('FLEX, K, DEF', detail.inner_text())
                    review.locator('.tw-depth-details > summary').click()
                    self.assertIn('Usable replacement-depth coverage is incomplete', review.inner_text())
                    self.assertIn('Excluded from usable cover · IR', review.inner_text())
                    self.assertEqual(harness.proposal(page), before)
                    self.assertEqual(len(requests), count)
                    review.get_by_role('button', name='Add to comparison', exact=True).click()
                    page.get_by_role('button', name='Back to offers', exact=True).click()
                    cheap = page.locator('#trade-result > article.tw-offer').filter(has_text='Lowest-cost supported offer found').first
                    self.assertIn('FAIR / OPTIONAL', cheap.inner_text())
                    cheap.get_by_role('button', name='Add to comparison', exact=True).click()
                    page.get_by_role('button', name='Compare selected offers', exact=True).click()
                    self.assertIn('FAIR / OPTIONAL', page.locator('#trade-comparison').inner_text())
                    page.get_by_role('button', name='Return to my offer or draft', exact=True).click()
                    self.assertEqual(harness.proposal(page), before)
                    self.assertEqual(len(requests), count)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                    metrics.update(extra_inspection_requests=len(requests)-count, draft_preserved=True, overflow=False)
                    records.append(metrics)
        self.assertEqual(rows, original)
        if os.getenv('DTOS_CUSTOMER_TRADE_EVIDENCE'):
            (Path(os.environ['DTOS_CUSTOMER_TRADE_EVIDENCE']) / 'journey.json').write_text(json.dumps(records, indent=2)+'\n')

    def test_retained_pick_label_does_not_follow_today_franchise_rename(self):
        helper = prepared.AcquisitionBrowserTests()
        harness = scout.ScoutWorkspaceStateBrowserTests()
        workspace = harness.workspace()
        workspace['workspace_context'].update(league_id='fixture', roster_id=1)
        workspace['manager_context']['roster_id'] = 1
        workspace['active_front_office'] = 1
        workspace['teams'].append({'roster_id': 3, 'team_name': 'Harbor at assessment', 'assets': []})
        pick = 'pick:2028:1:3'
        row = harness.offer([pick], ['player:x'])
        row['evaluation']['provenance'] = {'evaluation_id': 'retained-label-fixture', 'inputs': {'league_id': 'fixture', 'active_roster_id': 1}}
        row['proposal_presentation'] = {'send': [dict(asset_id=pick, label='Recorded2028 first · Harbor', kind='pick', year=2028, round=1, original_franchise=3)], 'receive': [dict(asset_id='player:x', label='Recorded target X', kind='player')]}
        def api(route, payload):
            self.assertTrue(route.request.url.endswith('/generate'))
            route.fulfill(json={'workflow': 'trade_for', 'results': [deepcopy(row)], 'count': 1})
        with helper.page(375, workspace=workspace, api=api) as (page, requests):
            harness.ready(page, '/trades/trade-for?asset_id=player:x')
            page.locator('#trade-find').press('Enter')
            page.get_by_role('button', name='Review trade', exact=True).click()
            original = harness.proposal(page)
            count = len(requests)
            workspace['teams'][2]['team_name'] = 'TODAY renamed franchise'
            workspace['teams'][1]['team_name'] = 'TODAY renamed partner'
            next(a for a in workspace['teams'][0]['assets'] if a['asset_id'] == pick)['label'] = 'TODAY renamed pick'
            page.reload()
            page.get_by_role('button', name='Use this offer in my draft', exact=True).wait_for()
            package = page.locator('.tw-offer-review .tw-offer-package').first.inner_text()
            self.assertIn('Recorded2028 first · Harbor', package)
            self.assertIn('original franchise #3', package)
            self.assertNotIn('TODAY', package)
            self.assertIn('NOT REVALIDATED', page.locator('.tw-offer-review').inner_text())
            self.assertEqual(harness.proposal(page), original)
            self.assertEqual(len(requests), count)
            page.locator('.tw-offer-review').get_by_role('button', name='Add to comparison', exact=True).click()
            selected = page.evaluate('JSON.parse(sessionStorage.getItem("dtos-trade-workspace:scout-session")).comparisonOffers')
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['summary']['partner'], 'Partner')
            self.assertEqual([a['id'] for a in selected[0]['assets']['sent']], [pick])
            self.assertEqual([a['id'] for a in selected[0]['assets']['received']], ['player:x'])
            self.assertIn('Recorded2028 first · Harbor', selected[0]['assets']['sent'][0]['label'])
            self.assertIn('original franchise #3', selected[0]['assets']['sent'][0]['label'])
            self.assertNotIn('TODAY', selected[0]['assets']['sent'][0]['label'])
            page.get_by_role('button', name='Compare selected offers', exact=True).click()
            comparison = page.locator('#trade-comparison')
            self.assertIn('Recorded2028 first · Harbor', comparison.inner_text())
            self.assertIn('NOT REVALIDATED', comparison.inner_text())
            self.assertNotIn('TODAY', comparison.locator('ol').first.inner_text())
            self.assertEqual(len(requests), count)
            page.get_by_role('button', name='Remove offer 1', exact=True).click()
            page.get_by_role('button', name='Return to my offer or draft', exact=True).click()
            self.assertEqual(harness.proposal(page), original)
            # A missing session copy must not discard the valid recorded names
            # in the same generation's history snapshot.
            page.evaluate("""() => { const key='dtos-trade-workspace:scout-session'; const s=JSON.parse(sessionStorage.getItem(key)); delete s.previewProposal.preview_presentation; sessionStorage.setItem(key,JSON.stringify(s)); }""")
            page.reload()
            page.get_by_role('button', name='Use this offer in my draft', exact=True).wait_for()
            package = page.locator('.tw-offer-review .tw-offer-package').first.inner_text()
            self.assertIn('Recorded2028 first · Harbor', package)
            self.assertIn('2028 round 1 · original franchise #3', package)
            self.assertNotIn('TODAY', package)
            recorded = page.evaluate('JSON.parse(sessionStorage.getItem("dtos-trade-workspace:scout-session"))')
            self.assertEqual(recorded['previewProposal']['assets_sent'], [pick])
            self.assertEqual(recorded['previewProposal']['assets_received'], ['player:x'])
            # The browser history snapshot is another legitimate retained copy.
            # Remove names from both stores to actually exercise an older state
            # without presentation metadata, rather than discarding valid names.
            page.evaluate("""() => {
              const strip = draft => {if(draft?.previewProposal){delete draft.previewProposal.preview_presentation;delete draft.previewProposal.preview_context.identity.counterparty;}};
              const key='dtos-trade-workspace:scout-session', saved=JSON.parse(sessionStorage.getItem(key));
              strip(saved);sessionStorage.setItem(key,JSON.stringify(saved));
              const state=history.state;
              if(state?.dtosTrade?.draft){strip(state.dtosTrade.draft);history.replaceState(state,'');}
            }""")
            page.reload()
            page.get_by_role('button', name='Use this offer in my draft', exact=True).wait_for()
            package = page.locator('.tw-offer-review .tw-offer-package').first.inner_text()
            self.assertNotIn('TODAY', package)
            self.assertIn('NOT REVALIDATED', page.locator('.tw-offer-review').inner_text())
            legacy = page.evaluate('JSON.parse(sessionStorage.getItem("dtos-trade-workspace:scout-session"))')
            self.assertEqual(legacy['previewProposal']['assets_sent'], [pick])
            self.assertEqual(legacy['previewProposal']['assets_received'], ['player:x'])
            self.assertNotIn('TODAY', page.locator('.tw-offer-review').inner_text())
            page.locator('.tw-offer-review').get_by_role('button', name='Add to comparison', exact=True).click()
            legacy_comparison = page.evaluate('JSON.parse(sessionStorage.getItem("dtos-trade-workspace:scout-session")).comparisonOffers')
            self.assertEqual([a['id'] for a in legacy_comparison[0]['assets']['sent']], [pick])
            self.assertEqual([a['id'] for a in legacy_comparison[0]['assets']['received']], ['player:x'])
            self.assertNotIn('TODAY', legacy_comparison[0]['assets']['sent'][0]['label'])
            self.assertIn('Franchise #2', legacy_comparison[0]['summary']['partner'])
            self.assertIn('recorded name unavailable', legacy_comparison[0]['summary']['partner'])
            self.assertNotIn('TODAY', legacy_comparison[0]['summary']['partner'])
            self.assertEqual(harness.proposal(page), original)
            self.assertEqual(len(requests), count)

    def test_optional_custom_pricing_stays_collapsed_until_selected_or_opened(self):
        helper = prepared.AcquisitionBrowserTests()
        harness = scout.ScoutWorkspaceStateBrowserTests()
        for active_custom in (False, True):
            with self.subTest(active_custom=active_custom):
                workspace = harness.workspace()
                workspace['personalization'] = dict(mode='custom' if active_custom else 'neutral', revision=2,
                    available=active_custom, method='relative_priced_order_v1', method_label='Relative Priced-Order',
                    personal_partial_available=active_custom, personal_value_count=3,
                    readiness_code='ready' if active_custom else 'market_unavailable',
                    market_generation='fixture-market', baseline_generation='fixture-baseline',
                    limitations=['Custom prices have not been prepared for these assets.'], values={})
                with helper.page(375, workspace=workspace) as (page, requests):
                    personal_reads = []
                    def personal(route):
                        personal_reads.append(route.request.url)
                        route.fulfill(status=503, json={'detail': 'Controlled optional Custom evidence unavailable'})
                    page.route('**/api/my-dtos', personal)
                    harness.ready(page, '/trades/create?front_office=1')
                    select = page.locator('#trade-valuation-mode')
                    pricing = page.locator('.tw-custom-pricing')
                    notice = page.locator('.tw-active-valuation-notice')
                    self.assertEqual(pricing.get_attribute('open'), None)
                    self.assertEqual(select.input_value(), 'custom' if active_custom else 'neutral')
                    self.assertEqual(select.locator('option[value=neutral]').inner_text(), 'Neutral Market')
                    if not active_custom:
                        self.assertTrue(notice.is_hidden())
                        self.assertTrue(page.locator('#trade-personal-retry').is_hidden())
                        self.assertNotIn('Custom prices have not been prepared', page.locator('.tw-valuation-mode').inner_text())
                        summary = pricing.locator(':scope > summary')
                        summary.focus()
                        summary.press('Enter')
                        self.assertTrue(pricing.evaluate('e=>e.open'))
                        self.assertIn('Custom prices have not been prepared', pricing.inner_text())
                        self.assertTrue(page.locator('#trade-personal-retry').is_visible())
                        summary.press('Enter')
                        self.assertTrue(page.locator('#trade-personal-retry').is_hidden())
                        self.assertEqual(select.input_value(), 'neutral')
                    else:
                        self.assertTrue(notice.is_visible())
                        self.assertIn('Relative Priced-Order', notice.inner_text())
                        self.assertIn('Some assets have unverified personal values', notice.inner_text())
                        original = harness.proposal(page)
                        before = len(personal_reads)
                        page.evaluate('window.dispatchEvent(new Event("focus"))')
                        page.wait_for_function("document.querySelector('.tw-active-valuation-notice').textContent.includes('need review')")
                        self.assertEqual(len(personal_reads), before + 1)
                        self.assertEqual(select.input_value(), 'custom')
                        self.assertEqual(harness.proposal(page), original)
                        self.assertTrue(notice.is_visible())
                    self.assertEqual(requests, [])
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
