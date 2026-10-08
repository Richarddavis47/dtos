"""Scout A–C: real Chromium session, API presentation and targeted reload contracts."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

from components.trade_workspace import trade_workspace
from tests import test_trade_workspace_batch1 as boundary
from tools.validation.browser_runtime import launch_chromium


class ScoutWorkspaceStateBrowserTests(unittest.TestCase):
    @staticmethod
    def workspace():
        def player(value, price):
            return {'asset_id': 'player:' + value, 'label': value.upper(), 'kind': 'player', 'position': 'WR', 'trade_value': price}
        return {'workspace_context': {'binding': 'scout-session', 'ownership_generation': 'owned'},
                'manager_context': {'league_id': 'fixture'}, 'csrf_token': 'fixture', 'teams': [
                    {'roster_id': 1, 'team_name': 'Active', 'assets': [player('a', 400), player('b', 250), player('d', 100),
                        {'asset_id': 'pick:2028:1:3', 'label': '2028 Round 1 — Original franchise Extremely Long Franchise Name / currently owned by Active',
                         'kind': 'pick', 'season': 2028, 'round': 1, 'original_roster_id': 3, 'trade_value': 200},
                        {'asset_id': 'pick:2028:2:3', 'label': '2028 Round 2 — Original franchise 3', 'kind': 'pick',
                         'season': 2028, 'round': 2, 'original_roster_id': 3, 'trade_value': 100}]},
                    {'roster_id': 2, 'team_name': 'Partner', 'assets': [player('x', 600), player('y', 100)]}]}

    @staticmethod
    def offer(sent, received):
        return {'proposal': {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': sent, 'assets_received': received},
                'evaluation': {'recommendation': 'WORTH PURSUING', 'why_you_would_do_it': 'Supported fixture benefit.',
                               'major_drawback': 'This spends depth.', 'counterparty_summary': 'Supported fixture return.'}}

    @contextmanager
    def page(self, width=390, *, api=None, workspace=None):
        data = workspace or self.workspace()
        requests, errors = [], []
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            context = browser.new_context(viewport={'width': width, 'height': 844})
            page = context.new_page()
            page.set_default_timeout(6000)
            page.on('pageerror', lambda error: errors.append(str(error)))

            def route(r):
                parsed = urlsplit(r.request.url)
                if parsed.netloc != 'dtos.test':
                    return r.abort()
                if parsed.path.startswith('/static/'):
                    path = Path(parsed.path.lstrip('/'))
                    return r.fulfill(content_type='text/css; charset=utf-8' if path.suffix == '.css' else 'text/javascript; charset=utf-8', body=path.read_text())
                if parsed.path == '/api/trades/workspace':
                    return r.fulfill(json=data)
                if parsed.path.startswith('/api/trades/'):
                    payload = r.request.post_data_json
                    requests.append((parsed.path.rsplit('/', 1)[-1], payload))
                    if api:
                        return api(r, payload)
                    offered = self.offer(['player:a', 'player:d'], ['player:x'])
                    if payload.get('workflow') == 'trade_for':
                        offered = self.offer(['player:a'], ['player:x', 'player:y'])
                    if parsed.path.endswith('/assist'):
                        offered = self.offer(['player:a'], list(payload['assets_received']))
                    body = {'results': [offered], 'count': 1, 'requested_mode': payload.get('repair_mode'),
                            'returned_modes': [payload['repair_mode']] if payload.get('repair_mode') else [], 'target_preserved': True,
                            'constraints': {'protected_assets': payload['protected_assets'], 'excluded_assets': payload['excluded_assets']}}
                    if parsed.path.endswith('/generate') and payload['workflow'] == 'shop':
                        body['markets'] = [{'counterparty_roster_id': 2, 'returns': [offered]}]
                    return r.fulfill(json=body)
                workflow = parsed.path.rsplit('/', 1)[-1]
                if workflow in ('shop', 'trade-for', 'create', 'recommended'):
                    preload = parse_qs(parsed.query).get('asset_id', [None])[0]
                    return r.fulfill(content_type='text/html; charset=utf-8', body=trade_workspace({'active_team': {'roster_id': 1}}, workflow, preload))
                r.abort()

            page.context.route('**/*', route)
            try:
                yield page, requests
                self.assertEqual(errors, [])
            finally:
                browser.close()

    @staticmethod
    def ready(page, url):
        page.goto('https://dtos.test' + url)
        page.locator('#trade-context').get_by_text('Active league', exact=False).wait_for()

    @staticmethod
    def adopt(page):
        page.get_by_role('button', name='Open editable offer:', exact=False).first.click()
        page.get_by_role('button', name='Adopt alternative', exact=True).click()

    @staticmethod
    def proposal(page):
        return page.evaluate("JSON.parse(sessionStorage.getItem('dtos-trade-workspace:scout-session')).currentProposal")

    def test_shop_protection_survives_adoption_cheaper_alternatives_and_reload(self):
        for width in (375, 390):
            with self.subTest(width=width), self.page(width) as (page, requests):
                self.ready(page, '/trades/shop?asset_id=player:a')
                page.locator('#shop-protected').select_option('player:b')
                page.click('#trade-find')
                self.adopt(page)
                original = self.proposal(page)
                self.assertEqual(original['sent'], ['player:a', 'player:d'])
                page.reload()
                page.locator('#trade-target:not([hidden])').wait_for()
                self.assertEqual(self.proposal(page), original)
                self.assertEqual(page.locator('#shop-protected').evaluate('n => [...n.selectedOptions].map(o => o.value)'), ['player:b'])
                page.click('#trade-adjust')
                page.fill('#trade-instruction', 'make it cheaper')
                page.click('#trade-apply-adjust')
                page.get_by_role('button', name='Open editable offer:', exact=False).click()
                self.assertEqual(self.proposal(page), original)
                self.assertIn('Original: A + D', page.locator('#trade-result').inner_text())
                page.get_by_role('button', name='Keep original', exact=True).click()
                self.assertEqual(self.proposal(page), original)
                self.adopt(page)
                self.assertEqual(self.proposal(page)['sent'], ['player:a'])
                page.click('#trade-alternatives')
                page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
                for _, request in requests:
                    self.assertEqual(request['protected_assets'], ['player:b'])
                    self.assertNotIn('player:b', request['assets_sent'])
                for path, request in requests:
                    if path in ('assist', 'alternatives'):
                        self.assertEqual(request['origin_workflow'], 'shop')
                        self.assertEqual(request['origin_asset_id'], 'player:a')
                        self.assertIn('player:a', request['assets_sent'])
                self.assertLessEqual(page.locator('body').evaluate('n => n.scrollWidth'), width)

    def test_trade_for_multi_asset_reload_and_target_retention(self):
        with self.page() as (page, requests):
            self.ready(page, '/trades/trade-for?asset_id=player:x')
            page.click('#trade-find')
            self.adopt(page)
            original = self.proposal(page)
            self.assertEqual(original['received'], ['player:x', 'player:y'])
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            self.assertEqual(self.proposal(page), original)
            page.click('#trade-adjust')
            page.fill('#trade-instruction', 'make it cheaper')
            page.click('#trade-apply-adjust')
            page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
            self.assertEqual(requests[-1][1]['origin_workflow'], 'trade_for')
            self.assertIn('player:x', requests[-1][1]['assets_received'])
            page.click('#trade-edit')
            page.get_by_role('button', name='Their assets', exact=True).click()
            page.locator('#trade-received-board button[data-asset-id="player:x"]').click()
            self.assertIn('player:x', self.proposal(page)['received'])

    def test_empty_targeted_workspaces_still_initialize(self):
        for route, which, value in (('shop', 'sent', 'player:a'), ('trade-for', 'received', 'player:x')):
            with self.subTest(route=route), self.page() as (page, _):
                self.ready(page, f'/trades/{route}?asset_id={value}')
                self.assertEqual(self.proposal(page)[which], [value])
                self.assertIn(value[-1].upper(), page.locator('#trade-target').inner_text())

    def test_new_target_replaces_incompatible_offer_and_invalid_entry_stays_blocked(self):
        with self.page() as (page, _):
            self.ready(page, '/trades/shop?asset_id=player:a')
            page.click('#trade-find')
            self.adopt(page)
            self.ready(page, '/trades/shop?asset_id=player:d')
            self.assertEqual(self.proposal(page), {'sent': ['player:d'], 'received': [], 'partner': 0})
            self.assertIn('D', page.locator('#trade-target').inner_text())
            for preload in ('player:missing', 'player:x'):
                self.ready(page, '/trades/shop?asset_id=' + preload)
                self.assertIn('not currently owned', page.locator('#trade-result').inner_text())
                self.assertTrue(page.locator('#trade-target').is_hidden())
                self.assertTrue(page.locator('#trade-find').is_disabled())

    def test_explicit_new_recommended_adoption_changes_objective_not_locks(self):
        def api(r, p):
            if p['workflow'] == 'shop':
                offered = self.offer(['player:a', 'player:d'], ['player:x'])
                r.fulfill(json={'markets': [{'counterparty_roster_id': 2, 'returns': [offered]}]})
            else:
                offered = {**self.offer(['player:d'], ['player:x']), 'workflow': 'recommended', 'family_id': 'fixture-family'}
                r.fulfill(json={'workflow': 'recommended', 'results': [offered], 'has_more': False})
        with self.page(api=api) as (page, _):
            self.ready(page, '/trades/shop?asset_id=player:a')
            page.locator('#shop-protected').select_option('player:b')
            page.click('#trade-find')
            self.adopt(page)
            original = self.proposal(page)
            self.ready(page, '/trades/recommended')
            page.click('#trade-find')
            page.get_by_role('button', name='Open editable offer:', exact=False).click()
            self.assertEqual(self.proposal(page), original)
            page.get_by_role('button', name='Keep original', exact=True).click()
            self.assertEqual(self.proposal(page), original)
            self.adopt(page)
            self.assertEqual(self.proposal(page)['sent'], ['player:d'])
            state = page.evaluate("JSON.parse(sessionStorage.getItem('dtos-trade-workspace:scout-session'))")
            self.assertEqual(state['protectedAssets'], ['player:b'])
            self.assertIsNone(state['requiredOutgoingAsset'])

    def test_preview_survives_reload_until_deliberate_keep_or_adopt(self):
        with self.page() as (page, _):
            self.ready(page, '/trades/shop?asset_id=player:a')
            page.click('#trade-find')
            self.adopt(page)
            original = self.proposal(page)
            page.click('#trade-adjust')
            page.fill('#trade-instruction', 'make it cheaper')
            page.click('#trade-apply-adjust')
            page.get_by_role('button', name='Open editable offer:', exact=False).click()
            page.reload()
            page.get_by_role('button', name='Keep original', exact=True).wait_for()
            self.assertEqual(self.proposal(page), original)
            self.assertIn('Original: A + D', page.locator('#trade-result').inner_text())
            page.get_by_role('button', name='Keep original', exact=True).click()
            self.assertEqual(self.proposal(page), original)
            page.click('#trade-adjust')
            page.fill('#trade-instruction', 'make it cheaper')
            page.click('#trade-apply-adjust')
            page.get_by_role('button', name='Open editable offer:', exact=False).click()
            page.get_by_role('button', name='Adopt alternative', exact=True).click()
            self.assertEqual(self.proposal(page)['sent'], ['player:a'])

    def test_explicit_shop_replaces_manual_package_and_preserves_locks(self):
        with self.page() as (page, requests):
            self.ready(page, '/trades/create')
            page.get_by_label('Counterparty', exact=True).select_option('2')
            for value in ('player:a', 'player:d'):
                page.locator(f'#trade-sent-board button[data-asset-id="{value}"]').click()
            page.get_by_role('button', name='Their assets', exact=True).click()
            page.locator('#trade-received-board button[data-asset-id="player:x"]').click()
            page.click('#trade-adjust')
            page.locator('#trade-constraint-asset').select_option('player:b')
            page.fill('#trade-instruction', 'keep this player')
            page.click('#trade-apply-adjust')
            page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
            self.ready(page, '/trades/shop?asset_id=player:a')
            self.assertEqual(self.proposal(page), {'sent': ['player:a'], 'received': [], 'partner': 0})
            self.assertEqual(page.locator('#shop-protected').evaluate('n => [...n.selectedOptions].map(o => o.value)'), ['player:b'])
            page.click('#trade-find')
            self.adopt(page)
            self.ready(page, '/trades/create')
            page.click('#trade-adjust')
            page.click('#trade-alternatives')
            page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
            self.assertEqual(requests[-1][1]['protected_assets'], ['player:b'])
            self.assertEqual(requests[-1][1]['origin_asset_id'], 'player:a')

    def test_one_exact_pick_lock_leaves_other_pick_usable(self):
        def api(r, p):
            offered = self.offer(['player:a', 'pick:2028:2:3'], ['player:x'])
            r.fulfill(json={'markets': [{'counterparty_roster_id': 2, 'returns': [offered]}], 'results': [offered]})
        with self.page(api=api) as (page, requests):
            self.ready(page, '/trades/shop?asset_id=player:a')
            page.locator('#shop-protected').select_option('pick:2028:1:3')
            page.click('#trade-find')
            self.adopt(page)
            self.assertEqual(requests[-1][1]['protected_assets'], ['pick:2028:1:3'])
            self.assertIn('pick:2028:2:3', self.proposal(page)['sent'])
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            page.click('#trade-adjust')
            page.click('#trade-alternatives')
            page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
            self.assertEqual(requests[-1][1]['protected_assets'], ['pick:2028:1:3'])
            self.assertNotIn('pick:2028:1:3', self.proposal(page)['sent'])

    def test_shop_pick_anchor_survives_adoption_and_repair(self):
        pick = 'pick:2028:1:3'
        def api(r, p):
            sent = [pick] if urlsplit(r.request.url).path.endswith('/assist') else [pick, 'player:d']
            offered = self.offer(sent, ['player:x'])
            body = {'results': [offered], 'requested_mode': p.get('repair_mode'),
                    'returned_modes': [p['repair_mode']] if p.get('repair_mode') else [], 'target_preserved': True}
            if urlsplit(r.request.url).path.endswith('/generate'):
                body['markets'] = [{'counterparty_roster_id': 2, 'returns': [offered]}]
            r.fulfill(json=body)
        with self.page(api=api) as (page, requests):
            self.ready(page, '/trades/shop?asset_id=' + pick)
            page.locator('#shop-protected').select_option('player:b')
            page.click('#trade-find')
            self.adopt(page)
            page.reload()
            page.locator('#trade-target:not([hidden])').wait_for()
            page.click('#trade-adjust')
            page.fill('#trade-instruction', 'make it cheaper')
            page.click('#trade-apply-adjust')
            self.adopt(page)
            page.click('#trade-alternatives')
            page.get_by_role('button', name='Open editable offer:', exact=False).wait_for()
            for path, request in requests:
                self.assertEqual(request['protected_assets'], ['player:b'])
                self.assertNotIn(pick, request['protected_assets'])
                if path != 'generate':
                    self.assertEqual(request['origin_asset_id'], pick)
                    self.assertIn(pick, request['assets_sent'])

    def test_real_api_exact_conflict_visible_without_automatic_relaxation(self):
        fixture = boundary.AuthenticatedTradeBoundaryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        workspace = fixture.client.get('/api/trades/workspace?front_office=1').json()
        pick = next(a for a in workspace['teams'][0]['assets'] if a['kind'] == 'pick')
        for width in (375, 390):
            def api(r, p):
                response = fixture.client.post('/api/trades/' + urlsplit(r.request.url).path.rsplit('/', 1)[-1],
                    json=p, headers={'X-CSRF-Token': fixture.csrf})
                self.assertEqual(response.status_code, 200)
                r.fulfill(json=response.json())
            with self.subTest(width=width), self.page(width, api=api, workspace=workspace) as (page, requests):
                self.ready(page, '/trades/shop?asset_id=' + pick['asset_id'])
                page.locator('#shop-protected').select_option(pick['asset_id'])
                page.click('#trade-find')
                page.locator('.tw-conflict').wait_for()
                self.assertIn('required outgoing Shop asset', page.locator('.tw-conflict').inner_text())
                page.get_by_label('Counterparty', exact=True).select_option('2')
                page.get_by_role('button', name='Their assets', exact=True).click()
                page.locator('#trade-received-board button[data-asset-id="2-QB-0"]').click()
                page.locator('#shop-protected').select_option(pick['asset_id'])
                page.click('#trade-adjust')
                page.fill('#trade-instruction', 'make it cheaper')
                page.click('#trade-apply-adjust')
                conflict = page.locator('.tw-conflict')
                conflict.wait_for()
                text = conflict.inner_text()
                self.assertIn(pick['asset_id'], text)
                self.assertIn(pick.get('raw_label') or pick['label'], text)
                self.assertIn('conflicts with the required trade objective', text)
                self.assertIn('Optional change: Remove the conflicting exact lock on', text)
                self.assertIn('No package was evaluated', text)
                self.assertEqual(page.get_by_text('Evaluated near misses', exact=True).count(), 0)
                self.assertEqual(page.locator('#shop-protected').evaluate('n => [...n.selectedOptions].map(o => o.value)'), [pick['asset_id']])
                self.assertEqual(requests[-1][1]['protected_assets'], [pick['asset_id']])
                self.assertTrue(conflict.is_visible())
                self.assertLessEqual(page.locator('body').evaluate('n => n.scrollWidth'), width)

    def test_long_pick_blocker_and_preview_controls_at_phone_widths(self):
        pick = self.workspace()['teams'][0]['assets'][3]
        def api(r, p):
            if urlsplit(r.request.url).path.endswith('/generate'):
                offered = self.offer(['player:a', 'player:d'], ['player:x'])
                r.fulfill(json={'markets': [{'counterparty_roster_id': 2, 'returns': [offered]}]})
            else:
                r.fulfill(json={'count': 0, 'results': [], 'requested_mode': p['repair_mode'], 'returned_modes': [],
                    'quiet_state': 'GENERIC FALLBACK MUST NOT REPLACE STRUCTURED BLOCKER',
                    'blocking_asset_ids': [pick['asset_id']], 'conflict_explanation': 'Your exact protected pick conflicts with the required outgoing objective.',
                    'smallest_optional_relaxation': 'Remove only the exact first-round lock, if you choose.'})
        for width in (375, 390):
            with self.subTest(width=width), self.page(width, api=api) as (page, _):
                self.ready(page, '/trades/shop?asset_id=player:a')
                page.locator('#shop-protected').select_option(pick['asset_id'])
                page.click('#trade-find')
                page.get_by_role('button', name='Open editable offer:', exact=False).click()
                for name in ('Keep original', 'Adopt alternative'):
                    button = page.get_by_role('button', name=name, exact=True)
                    button.scroll_into_view_if_needed()
                    self.assertTrue(button.is_visible())
                    self.assertTrue(button.evaluate('n => {const r=n.getBoundingClientRect(); return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===n;}'))
                page.get_by_role('button', name='Adopt alternative', exact=True).click()
                page.click('#trade-adjust')
                page.fill('#trade-instruction', 'make it cheaper')
                page.click('#trade-apply-adjust')
                conflict = page.locator('.tw-conflict')
                conflict.wait_for()
                self.assertIn(pick['label'], conflict.inner_text())
                self.assertIn('Remove only the exact first-round lock', conflict.inner_text())
                self.assertNotIn('GENERIC FALLBACK', page.locator('#trade-result').inner_text())
                self.assertLessEqual(page.locator('body').evaluate('n => n.scrollWidth'), width)
                conflict.scroll_into_view_if_needed()
                self.assertGreater(conflict.bounding_box()['height'], 44)
                optional = conflict.get_by_text('Optional change:', exact=False)
                optional.scroll_into_view_if_needed()
                self.assertTrue(optional.evaluate('n => {const r=n.getBoundingClientRect(); const top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2); return top===n || n.contains(top);}'))
