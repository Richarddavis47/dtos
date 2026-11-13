"""Real disposable authenticated routes, source evaluation and contextual Back.

No seeded recommendation, fake admission or provider acquisition. Chromium
touch emulation is not physical iPhone/Safari acceptance.
"""
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
from unittest import TestCase
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tools.validation.browser_runtime import launch_chromium
from tests import test_contextual_back as contextual_back


class TradePartnerHistoryBrowserTests(TestCase):
    def fixture(self):
        from routes.history import create_history_router
        from src.core.history_context.store import CanonicalHistoryStore
        from src.core.history_context.season_cache import SleeperSeasonCache
        import dtos_app
        helper = contextual_back.ContextualBackTests()
        self.addCleanup(helper.doCleanups)
        f = helper.fixture()
        directory = self.enterContext(tempfile.TemporaryDirectory())
        cache = SleeperSeasonCache(Path(directory))
        store = CanonicalHistoryStore()
        self.enterContext(patch('src.core.history_context.store.sleeper_season_cache', cache))
        self.enterContext(patch('services.history.historical_store', store))
        self.enterContext(patch('services.history.canonical_history_store', store))
        store.update_current('league-1', f.editor.data)
        f.editor.app.include_router(create_history_router(
            league_id='league-1', page=dtos_app.page, require_data=lambda: f.editor.data,
            league_resolver=lambda: f.editor.data['league']['league_id']))
        return helper, f

    def record(self, name, rows):
        folder = os.environ.get('DTOS_PARTNER_HISTORY_EVIDENCE')
        if folder:
            destination = Path(folder)
            destination.mkdir(parents=True, exist_ok=True)
            identity = {key: subprocess.check_output(command, text=True).strip() for key, command in (
                ('commit', ['git', 'rev-parse', 'HEAD']), ('tree', ['git', 'rev-parse', 'HEAD^{tree}']))}
            (destination / (name + '.json')).write_text(json.dumps({
                **identity, 'source': 'disposable prepared league; real authenticated HTTP and evaluator',
                'physical_safari_tested': False, 'checks': rows}, indent=2) + '\n')

    def round_trip(self, helper, page, requests, path, *, touch=False):
        link = page.locator('#trade-result .tw-partner-history').first
        self.assertEqual(link.inner_text(), 'See franchise trade history')
        self.assertIn('league-1%3Afranchise%3A2', link.get_attribute('href'))
        link.scroll_into_view_if_needed()
        box = link.bounding_box()
        self.assertGreaterEqual(box['height'], 40)
        before_posts = [r for r in requests if r[0] == 'POST']
        if touch:
            cdp = page.context.new_cdp_session(page)
            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x'] + box['width']/2, 'y': box['y'] + box['height']/2}]})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
            cdp.detach()
        else:
            page.keyboard.press('Tab')
            link.focus()
            self.assertNotEqual(link.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
            page.keyboard.press('Enter')
        page.wait_for_url('**/history/team/league-1%3Afranchise%3A2')
        self.assertIn('Completed trade observations', page.locator('body').inner_text())
        self.assertIn('totals are unknown', page.locator('body').inner_text())
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), page.viewport_size['width'])
        folder = os.environ.get('DTOS_PARTNER_HISTORY_EVIDENCE')
        if folder:
            output = Path(folder)
            output.mkdir(parents=True, exist_ok=True)
            stem = path.rsplit('/', 1)[-1] + '-' + str(page.viewport_size['width'])
            page.screenshot(path=str(output / (stem + '-history.png')), full_page=True)
        helper.back(page, path)
        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
        page.locator('#trade-result .tw-partner-history').first.wait_for()
        self.assertEqual([r for r in requests if r[0] == 'POST'], before_posts)
        if folder:
            page.screenshot(path=str(output / (stem + '-returned.png')), full_page=True)
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), page.viewport_size['width'])

    def test_evaluation_round_trip_retains_custom_draft_and_filters_at_four_sizes(self):
        helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        helper.choose(page)
        page.select_option('#trade-valuation-mode', 'custom')
        page.locator('[data-side=sent]').click()
        page.get_by_role('searchbox', name='Search my assets').fill('a')
        page.locator('#trade-run').click()
        page.locator('#trade-result .tw-partner-history').wait_for()
        before = helper.draft(page)
        saved = f.editor.state()
        rows = []
        with patch('services.sleeper.sleeper_get', side_effect=AssertionError('navigation must not acquire a provider')):
            for width, height in [(320,432), (375,667), (390,844), (1280,900)]:
                page.set_viewport_size({'width': width, 'height': height})
                self.round_trip(helper, page, requests, '/trades/create', touch=width==390)
                after = helper.draft(page)
                for key in ('currentProposal', 'valuationMode', 'strategy'):
                    self.assertEqual(after[key], before[key])
                self.assertEqual(after['navigationView']['filters'], before['navigationView']['filters'])
                self.assertEqual(after['currentAssessment']['identity']['package'], before['currentAssessment']['identity']['package'])
                rows.append({'viewport': [width,height], 'mode': after['valuationMode'], 'draft': after['currentProposal'], 'filters': after['navigationView']['filters'], 'post_requests': [r for r in requests if r[0]=='POST']})
        self.assertEqual(f.editor.state(), saved)
        self.assertFalse(errors, errors)
        self.record('evaluation-round-trip', rows)

    def test_recommendation_round_trip_retains_clicked_offer_without_adopting(self):
        helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, requests, _, _, errors = helper.page(browser, f)
        helper.ready(page, '/trades/recommended')
        initial = helper.draft(page)
        original = initial['currentProposal']
        page.select_option('#trade-strategy', 'REBUILD')
        page.locator('#trade-find').click()
        offer = page.locator('#trade-result .tw-offer').first
        review = offer.get_by_role('button', name='Review trade', exact=True)
        review.wait_for(timeout=30000)
        package = offer.locator(':scope > p').filter(has_text=re.compile(r'^You (send|receive):')).all_text_contents()
        self.assertTrue(package)
        # Partner history belongs to the organized review, not every compact
        # offer card. Opening that prepared review does not adopt or evaluate.
        self.assertEqual(offer.locator('.tw-partner-history').count(), 0)
        before_review_posts = [r for r in requests if r[0] == 'POST']
        review.focus()
        page.keyboard.press('Enter')
        page.locator('#trade-result .tw-offer-review .tw-partner-history').first.wait_for()
        self.assertEqual([r for r in requests if r[0] == 'POST'], before_review_posts)
        self.assertEqual(helper.draft(page)['currentProposal'], original)
        clicked = helper.draft(page)['previewProposal']
        self.assertIsNotNone(clicked)
        expected = {k: clicked[k] for k in ('partner_roster_id','assets_sent','assets_received')}
        self.assertEqual(page.locator('#trade-result .tw-offer-review').first.locator(':scope > p').filter(has_text=re.compile(r'^You (send|receive):')).all_text_contents(), package)
        rows = []
        with patch('services.sleeper.sleeper_get', side_effect=AssertionError('navigation must not acquire a provider')):
            for width, height in [(320,432), (375,667), (390,844), (1280,900)]:
                page.set_viewport_size({'width': width, 'height': height})
                self.round_trip(helper, page, requests, '/trades/recommended', touch=width==375)
                after = helper.draft(page)
                self.assertEqual(after['currentProposal'], original)
                self.assertEqual(after['strategy'], 'REBUILD')
                self.assertEqual(after['valuationMode'], initial['valuationMode'])
                self.assertTrue(after['navigationView']['includePicks'])
                self.assertEqual(after['navigationView']['typeFilter'], 'all')
                self.assertEqual(page.locator('#trade-result .tw-offer').first.locator(':scope > p').filter(has_text=re.compile(r'^You (send|receive):')).all_text_contents(), package)
                proposal = after['previewProposal']
                exact = {k:proposal[k] for k in ('partner_roster_id','assets_sent','assets_received')}
                expected = expected or exact
                self.assertEqual(exact, expected)
                self.assertIn('not revalidated', page.locator('#trade-result').inner_text().lower())
                rows.append({'viewport':[width,height], 'preview':exact, 'draft':after['currentProposal'], 'post_requests':[r for r in requests if r[0]=='POST']})
        self.assertFalse(errors, errors)
        self.record('recommendation-round-trip', rows)

    def test_league_switch_reauthorizes_and_discards_stale_return(self):
        helper, f = self.fixture()
        pw = self.enterContext(sync_playwright())
        browser = launch_chromium(pw, headless=True)
        self.addCleanup(browser.close)
        page, _, _, _, errors = helper.page(browser, f)
        helper.ready(page)
        helper.choose(page)
        page.locator('#trade-run').click()
        page.locator('#trade-result .tw-partner-history').click()
        page.wait_for_url('**/history/team/**')
        f.editor.store.upsert_membership('account-a', {'league_id':'league-2', 'name':'Other'}, 'account-a', 1, 'Other', 'active')
        f.editor.store.activate('account-a', 'league-2')
        f.editor.data['league']['league_id'] = 'league-2'
        page.locator('#dtos-back').click()
        page.wait_for_url(helper.origin + '/')
        self.assertEqual(page.locator('#trade-builder').count(), 0)
        self.assertEqual(f.editor.client.get('/history/team/league-1:franchise:2').status_code, 404)
        self.assertFalse(errors, errors)
