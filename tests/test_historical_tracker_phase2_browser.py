"""Rendered source-backed discovery, lineage, reload and phone interaction."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from routes.home import create_home_router
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from tools.validation.browser_runtime import launch_chromium
from tests import test_historical_tracker_phase2 as fixtures


class TrackerPhase2BrowserTests(unittest.TestCase):
    def setUp(self):
        import dtos_app
        self.application = dtos_app
        self.fixture = fixtures.TrackerPhase2Tests()
        self.fixture.page_renderer = dtos_app.page
        self.fixture.setUp()
        self.fixture.data['last_sync'] = '2026-10-13T02:00:00Z'
        self.fixture.data['roster_positions'] = self.fixture.fixture.sources[0]['league']['roster_positions']
        self.fixture.data['league_settings'] = self.fixture.fixture.sources[0]['league']['settings']
        self.fixture.data['scoring_settings'] = self.fixture.fixture.sources[0]['league']['scoring_settings']
        self.fixture.data['transactions'] = [t for bucket in self.fixture.fixture.sources[0]['transactions'].values() for t in bucket]
        self.fixture.data['team_lookup'] = {t['roster_id']: t for t in self.fixture.data['teams']}
        self.fixture.fixture.store.update_current(fixtures.DAY, self.fixture.data)
        self.fixture.app.include_router(create_home_router(
            ensure_fresh=fixtures.prepared, require_data=lambda: self.fixture.data, page=dtos_app.page))
        self.measurements = []

    def tearDown(self):
        self.fixture.tearDown()

    def browser(self, pw):
        browser = launch_chromium(pw, headless=True, args=['--no-sandbox'])
        def transport(route):
            url = urlsplit(route.request.url)
            if url.netloc != 'fixture':
                route.fulfill(status=404)
                return
            response = self.fixture.client.get(url.path + ('?' + url.query if url.query else ''))
            route.fulfill(status=response.status_code,
                          content_type=response.headers.get('content-type', 'text/html'), body=response.content)
        return browser, transport

    def bounded(self, page, width, label):
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width, label)
        self.measurements.append({'view': label, 'width': width,
                                  'documentWidth': page.evaluate('document.documentElement.scrollWidth'),
                                  'height': page.evaluate('document.documentElement.scrollHeight')})

    def test_actual_discovery_multi_hop_return_and_lazy_production_at_all_widths(self):
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), patch.dict(self.application.STATE, {'data': self.fixture.data}), sync_playwright() as pw:
            browser, transport = self.browser(pw)
            for width, height in [(320, 568), (375, 667), (390, 844), (390, 432), (1165, 800)]:
                page = browser.new_page(viewport={'width': width, 'height': height})
                page.route('**/*', transport)
                production_requests = []
                page.on('request', lambda request: production_requests.append(request.url) if '/production?' in request.url else None)
                page.goto('http://fixture/league')
                page.get_by_role('link', name='Transactions', exact=False).filter(has=page.locator('h3')).click()
                page.locator('select[name="scope"]').select_option('all_history')
                page.locator('select[name="type"]').select_option('trade')
                page.get_by_role('button', name='Apply filters', exact=False).click()
                page.get_by_role('heading', name='Historical Archive', exact=True).wait_for()
                self.assertNotIn('int_parsing', page.locator('body').inner_text())
                self.assertIn('Archive page 1', page.locator('main').inner_text())
                self.bounded(page, width, 'archive form')
                page.locator(f'a[href="/trades/history/{fixtures.ROOT}"]').first.click()
                self.assertEqual(production_requests, [])
                self.assertIn('Denzel Boston', page.locator('.trade-timeline').inner_text())
                self.assertIn('Chase Bank', page.locator('.trade-timeline').inner_text())
                source = page.locator('details[data-production-endpoint]')
                summary = source.locator(':scope > summary')
                summary.focus()
                self.assertNotEqual(summary.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                page.keyboard.press('Enter')
                page.get_by_text('Complete holding-period benefit: Unavailable.', exact=False).first.wait_for()
                self.assertEqual(len(production_requests), 1)
                summary.click()
                summary.click()
                self.assertEqual(len(production_requests), 1)
                self.bounded(page, width, 'original and loaded partial production')
                page.locator(f'a[href="/picks/{fixtures.PICK}?from_trade={fixtures.ROOT}"]').first.click()
                self.assertIn('Consumed by verified draft conversion', page.locator('main').inner_text())
                player = page.get_by_role('link', name='Denzel Boston', exact=True)
                self.assertIn('from_trade=' + fixtures.ROOT, player.get_attribute('href'))
                player.click()
                page.get_by_role('link', name='Back to original trade timeline', exact=False).wait_for()
                self.bounded(page, width, 'converted player')
                page.reload()
                self.assertEqual(page.get_by_role('link', name='Back to original trade timeline', exact=False).get_attribute('href'), '/trades/history/' + fixtures.ROOT)
                page.get_by_role('link', name='Open observed historical performance').click()
                page.get_by_role('link', name='Back to original trade timeline', exact=False).wait_for()
                self.bounded(page, width, 'partial historical performance')
                page.go_back()
                page.locator('a[href="/trades/history/1414718106177122304?from_trade=' + fixtures.ROOT + '"]').last.click()
                page.reload()
                back = page.get_by_role('link', name='Back to original trade timeline', exact=False)
                self.assertEqual(back.get_attribute('href'), '/trades/history/' + fixtures.ROOT)
                back.focus()
                self.assertNotEqual(back.evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'none')
                back.press('Enter')
                self.assertEqual(urlsplit(page.url).path, '/trades/history/' + fixtures.ROOT)
                page.goto('http://fixture/trades/history/' + fixtures.FAAB)
                self.assertEqual(page.locator('.timeline-faab').count(), 1)
                self.assertIn('100 FAAB', page.locator('.timeline-faab').inner_text())
                self.assertIn('Nasty Navel Lasers → zkobes', page.locator('.timeline-faab').inner_text())
                self.assertEqual(page.locator('.timeline-asset').count(), 8)
                page.locator('details:not([data-production-endpoint])').evaluate_all('(rows)=>rows.forEach(r=>r.open=true)')
                self.bounded(page, width, 'three-party FAAB and expanded evidence')
                page.goto('http://fixture/history/2023')
                self.assertEqual(page.get_by_role('heading', name='2023 Season Archive', level=2).count(), 1)
                self.bounded(page, width, 'missing-bracket season')
                page.close()
            browser.close()
        target = Path('.validation/tracker-phase2')
        target.mkdir(parents=True, exist_ok=True)
        (target / 'browser-geometry.json').write_text(json.dumps(self.measurements, indent=2))

    def test_scope_switch_foreign_origin_and_source_change_feedback(self):
        with patch.object(data_platform, 'warehouse', SnapshotWarehouse()), patch.dict(self.application.STATE, {'data': self.fixture.data}), sync_playwright() as pw:
            browser, transport = self.browser(pw)
            page = browser.new_page(viewport={'width': 320, 'height': 568})
            page.route('**/*', transport)
            page.goto('http://fixture/trades/history/' + fixtures.ROOT)
            facts = self.fixture.fixture.cache.read(fixtures.DAY, 2026).facts.copy()
            facts['matchups'] = {'1': []}
            self.fixture.publish(facts)
            page.locator('details[data-production-endpoint] summary').click()
            page.get_by_text('Source evidence changed. Reload this trade.', exact=False).wait_for()
            self.bounded(page, 320, 'changed-source warning')
            day = self.fixture.data
            self.fixture.data = self.fixture.fixture.data[fixtures.ARK]
            self.application.STATE['data'] = self.fixture.data
            self.assertEqual(page.goto('http://fixture/trades/history/' + fixtures.ROOT).status, 404)
            self.assertEqual(page.goto('http://fixture/history').status, 200)
            self.bounded(page, 320, 'independent Arkham history')
            self.fixture.data = day
            self.application.STATE['data'] = day
            self.assertEqual(page.goto('http://fixture/trades/history/' + fixtures.ROOT).status, 200)
            self.assertEqual(page.locator('.trade-timeline a.back').get_attribute('href'), '/transactions')
            page.close()
            browser.close()


if __name__ == '__main__':
    unittest.main()
