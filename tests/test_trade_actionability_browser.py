"""Real authenticated HTTP and released JS, using disposable prepared evidence."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from services.trade_intelligence import evaluate_trade_request
from tests import test_trade_workflow_experience as workflows
from tools.validation.browser_runtime import launch_chromium


class TradeActionabilityBrowserTests(unittest.TestCase):
    def fixture(self):
        h = workflows.TradeWorkflowExperienceTests()
        f = h.fixture()
        self.addCleanup(h.doCleanups)
        return h, f

    def test_qualified_offer_preview_evaluate_and_return_at_four_widths(self):
        h, f = self.fixture()
        evidence = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                    with self.subTest(width=width):
                        page, records, _, errors, _ = h.page(browser, f, width, height)
                        h.ready(page)
                        self.assertEqual(records, [])  # navigation is not discovery
                        page.select_option('#trade-strategy', 'REBUILD')
                        page.locator('#trade-find').click()
                        h.complete(page)
                        body = records[-1]['body']
                        self.assertTrue(body['results'])
                        row = next(r for r in body['results'] if r['evaluation']['generated_trade_eligible'])
                        e, proposal = row['evaluation'], row['proposal']
                        again = evaluate_trade_request(f.f.data, {**proposal, 'strategy': 'REBUILD'}, projection_reader=f.source.reader)['evaluation']
                        for key in ('recommendation', 'generated_trade_eligible', 'market_evidence', 'multi_horizon_impact'):
                            self.assertEqual(json.loads(json.dumps(e[key])), json.loads(json.dumps(again[key])))
                        card = page.locator('.tw-offer').first
                        d = e['decision_context']
                        self.assertIn(d['decisive_reason'], card.inner_text())
                        lead = card.locator(':scope > .tw-decision-lead')
                        for selector in ('.tw-offer-reason', '.tw-drawback', '.tw-offer-effects', '.tw-offer-market'):
                            self.assertEqual(lead.locator(':scope > ' + selector).count(), 1)
                        geometry = card.evaluate('e=>{const c=e.getBoundingClientRect(),l=e.querySelector(".tw-decision-lead").getBoundingClientRect();return {action:e.querySelector(".tw-next-action").getBoundingClientRect().top-c.top,lead:l.top-c.top,lead_bottom:l.bottom-c.top,lead_height:l.height};}')
                        self.assertLess(geometry['action'], 850)
                        self.assertLess(geometry['lead'], geometry['action'])
                        self.assertLessEqual(geometry['lead_bottom'], geometry['action'])
                        self.assertEqual(card.locator('.tw-depth-details,.tw-lineup-details,.tw-draft-capital').count(), 0)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        card.locator(':scope > .tw-next-action').click()
                        preview = page.locator('#trade-result')
                        self.assertIn(d['decisive_reason'], preview.inner_text())
                        self.assertIn(d['verdict'], preview.inner_text())
                        review = preview.locator('.tw-offer-review')
                        review.locator('.tw-offer-sources > summary').press('Enter')
                        review.locator('.tw-team-impact-details > summary').press('Enter')
                        self.assertIn(d['decision_next_step'], review.inner_text())
                        for key in ('your_side_summary', 'their_side_summary', 'decision_conditions'):
                            for line in d[key].splitlines():
                                # Presentation translates prose; exact amounts and qualifications stay intact.
                                expected = line.replace('Useful replacement production changes', 'Projected points from eligible backups change')
                                self.assertIn(expected, review.inner_text())
                        self.assertEqual(len(records), 1)
                        page.get_by_role('button', name='Back to offers', exact=True).click()
                        self.assertEqual(page.locator('#trade-strategy').input_value(), 'REBUILD')
                        self.assertEqual(len(records), 1)
                        page.locator('.tw-offer').first.locator(':scope > .tw-next-action').click()
                        page.get_by_role('button', name='Use this offer in my draft', exact=True).click()
                        self.assertIn(d['decisive_reason'], page.locator('#trade-result').inner_text())
                        page.get_by_role('button', name='Reevaluate Trade', exact=True).click()
                        page.wait_for_function("['fresh_complete','fresh_incomplete'].includes(document.querySelector('#trade-result').dataset.assessmentState)")
                        evaluated = next(r for r in reversed(records) if r['path'] == '/api/trades/evaluate')
                        self.assertEqual(evaluated['status'], 200)
                        self.assertEqual(evaluated['payload']['assets_sent'], proposal['assets_sent'])
                        self.assertEqual(evaluated['payload']['assets_received'], proposal['assets_received'])
                        self.assertEqual(evaluated['body']['evaluation']['decision_context']['verdict'], d['verdict'])
                        self.assertIn(d['decisive_reason'], page.locator('#trade-result').inner_text())
                        # Existing workspace retention, not another navigation/history system.
                        page.reload()
                        page.wait_for_function("!document.querySelector('#trade-context').textContent.includes('Loading')")
                        self.assertEqual(page.locator('#trade-strategy').input_value(), 'REBUILD')
                        self.assertIn(d['verdict'], page.locator('#trade-result').inner_text())
                        self.assertEqual(len([r for r in records if r['path'] == '/api/trades/generate']), 1)
                        self.assertEqual(errors, [])
                        evidence.append({'viewport': [width, height], 'geometry': geometry, 'proposal': proposal, 'verdict': d['verdict'], 'matched_numeric_fields': True, 'errors': errors})
                        target = os.environ.get('DTOS_TRADE_ACTIONABILITY_EVIDENCE')
                        if target:
                            Path(target).mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(Path(target, f'evaluate-{width}.png')), full_page=True)
                        page.close()
            finally:
                browser.close()
        target = os.environ.get('DTOS_TRADE_ACTIONABILITY_EVIDENCE')
        if target:
            Path(target, 'matched-journeys.json').write_text(json.dumps(evidence, indent=2) + '\n')

    def test_completed_zero_qualified_has_recorded_diagnosis_and_separate_alternatives(self):
        h, f = self.fixture()
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page, records, _, errors, _ = h.page(browser, f)
                h.ready(page)
                page.select_option('#trade-strategy', 'RETOOL')
                page.locator('#trade-find').click()
                h.complete(page)
                body = records[-1]['body']
                self.assertFalse(any(r['evaluation']['generated_trade_eligible'] for r in body['results']))
                self.assertIn('No qualified recommendations', page.locator('#trade-result').inner_text())
                self.assertIn('No bilateral recommendation', body['zero_result_guidance']['message'])
                expected = body['zero_result_guidance']['message'].replace('No bilateral recommendation', 'No recommendation for both teams')
                self.assertIn(expected, page.locator('#trade-result').inner_text())
                self.assertIn('Main limit:', body['quiet_state'])
                self.assertTrue(page.get_by_role('region', name='Other evaluated offers · not qualified').count())
                self.assertNotIn('Why now', page.locator('#trade-result').inner_text())
                self.assertNotIn('temporarily deferred', page.locator('#recommendation-status').inner_text())
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_timing_heading_requires_a_supported_matching_calendar_signal(self):
        h, f = self.fixture()
        from services.recommended_trade_search import surface_evidence
        for kind, expected in (('valid', True), ('wrong_generation', False), ('roster_fit', False), ('unavailable', False)):
            def explanatory_fixture(row):
                opportunity = surface_evidence(row)
                d = row['evaluation']['decision_context']
                weeks = d['lineup']['weeks']
                catalyst = dict(type='UPCOMING_BYE_LINEUP_FIT', side='active', horizon='current_week',
                    availability='supported', generation=d['lineup_source_generation'], weeks=weeks,
                    delta=d['lineup_weekly_comparisons']['active'][str(weeks[0])], limitation='Calendar fixture; not a live timing claim.')
                if kind == 'wrong_generation':
                    catalyst['generation'] = 'foreign'
                if kind == 'roster_fit':
                    catalyst['type'] = 'CURRENT_COMPETITIVE_WINDOW_ALIGNMENT'
                opportunity['why_now'] = dict(availability='unavailable' if kind == 'unavailable' else 'supported_current_state', catalysts=[catalyst])
                return opportunity

            with self.subTest(kind=kind), patch('services.recommended_trade_search.surface_evidence', side_effect=explanatory_fixture), sync_playwright() as pw:
                browser = launch_chromium(pw, headless=True)
                try:
                    page, _, _, errors, _ = h.page(browser, f)
                    h.ready(page)
                    page.select_option('#trade-strategy', 'REBUILD')
                    page.locator('#trade-find').click()
                    h.complete(page)
                    page.locator('.tw-offer').first.locator(':scope > .tw-next-action').click()
                    page.get_by_role('button', name='Use this offer in my draft', exact=True).click()
                    # Adopted evidence is deliberately retained, never current.
                    text = page.locator('#trade-result').inner_text()
                    self.assertEqual('Timing context at assessment · not revalidated' in text, expected)
                    self.assertNotIn('Why now · supported context', text)
                    self.assertEqual(errors, [])
                finally:
                    browser.close()
