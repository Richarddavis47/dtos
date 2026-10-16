"""Actual canonical HTTP and released-client controls for retained evidence/display."""
import json
import os
from pathlib import Path
import unittest
from decimal import Decimal
import hashlib
import sqlite3
from time import perf_counter

from tests import test_trade_decision_http_browser as decision
from tests import test_trade_calculator_browser as calculator
from src.ui.intelligence_presentation import manager_points
from services.trade_explanation import _decision_primary


class TradeFinalEvidenceBrowserTests(unittest.TestCase):
    def setUp(self):
        self.f = decision.DecisionHTTPBrowserTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.geometry = []

    def tearDown(self):
        target = os.environ.get("DTOS_TRADE_FINAL_EVIDENCE")
        if target:
            path = Path(target)
            rows = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps(rows + self.geometry, indent=2))

    def build(self, page):
        self.f.ready(page)
        page.select_option("#trade-partner", "2")
        page.select_option("#trade-strategy", "WIN NOW")
        self.f.select(page, "sent", "a")
        self.f.select(page, "sent", "2029-R1-1")
        self.f.select(page, "received", "c")

    def current(self, page):
        return next(iter(self.f.state(page).values()))["currentAssessment"]

    def previous(self, page):
        return page.locator("#trade-result > details").filter(
            has=page.get_by_text("Previous assessment · NOT REVALIDATED", exact=True)
        )

    def durable_state(self):
        files, tables = {}, {}
        for label, folder in [("projection", self.f.f.tmp.name), ("account", self.f.auth.folder.name)]:
            for path in sorted(Path(folder).rglob('*')):
                if not path.is_file():
                    continue
                key = label + '/' + str(path.relative_to(folder))
                files[key] = hashlib.sha256(path.read_bytes()).hexdigest()
                if path.suffix == '.sqlite3':
                    with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
                        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                        tables[key] = {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in names}
        return {'files': files, 'tables': tables}

    def complete_then_incomplete(self, page):
        self.build(page)
        page.click("#trade-run")
        page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_complete'")
        old = self.current(page)
        self.assertEqual(len(old["evaluation"]["major_limitations"]), 6)
        self.f.data["market_data"] = {}
        page.click("#trade-run")
        page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_incomplete'")
        return old

    def test_complete_prior_evidence_accessible_without_storage_or_request_growth(self):
        for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
            with self.subTest(width=width), self.f.browser(width, height) as page:
                # Each viewport has independent canonical data and a real completed prior.
                if width != 320:
                    self.f.data["market_data"] = self.market
                self.market = self.f.data["market_data"]
                old = self.complete_then_incomplete(page)
                detail = self.previous(page)
                self.assertEqual(detail.count(), 1)
                self.assertIsNone(detail.get_attribute("open"))
                self.assertEqual(page.locator("#trade-result").get_attribute("data-assessment-freshness"), "current")
                saved = page.evaluate("JSON.stringify(sessionStorage)")
                requests = len(self.f.requests)
                reads = len(self.f.measurements)
                durable = self.durable_state()
                summary = detail.locator(":scope > summary")
                closed_height = detail.bounding_box()['height']
                primary_height = page.locator('#trade-result').bounding_box()['height']
                start = perf_counter()
                summary.focus()
                page.keyboard.press("Enter")
                expanded_height = detail.bounding_box()['height']
                expand_ms = round((perf_counter() - start) * 1000, 3)
                text = detail.inner_text()
                # These are facts from the actual saved canonical evaluator response.
                self.assertIn(old["evaluation"]["why_they_would_do_it"], text)
                self.assertIn(old["evaluation"]["counterparty_summary"], text)
                for limitation in old["evaluation"]["major_limitations"]:
                    self.assertIn(limitation.replace("_", " "), text)
                self.assertIn("-7.70", text)
                self.assertIn("provisional", text.lower())
                # Read the existing saved diagnostic; do not recalculate or save
                # another assessment just to disclose its absolute lineup cost.
                horizon = old["evaluation"]["dimensions"]["strategic_fit"]["partner"]["horizons"]["current_week"]
                self.assertEqual((horizon["pre_total"], horizon["post_total"]), (27.7, 20))
                self.assertIn("27.70 → 20.00", text)
                self.assertIn("WIN NOW", text)
                self.assertIn("945", text)
                self.assertIn("929", text)
                self.assertIn("not current", text.lower())
                self.assertTrue(summary.evaluate("e=>e===document.activeElement"))
                self.geometry.append({"case": "complete-prior", "width": width, "height": height,
                                      "expanded_height": expanded_height, "expand_ms": expand_ms,
                                      "closed_height": closed_height, "primary_height": primary_height,
                                      "current_text": page.locator("#trade-result > .tw-assessment-status").inner_text(),
                                      "prior_text": text, "stored_prior_bytes": len(json.dumps(self.current(page)["previous_assessment"]))})
                for _ in range(3):
                    summary.click()
                    summary.click()
                self.assertEqual(page.evaluate("JSON.stringify(sessionStorage)"), saved)
                self.assertEqual(len(self.f.requests), requests)
                self.assertEqual(len(self.f.measurements), reads)
                self.assertEqual(self.durable_state(), durable)
                self.geometry[-1]['durable_files_and_tables'] = durable
                self.geometry[-1]['durable_state_unchanged'] = True
                self.geometry[-1]['storage_bytes_unchanged'] = True
                self.geometry[-1]['no_new_http_requests'] = True
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)

    def test_complete_previous_survives_reload_history_then_current_success_clears_it(self):
        with self.f.browser() as page:
            market = self.f.data['market_data']
            old = self.complete_then_incomplete(page)
            for action in ('reload', 'history'):
                if action == 'reload':
                    page.reload(wait_until='load')
                else:
                    page.goto('https://dtos.test/trades?front_office=1', wait_until='load')
                    page.go_back(wait_until='load')
                page.wait_for_function("document.querySelector('#trade-context')?.textContent.includes('Active league')")
                detail = self.previous(page)
                self.assertIsNone(detail.get_attribute('open'))
                detail.locator(':scope > summary').click()
                self.assertIn(old['evaluation']['why_they_would_do_it'], detail.inner_text())
                self.assertIn('-7.70', detail.inner_text())
                self.assertIn('2029 Round 1', detail.inner_text())
                self.assertEqual(self.current(page)['previous_assessment']['identity']['strategy'], 'WIN NOW')
            self.f.data['market_data'] = market
            page.get_by_role('button', name='Reevaluate Trade', exact=True).click()
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_complete'")
            self.assertEqual(self.previous(page).count(), 0)

    def test_actual_canonical_balance_http_strings_preview_keep_and_adopt(self):
        with self.f.browser() as page:
            self.f.ready(page)
            page.select_option('#trade-partner', '2')
            page.select_option('#trade-strategy', 'WIN NOW')
            self.f.select(page, 'sent', 'a')
            self.f.select(page, 'received', 'c')
            page.click('#trade-balance-offer')
            page.get_by_role('button', name='Preview adjustment', exact=True).first.wait_for()
            response = self.f.responses[-1]
            self.assertTrue(response['results'])
            first = response['results'][0]
            shown = first['balance_adjustment']['display']['suggested']
            raw = first['balance_adjustment']['suggested']
            self.assertEqual(shown['sent'], manager_points(raw['sent']['total']))
            self.assertEqual(shown['gap'], manager_points(raw['absolute_gap']))
            self.assertTrue(all('c' in row['proposal']['assets_received'] for row in response['results']))
            original = next(iter(self.f.state(page).values()))['currentProposal']
            page.get_by_role('button', name='Preview adjustment', exact=True).first.click()
            compare = page.get_by_text('Compare with original proposal', exact=True).locator('..')
            compare.locator(':scope > summary').click()
            self.assertIn(f"Suggested Market: {shown['sent']} sent / {shown['received']} received · Gap {shown['gap']}", compare.inner_text())
            page.get_by_role('button', name='Keep original', exact=True).click()
            self.assertEqual(next(iter(self.f.state(page).values()))['currentProposal'], original)
            page.get_by_role('button', name='Preview adjustment', exact=True).first.click()
            page.get_by_role('button', name='Adopt alternative', exact=True).click()
            self.assertEqual(page.locator('#trade-result').get_attribute('data-assessment-state'), 'retained')
            adopted = next(iter(self.f.state(page).values()))['currentProposal']
            self.assertEqual(adopted['sent'], first['proposal']['assets_sent'])
            self.assertEqual(adopted['received'], first['proposal']['assets_received'])

    def test_no_previous_and_current_recovery_keep_existing_state_contract(self):
        with self.f.browser() as page:
            self.build(page)
            saved = self.f.data["market_data"]
            self.f.data["market_data"] = {}
            page.click("#trade-run")
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_incomplete'")
            self.assertEqual(self.previous(page).count(), 0)
            self.f.data["market_data"] = saved
            page.get_by_role("button", name="Reevaluate Trade", exact=True).click()
            page.wait_for_function("document.querySelector('#trade-result').dataset.assessmentState==='fresh_complete'")
            self.assertEqual(self.previous(page).count(), 0)


class TradeMarketDisplayBrowserTests(unittest.TestCase):
    def setUp(self):
        self.f = calculator.CalculatorBrowserTests()
        self.f.setUp()

    def test_completed_market_panel_matches_canonical_strings_without_changing_evidence(self):
        decision = {'lineup': {'explanation': 'Controlled display context.'},
                    'summary': 'Market is separate from strategic fit.', 'main_cost': 'Fixture cost.', 'limitation': None,
                    'next_action': 'Review this controlled fixture.'}
        for sent, received in [(620.125, 600), (600, 620.125), (620.135, 600), (0, 0), (-0.0, 0)]:
            market = {'availability': 'full', 'sent': {'total': sent}, 'received': {'total': received},
                      'difference': float(Decimal(str(received)) - Decimal(str(sent)))}
            original = json.dumps(market, sort_keys=True)
            html = _decision_primary({'market_evidence': market}, decision)
            self.assertIn('You send <b>' + manager_points(sent) + '</b>', html)
            self.assertIn('You receive <b>' + manager_points(received) + '</b>', html)
            if sent != received:
                gap = abs(market['difference'])
                self.assertIn(manager_points(gap) + ' more current Market value', html)
                self.assertIn('Your counterparty receives' if sent > received else 'You receive', html)
            self.assertEqual(json.dumps(market, sort_keys=True), original)
        market = {'availability': 'partial', 'sent': {'total': None, 'known_subtotal': 0}, 'received': {'total': 620.125, 'known_subtotal': 620.125}, 'difference': None}
        html = _decision_primary({'market_evidence': market}, decision)
        self.assertIn('Incomplete · known 0', html)
        self.assertIn('Incomplete · known 620.12', html)
        self.assertNotIn('more current Market value', html)

    def test_fractional_balance_preview_and_workspace_use_same_canonical_display(self):
        # Controlled compatible canonical DTO values; not production prices.
        for price, width, height in [(620.125, 320, 432), (620.125, 375, 667), (620.125, 390, 844),
                                     (620.125, 1280, 900), (620.135, 320, 432), (620.145, 375, 667), (620.115, 390, 844)]:
            original = float(Decimal(str(price)) - Decimal('200'))
            gap = float(Decimal(str(price)) - Decimal('600'))
            original_gap = float(Decimal('600') - Decimal(str(original)))
            data = self.f.fixture.workspace()
            data["calculator_generation"] = "canonical-fixture"
            data["teams"][0]["assets"][0]["trade_value"] = original
            data["teams"][1]["assets"][0]["trade_value"] = 600

            def response(route, payload):
                offer = self.f.fixture.offer(["player:a", "pick:2028:1:3"], ["player:x"])
                offer["balance_adjustment"] = {
                    "market_generation": "canonical-fixture", "change": "ADD_PICK",
                    "original": {"sent": {"total": original}, "received": {"total": 600}, "absolute_gap": original_gap},
                    "suggested": {"sent": {"total": price}, "received": {"total": 600}, "absolute_gap": gap},
                    "display": {"original": {"sent": manager_points(original), "received": "600", "gap": manager_points(original_gap)},
                                "suggested": {"sent": manager_points(price), "received": "600", "gap": manager_points(gap)}},
                    "reason": "Owned exact-pick adjustment.", "meaning": "Market comparison, not a recommendation."}
                route.fulfill(json={"results": [offer], "count": 1})

            with self.subTest(price=price, width=width), self.f.fixture.page(width=width, api=response, workspace=data) as (page, _):
                page.set_viewport_size({'width': width, 'height': height})
                self.f.build(page)
                page.click("#trade-balance-offer")
                card = page.locator(".tw-balance-offer").first
                expected = f"You send {manager_points(price)} / You receive 600. Difference: {manager_points(gap)}"
                self.assertIn(expected, card.locator(".tw-offer-market").inner_text())
                page.get_by_role("button", name="Preview adjustment", exact=True).first.click()
                compare = page.get_by_text("Compare with original proposal", exact=True).locator("..")
                compare.locator(":scope > summary").click()
                self.assertIn(f"Suggested Market: {manager_points(price)} sent / 600 received · Gap {manager_points(gap)}", compare.inner_text())
                self.assertIn(f"Outgoing Market cost: {manager_points(original)} → {manager_points(price)}", compare.inner_text())
                page.get_by_role("button", name="Adopt alternative", exact=True).click()
                self.assertIn(f"You send: {manager_points(price)}", page.locator("#trade-balance").inner_text())
                self.assertIn(f"Value gap: {manager_points(gap)}", page.locator("#trade-balance").inner_text())
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)

    def test_workspace_canonical_decimal_zero_and_missing_matrix(self):
        for price in (0, -0.0, 0.005, 1.005, 1.015, 2.675, 1e-7, 1e20, None):
            data = self.f.fixture.workspace()
            data['calculator_generation'] = 'canonical-fixture'
            data['teams'][0]['assets'][0]['trade_value'] = price
            data['teams'][1]['assets'][0]['trade_value'] = 0
            with self.subTest(price=price), self.f.fixture.page(workspace=data) as (page, requests):
                self.f.build(page)
                text = page.locator('#trade-balance').inner_text()
                if price is None:
                    self.assertIn('You send: Unavailable', text)
                    self.assertIn('pricing evidence missing', text)
                    self.assertNotIn('Value gap:', text)
                else:
                    self.assertIn('You send: ' + manager_points(price), text)
                    self.assertIn('Value gap: ' + manager_points(price), text)
                    self.assertNotIn('-0', text)
                self.assertEqual(requests, [])

    def test_partial_and_incompatible_comparisons_keep_qualifications(self):
        for kind in ('partial', 'incompatible'):
            data = self.f.fixture.workspace()
            data['calculator_generation'] = 'canonical-fixture'

            def response(route, payload):
                offer = self.f.fixture.offer(['player:a', 'pick:2028:1:3'], ['player:x'])
                offer['evaluation']['recommendation'] = None
                offer['balance_adjustment'] = {
                    'market_generation': 'foreign-publication' if kind == 'incompatible' else 'canonical-fixture',
                    'original': {'sent': {'total': 400}, 'received': {'total': 600}, 'absolute_gap': 200},
                    'suggested': {'availability': 'partial', 'sent': {'total': None, 'known_subtotal': 0},
                                  'received': {'total': 600}, 'absolute_gap': None},
                    'reason': 'Incomplete prepared comparison.', 'meaning': 'No definitive Market advantage.'}
                route.fulfill(json={'results': [offer], 'count': 1})

            with self.subTest(kind=kind), self.f.fixture.page(api=response, workspace=data) as (page, _):
                self.f.build(page)
                original = self.f.state(page)['currentProposal']
                page.click('#trade-balance-offer')
                text = page.locator('.tw-offer-market').inner_text()
                self.assertIn('Unavailable', text)
                self.assertNotIn('Difference: 0.', text)
                page.get_by_role('button', name='Preview adjustment', exact=True).click()
                if kind == 'partial':
                    compare = page.get_by_text('Compare with original proposal', exact=True).locator('..')
                    compare.locator(':scope > summary').click()
                    self.assertIn('Incomplete · known subtotal 0', compare.inner_text())
                    self.assertIn('Gap Unavailable', compare.inner_text())
                    self.assertIn('Outgoing Market cost: 400 → Incomplete · known subtotal 0', compare.inner_text())
                else:
                    self.assertIn('Market evidence updated', page.locator('#trade-result').inner_text())
                self.assertEqual(self.f.state(page)['currentProposal'], original)

    def test_alternative_target_is_separate_and_keeps_the_same_display_contract(self):
        data = self.f.fixture.workspace()
        data['calculator_generation'] = 'canonical-fixture'
        data['teams'][0]['assets'][0]['trade_value'] = 420.125
        data['teams'][1]['assets'][1]['trade_value'] = 400

        def response(route, payload):
            primary = self.f.fixture.offer(['player:a', 'pick:2028:1:3'], ['player:x'])
            alternative = self.f.fixture.offer(['player:a'], ['player:y'])
            for offer, sent, received in [(primary, 620.125, 600), (alternative, 420.125, 400)]:
                offer['balance_adjustment'] = {
                    'market_generation': 'canonical-fixture',
                    'original': {'sent': {'total': 420.125}, 'received': {'total': 600}, 'absolute_gap': 179.875},
                    'suggested': {'sent': {'total': sent}, 'received': {'total': received}, 'absolute_gap': 20.125},
                    'display': {'original': {'sent': '420.12', 'received': '600', 'gap': '179.88'},
                                'suggested': {'sent': manager_points(sent), 'received': manager_points(received), 'gap': '20.12'}},
                    'reason': 'Qualified alternative example.', 'meaning': 'Preview before adoption.'}
            route.fulfill(json={'results': [primary], 'other_trade_ideas': [alternative], 'count': 1})

        with self.f.fixture.page(api=response, workspace=data) as (page, _):
            self.f.build(page)
            page.click('#trade-balance-offer')
            page.get_by_role('button', name='Preview adjustment', exact=True).nth(1).wait_for()
            self.assertIn('Other trade ideas', page.locator('#trade-result').inner_text())
            cards = page.locator('.tw-balance-offer')
            self.assertIn('You receive: X', cards.nth(0).inner_text())
            self.assertIn('You receive: Y', cards.nth(1).inner_text())
            cards.nth(1).get_by_role('button', name='Preview adjustment', exact=True).click()
            compare = page.get_by_text('Compare with original proposal', exact=True).locator('..')
            compare.locator(':scope > summary').click()
            self.assertIn('Suggested Market: 420.12 sent / 400 received · Gap 20.12', compare.inner_text())
            self.assertEqual(self.f.state(page)['currentProposal']['received'], ['player:x'])
