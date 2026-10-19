"""Actual authenticated Trade evaluation and released client in Chromium.

Projection/Market amounts are disposable controlled observations. Day Traders
and Arkham IDs exercise isolated league contexts, not their current live rosters.
This is author-run responsive Chromium, not physical iPhone/Safari acceptance.
"""

import json
import os
from pathlib import Path
from time import perf_counter
import unittest
from unittest.mock import patch

from src.core.intelligence.team_strength import prepare_for_data
from src.ui.intelligence_presentation import manager_points
from tests import test_trade_decision_http_browser as decision


class ReserveQualityBrowserTests(unittest.TestCase):
    def setUp(self):
        self.f = decision.DecisionHTTPBrowserTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.geometry = []
        names = {'b': 'Supported Reserve Quarterback', 'd': 'Incoming Depth Quarterback'}
        for team in self.f.data['teams']:
            for player in team['players']:
                if player['id'] in names:
                    player['name'] = names[player['id']]
                    self.f.data['players'][player['id']]['full_name'] = player['name']

    def tearDown(self):
        target = os.environ.get('DTOS_RESERVE_BROWSER_EVIDENCE')
        if target:
            path = Path(target)
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps(rows + self.geometry, indent=2))

    def prepare(self, league_id, *, consolidation=False, scoring=1):
        self.f.data['league'].update(league_id=league_id,
                                    scoring_settings={'pass_yd': scoring})
        self.f.auth.store.upsert_membership(self.f.auth.account_id,
            {'league_id': league_id, 'season': '2026', 'name': 'Controlled reserve fixture'},
            'fixture-user', 1, 'Controlled franchise', 'active')
        self.f.auth.store.activate(self.f.auth.account_id, league_id)
        self.f.f.points.update(a=20 if consolidation else 50,
                               b=14 if consolidation else 40,
                               e=13 if consolidation else 0,
                               c=28 if consolidation else 60,
                               d=3 if consolidation else 1,
                               f=4 if consolidation else 0)
        self.f.f.prices(**({'a': 125, 'b': 125, 'c': 250} if consolidation else {}))
        payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week,
                           'stats': {'pass_yd': points}, 'player': {'position': 'QB'}}
                          for pid, points in self.f.f.points.items()]
                    for week in (2, 3, 4, 5)}
        self.f.f.reader.publish_horizon(payloads, data=self.f.data, league_id=league_id,
                                       season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.f.f.reader, self.f.data)

    def evaluate(self, page, sent=('b',), received=('d',), strategy='REBUILD'):
        self.f.ready(page)
        page.select_option('#trade-partner', '2')
        page.select_option('#trade-strategy', strategy)
        for pid in sent:
            self.f.select(page, 'sent', pid)
        for pid in received:
            self.f.select(page, 'received', pid)
        page.get_by_role('button', name='Evaluate Trade', exact=True).click()
        page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_complete'")
        return self.f.responses[-1]['evaluation']

    def test_same_count_quality_loss_in_actual_http_and_phone_disclosure(self):
        for league, scoring in (('1313066632158924800', 1),
                                ('1319750579458686976', 2)):
            self.prepare(league, scoring=scoring)
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                with self.subTest(league=league, width=width), self.f.browser(width, height) as page:
                    e = self.evaluate(page)
                    quality = e['dimensions']['package_quality']['active']
                    self.assertEqual(set(quality['reserve_slot_changes'].values()), {0})
                    self.assertEqual(quality['reserve_quality']['mean_weekly_delta'], -39 * scoring)
                    self.assertEqual(e['lineup_impact']['active']['delta'], 0)
                    self.assertEqual(e['provenance']['inputs']['league_id'], league)
                    primary = page.locator('#trade-result .tw-decision')
                    primary_text = primary.inner_text()
                    self.assertNotIn('No material downside identified', primary_text)
                    self.assertIn('legal-replacement production falls', primary_text)
                    self.assertIn(f'{39 * scoring:.2f}', primary_text)
                    self.assertIn('starters are unchanged', primary_text)
                    sent = page.locator('#trade-sent-chips button[data-asset-id="b"]')
                    received = page.locator('#trade-received-chips button[data-asset-id="d"]')
                    self.assertIn('Supported Reserve Quarterback', sent.inner_text())
                    self.assertIn('Incoming Depth Quarterback', received.inner_text())
                    self.assertIn('you send', sent.get_attribute('aria-label'))
                    self.assertIn('you receive', received.get_attribute('aria-label'))
                    full = page.locator('#trade-result .tw-evaluation-detail')
                    self.assertIsNone(full.get_attribute('open'))
                    supporting = full.get_by_text('Supporting evidence and limitations', exact=True).locator('..')
                    self.assertIsNone(supporting.get_attribute('open'))
                    saved = page.evaluate('JSON.stringify(sessionStorage)')
                    requests = len(self.f.measurements)
                    collapsed = page.locator('#trade-result').bounding_box()['height']
                    start = perf_counter()
                    summary = full.locator(':scope > summary')
                    summary.focus()
                    page.keyboard.press('Enter')
                    self.assertTrue(summary.evaluate('e=>e===document.activeElement'))
                    evidence_summary = supporting.locator(':scope > summary')
                    evidence_summary.focus()
                    evidence_summary.press('Enter')
                    evidence = supporting.inner_text()
                    for week in (2, 3, 4, 5):
                        self.assertIn(f'Your team · Week {week} · Legal reserve production before trade: {manager_points(40 * scoring)} ', evidence)
                        self.assertIn(f'Your team · Week {week} · Legal reserve production after trade: {manager_points(scoring)} ', evidence)
                        self.assertIn(f'Your team · Week {week} · Legal reserve production change: {manager_points(-39 * scoring)} ', evidence)
                    self.assertIn('provisional', evidence.lower())
                    expanded = page.locator('#trade-result').bounding_box()['height']
                    expand_ms = round((perf_counter() - start) * 1000, 3)
                    for _ in range(2):
                        evidence_summary.click()
                        evidence_summary.click()
                    self.assertEqual(page.evaluate('JSON.stringify(sessionStorage)'), saved)
                    self.assertEqual(len(self.f.measurements), requests)
                    document_width = page.evaluate('document.documentElement.scrollWidth')
                    self.assertLessEqual(document_width, width)
                    self.geometry.append({'case': 'same-count-reserve-loss', 'league': league,
                        'controlled_scoring': {'pass_yd': scoring}, 'viewport': [width, height],
                        'document_width': document_width, 'primary_height': round(primary.bounding_box()['height'], 2),
                        'collapsed_result_height': round(collapsed, 2), 'expanded_result_height': round(expanded, 2),
                        'expand_ms': expand_ms, 'primary_text': primary_text,
                        'reserve_before': 40 * scoring, 'reserve_after': scoring,
                        'reserve_delta': -39 * scoring, 'reserve_slot_change': 0,
                        'initial_disclosures_closed': True, 'keyboard_and_pointer': True,
                        'expansion_requests': len(self.f.measurements) - requests,
                        'expansion_saved_state_unchanged': True,
                        'author_run_environment': 'isolated authenticated HTTP and responsive Chromium'})

    def test_supported_consolidation_stays_favorable_and_discloses_depth_cost(self):
        self.prepare('1313066632158924800', consolidation=True)
        with self.f.browser(320, 432) as page:
            e = self.evaluate(page, sent=('a', 'b'), received=('c',), strategy='WIN NOW')
            self.assertEqual(e['recommendation'], 'WORTH PURSUING')
            self.assertEqual(e['lineup_impact']['active']['delta'], 8)
            self.assertEqual(e['dimensions']['package_quality']['active']['assessment'], 'SUPPORTED CONSOLIDATION')
            self.assertEqual(e['dimensions']['package_quality']['active']['reserve_quality']['mean_weekly_delta'], -1)
            text = page.locator('#trade-result .tw-decision').inner_text()
            self.assertIn('1.00', text)
            self.assertIn('legal-replacement production falls', text)
            self.assertIn('WORTH PURSUING', page.locator('#trade-result .dtos-explanation > p').first.inner_text())
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 320)

    def test_retained_assessment_preserves_original_partner_and_reserve_evidence(self):
        # The original accepted actual evaluator fixture has a -7.70 partner
        # starter cost and 27.70 -> 20.00 absolute points. New reserve detail
        # must share the existing bounded assessment without displacing either.
        with self.f.browser(320, 432) as page:
            old = self.evaluate(page, sent=('a', '2029-R1-1'), received=('c',),
                                strategy='WIN NOW')
            horizon = old['dimensions']['strategic_fit']['partner']['horizons']['current_week']
            self.assertEqual((horizon['pre_total'], horizon['post_total']), (27.7, 20))
            self.assertEqual(horizon['delta'], -7.7)
            self.f.data['market_data'] = {}
            page.locator('#trade-run').click()
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_incomplete'")
            for navigation in ('initial', 'reload', 'back'):
                if navigation == 'reload':
                    page.reload(wait_until='load')
                elif navigation == 'back':
                    page.goto('https://dtos.test/trades?front_office=1', wait_until='load')
                    page.go_back(wait_until='load')
                page.wait_for_function("document.querySelector('#trade-context')?.textContent.includes('Active league')")
                prior = page.locator('#trade-result > details').filter(has=page.get_by_text(
                    'Previous assessment · NOT REVALIDATED', exact=True))
                self.assertEqual(prior.count(), 1)
                self.assertIsNone(prior.get_attribute('open'))
                state = next(iter(self.f.state(page).values()))['currentAssessment']
                saved_prior = state['previous_assessment']
                saved = json.dumps(saved_prior, sort_keys=True)
                self.assertLess(len(saved.encode()), 64000)
                requests = len(self.f.measurements)
                prior.locator(':scope > summary').focus()
                page.keyboard.press('Enter')
                text = prior.inner_text()
                self.assertIn('-7.70', text)
                self.assertIn('27.70 → 20.00', text)
                self.assertIn(old['why_they_would_do_it'], text)
                self.assertIn(old['counterparty_summary'], text)
                self.assertIn('WIN NOW', text)
                self.assertIn('2029 Round 1', text)
                self.assertIn('not current', text.lower())
                for limitation in old['major_limitations']:
                    self.assertIn(limitation.replace('_', ' '), text)
                for side, title in (('active', 'Your team'), ('partner', 'Their team')):
                    detail = prior.get_by_text(title + ' strategic evidence', exact=True).locator('..')
                    detail.locator(':scope > summary').click()
                    reserve_text = detail.inner_text()
                    self.assertIn('Previous useful replacement production · NOT REVALIDATED', reserve_text)
                    weeks = old['dimensions']['package_quality'][side]['reserve_quality_by_week']
                    for week, row in weeks.items():
                        self.assertIn(f"Week {week}: {row['pre_points']:.2f} → {row['post_points']:.2f} projected reserve points", reserve_text)
                        self.assertIn(f"change {row['delta']:.2f}", reserve_text)
                    self.assertIn('Conditional replacement projection', reserve_text)
                    self.assertIn('does not predict injuries', reserve_text)
                self.assertEqual(json.dumps(next(iter(self.f.state(page).values()))[
                    'currentAssessment']['previous_assessment'], sort_keys=True), saved)
                self.assertEqual(len(self.f.measurements), requests)
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 320)
                self.geometry.append({'case': 'retained-original-and-reserve-evidence',
                    'navigation': navigation, 'viewport': [320, 432],
                    'original_partner_change': -7.7, 'original_partner_points': [27.7, 20],
                    'saved_prior_bytes': len(saved.encode()), 'saved_prior_unchanged': True,
                    'expansion_requests': len(self.f.measurements) - requests,
                    'original_and_new_evidence_accessible': True,
                    'author_run_environment': 'isolated authenticated HTTP and responsive Chromium'})


if __name__ == '__main__':
    unittest.main()
