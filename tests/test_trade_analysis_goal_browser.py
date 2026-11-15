"""Actual guarded search → temporary goal choice; no saved-goal write."""
import json
import os
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright
from tests import test_00_trade_workflow_experience as workflow
from tools.validation.browser_runtime import launch_chromium


class TradeAnalysisGoalBrowserTests(unittest.TestCase):
    def test_completed_no_goal_search_offers_explicit_temporary_choice(self):
        h = workflow.TradeWorkflowExperienceTests()
        f = h.fixture()
        self.addCleanup(h.doCleanups)
        f.f.data['teams'][0].pop('strategy', None)
        f.f.client.cookies.delete('dtos_strategy')
        observations = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
                    with self.subTest(width=width):
                        page, records, _, errors, _ = h.page(browser, f, width, height)
                        try:
                            h.ready(page)
                            page.select_option('#trade-strategy', '')
                            self.assertEqual(records, [])
                            page.locator('#trade-find').click()
                            h.complete(page)
                            body = records[-1]['body']
                            self.assertEqual(records[-1]['status'], 200)
                            self.assertFalse(any(r['evaluation']['generated_trade_eligible'] for r in body['results']))
                            goal = body['zero_result_guidance']['analysis_goal']
                            self.assertGreater(goal['assessments'], 0)
                            self.assertTrue(goal['temporary_only'])
                            result = page.locator('#trade-result')
                            self.assertIn('No qualified recommendations', result.inner_text())
                            self.assertIn('temporary analysis goal', result.inner_text())
                            self.assertIn('cannot choose this goal', result.inner_text())
                            choice = page.get_by_role('button', name='Choose temporary analysis goal', exact=True)
                            before = len(records)
                            choice.press('Enter')
                            self.assertTrue(page.locator('#trade-strategy').evaluate('e=>e===document.activeElement'))
                            self.assertEqual(page.locator('#trade-strategy').input_value(), '')
                            self.assertEqual(len(records), before)
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            target = os.environ.get('DTOS_TRADE_GOAL_EVIDENCE')
                            if target:
                                directory = Path(target)
                                directory.mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(directory / f'goal-choice-{width}.png'), full_page=True)
                            page.select_option('#trade-strategy', 'REBUILD')
                            self.assertEqual(len(records), before)
                            self.assertNotIn('strategy', f.f.data['teams'][0])
                            self.assertIsNone(f.f.client.cookies.get('dtos_strategy'))
                            page.locator('#trade-find').click()
                            h.complete(page)
                            self.assertEqual(records[-1]['payload']['strategy'], 'REBUILD')
                            self.assertEqual(len([r for r in records if r['path'] == '/api/trades/generate']), 2)
                            self.assertFalse(records[-1]['body']['zero_result_guidance'] and records[-1]['body']['zero_result_guidance']['analysis_goal']['selection_required'])
                            self.assertFalse(errors, errors)
                            observations.append(dict(width=width, completed_no_goal=True,
                                strategy_assessments=goal['assessments'], real_gap_overlap=goal['also_missing_evidence'],
                                no_automatic_search=True, explicit_goal='REBUILD', saved_goal_unchanged=True,
                                no_qualification_inferred=True, browser='Chromium emulation'))
                        finally:
                            page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_TRADE_GOAL_EVIDENCE'):
            Path(os.environ['DTOS_TRADE_GOAL_EVIDENCE'], 'observations.json').write_text(json.dumps(observations, indent=2) + '\n')
