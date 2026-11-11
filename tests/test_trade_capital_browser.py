"""Prepared evaluator -> recorded inventory -> phone comparison, without reads on expand."""
from copy import deepcopy
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_offer_comparison_browser as comparison_fixture


class CapitalBrowserTests(unittest.TestCase):
    def test_actual_offers_two_alternatives_reload_and_scope_at_four_sizes(self):
        for superflex in (False, True):
            with self.subTest(superflex=superflex):
                control = comparison_fixture.OfferComparisonBrowserTests()
                self.addCleanup(control.doCleanups)
                source, helper, f = control.fixture(superflex)
                data = f.editor.data
                owners = {(int(p.get('year', p.get('season'))), int(p['round']), int(p['original_roster_id'])): int(t['roster_id'])
                          for t in data['teams'] for p in t.get('picks_owned', [])}
                for original in sorted({k[2] for k in owners} - {int(t['roster_id']) for t in data['teams']}):
                    data['teams'].append(dict(roster_id=original, team_name=f'Original {original}', players=[], picks_owned=[]))
                years = sorted({k[0] for k in owners})
                roster_ids = sorted(int(t['roster_id']) for t in data['teams'])
                data['league'].setdefault('settings', {})['draft_rounds'] = 4
                data['league']['season'] = '2026'
                ledger = [dict(season=y, round=r, original_roster_id=o, current_owner_id=owners.get((y, r, o), o))
                          for y in years for r in range(1, 5) for o in roster_ids]
                data['pick_ledger'] = ledger
                data['traded_picks'] = [dict(season=str(p['season']), round=p['round'], roster_id=p['original_roster_id'], owner_id=p['current_owner_id'])
                                        for p in ledger if p['original_roster_id'] != p['current_owner_id']]
                for t in data['teams']:
                    t['picks_owned'] = [p for p in ledger if p['current_owner_id'] == t['roster_id']]
                source.publish(f)
                saved = deepcopy(f.editor.state())
                with sync_playwright() as pw:
                    browser = launch_chromium(pw, headless=True)
                    try:
                        page, requests, _, _, errors = helper.page(browser, f)
                        helper.ready(page)
                        control.evaluate(page, helper, 'd', with_pick=True)
                        box = page.locator('#trade-result .tw-draft-capital').first
                        self.assertIn('Your draft capital after this trade', box.inner_text())
                        self.assertIn('own firsts', box.inner_text())
                        box.locator('summary').first.press('Enter')
                        self.assertIn('2028-R1-3', box.inner_text())
                        self.assertIn('2028-R1-1', box.inner_text())
                        page.locator('#trade-result > .tw-compare-add').click()
                        control.evaluate(page, helper, 'c')
                        page.locator('#trade-result > .tw-compare-add').click()
                        control.open_readonly(page, requests)
                        self.assertEqual(page.locator('#trade-comparison .tw-draft-capital').count(), 3)
                        before = [r for r in requests if r[0] == 'POST']
                        for width, height in [(320,432),(375,667),(390,844),(1280,900)]:
                            page.set_viewport_size(dict(width=width, height=height))
                            page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            self.assertIn('other firsts', page.locator('#trade-comparison').inner_text())
                            control.record('draft-capital-' + str(superflex) + '-' + str(width), dict(
                                complete_recorded_inventories=3, four_viewports=True, exact_originals=[1,3],
                                no_comparison_http=True, capital_records=[x['context']['draft_capital_record'] for x in helper.draft(page)['comparisonOffers']]), page)
                        page.locator('#trade-comparison button', has_text='Return to my offer or draft').click()
                        page.reload(); helper.ready(page); control.open_readonly(page, requests)
                        self.assertIn('NOT REVALIDATED', page.locator('#trade-comparison').inner_text())
                        self.assertEqual([r for r in requests if r[0] == 'POST'], before)
                        # Ownership changes cannot replace either original offer's inventory.
                        recorded = [x['context']['draft_capital_record'] for x in helper.draft(page)['comparisonOffers']]
                        changed = next(p for p in ledger if p['original_roster_id'] == 1 and p['round'] == 2)
                        changed['current_owner_id'] = 2
                        data['traded_picks'].append(dict(season=str(changed['season']), round=2, roster_id=1, owner_id=2))
                        for t in data['teams']:
                            t['picks_owned'] = [p for p in ledger if p['current_owner_id'] == t['roster_id']]
                        source.publish(f)
                        page.reload(); helper.ready(page); control.open_readonly(page, requests)
                        self.assertEqual([x['context']['draft_capital_record'] for x in helper.draft(page)['comparisonOffers']], recorded)
                        self.assertEqual(page.locator('#trade-comparison').get_attribute('data-comparison-state'), 'stale')
                        self.assertEqual(page.locator('#trade-comparison .tw-draft-capital').count(), 3)
                        self.assertIn('NOT REVALIDATED', page.locator('#trade-comparison').inner_text())
                        self.assertEqual(f.editor.state(), saved)
                        # A different league discards all contextual comparison state.
                        f.editor.store.upsert_membership('account-a', {'league_id':'league-2','name':'Other'}, 'account-a', 1, 'Other', 'active')
                        f.editor.store.activate('account-a','league-2'); data['league']['league_id'] = 'league-2'
                        helper.ready(page)
                        self.assertTrue(page.locator('#trade-comparison-tray').is_hidden())
                        self.assertEqual(helper.draft(page)['comparisonOffers'], [])
                        self.assertEqual([r for r in requests if r[0] == 'POST'], before)
                        self.assertFalse(errors, errors)
                        # Original-league Market evidence must not cross into the new league.
                        self.assertEqual(f.editor.client.get('/api/my-dtos').status_code, 409)
                    finally:
                        browser.close()

    def test_partial_truncated_and_cross_league_records_render_unknown(self):
        from tests.test_trade_capital_inventory import fixture, record
        data = fixture(); data.pop('traded_picks')
        partial = record(data)
        complete = record(fixture())
        from pathlib import Path
        script = Path('static/js/trade_comparison.js').read_text()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page(viewport=dict(width=320, height=432))
                page.set_content('<main></main>'); page.add_script_tag(content=script)
                for row, scope in [(partial, dict(league='league', roster=1)), (complete, dict(league='other', roster=1)),
                                   (dict(complete, characters=complete['characters']+1), dict(league='league', roster=1))]:
                    text = page.evaluate('''([record, scope]) => { const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
                      const view=window.DTOSOfferComparison.capitalView(record,node,scope,true);document.querySelector('main').replaceChildren(view);return view.textContent;}''', [row, scope])
                    self.assertIn('unknown', text)
                    self.assertNotIn('own firsts', text)
            finally:
                browser.close()
