"""Atomic account imports and accurately scoped Commissioner lineup evidence."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests import test_public_readiness as onboarding
from tests import test_dynamic_needs as diagnostics
from src.core.accounts import AccountStore
from src.core.intelligence.cache import IntelligenceCache
from src.core.intelligence.orchestrator import IntelligenceOrchestrator
from services.commissioner import build_commissioner_desk
from components.commissioner import front_office_summary, COMMISSIONER_DESK_CSS
from tools.validation.browser_runtime import launch_chromium
from playwright.sync_api import sync_playwright


def snapshot(store):
    """Logical contents, including revisions/identities, not a SQLite byte claim."""
    with closing(store.connect()) as c:
        return {r[0]: [list(row) for row in c.execute('SELECT * FROM "' + r[0] + '" ORDER BY rowid')]
                for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()}


class AtomicImportTests(unittest.TestCase):
    setUp = onboarding.PublicOnboardingTests.setUp
    link = onboarding.PublicOnboardingTests.link

    def sleeper(self, request):
        if request.url.path.endswith('/300'):
            return httpx.Response(200, json={'league_id': '300', 'name': 'Third league', 'sport': 'nfl', 'season': '2026'})
        return onboarding.PublicOnboardingTests.sleeper(self, request)

    def initial(self):
        self.link()
        for lid in ('300', '100'):
            self.assertEqual(self.client.post('/account/leagues/import', data={'csrf_token': self.csrf, 'league_id': lid}, follow_redirects=False).status_code, 303)

    def import_request(self, discovered=False):
        return self.client.post('/account/leagues/200' if discovered else '/account/leagues/import',
            data={'csrf_token': self.csrf, 'league_id': '200'}, follow_redirects=False)

    def test_four_stale_import_races_leave_all_durable_rows_unchanged(self):
        self.initial()
        evidence = []
        for discovered in (False, True):
            for selected, api in (('300', True), ('100', False)):
                with self.subTest(discovered=discovered, selected=selected):
                    entered, resume = threading.Event(), threading.Event()
                    async def prepare(lid):
                        if lid == '200':
                            entered.set()
                            if not await asyncio.to_thread(resume.wait, 10):
                                raise AssertionError('Import barrier was not released')
                        return object()
                    self.runtime.get.side_effect = prepare
                    with ThreadPoolExecutor() as pool:
                        pending = pool.submit(self.import_request, discovered)
                        try:
                            self.assertTrue(entered.wait(10))
                            response = self.client.post('/api/account/active-league', json={'league_id': selected}, headers={'X-CSRF-Token': self.csrf}) if api else self.client.post('/account/leagues/' + selected + '/activate', data={'csrf_token': self.csrf}, follow_redirects=False)
                            self.assertIn(response.status_code, (200, 303))
                            before = snapshot(self.store)
                        finally:
                            resume.set()
                        response = pending.result(10)
                    after = snapshot(self.store)
                    evidence.append({'discovered': discovered, 'new_selection': selected, 'status': response.status_code,
                        'before_counts': {k: len(v) for k,v in before.items()}, 'after_counts': {k: len(v) for k,v in after.items()},
                        'logically_identical': before == after})
                    if os.environ.get('DTOS_IMPORT_EVIDENCE'):
                        Path(os.environ['DTOS_IMPORT_EVIDENCE']).write_text(json.dumps(evidence, indent=2))
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(before, after)
        self.runtime.get.side_effect = None
        self.assertEqual(self.import_request().status_code, 303)
        self.assertEqual(len(self.store.memberships(self.account)), 3)
        self.assertEqual(self.store.context_for_session(self.token).active_league_id, '200')
        self.assertEqual(AccountStore(self.store.path).health()['counts']['memberships'], 3)

    def test_session_revoked_during_preparation_writes_nothing(self):
        self.initial()
        async def prepare(lid):
            self.store.revoke_session(self.token)
        self.runtime.get.side_effect = prepare
        # Expected comparison includes the deliberate logout, not the old request.
        original = self.store.revoke_session
        before = []
        def revoke(token):
            original(token)
            before.append(snapshot(self.store))
        with patch.object(self.store, 'revoke_session', side_effect=revoke):
            response = self.import_request()
        self.assertIn(response.status_code, (401, 303))
        self.assertEqual(before[-1], snapshot(self.store))

    def test_commit_failure_rolls_back_membership_series_and_revision(self):
        self.initial()
        with self.store.transaction() as c:
            c.execute("CREATE TRIGGER fail_import BEFORE INSERT ON account_league_series_seasons WHEN NEW.league_id='200' BEGIN SELECT RAISE(ABORT,'isolated commit failure'); END")
        before = snapshot(self.store)
        response = self.import_request()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(before, snapshot(self.store))
        with self.store.transaction() as c:
            c.execute('DROP TRIGGER fail_import')
        self.assertEqual(self.import_request().status_code, 303)

    def test_preparation_failure_and_cancel_do_not_open_write_transaction(self):
        self.initial()
        before = snapshot(self.store)
        async def failure(lid):
            with self.store.transaction() as c:
                self.assertEqual(c.execute('SELECT count(*) FROM accounts').fetchone()[0], 1)
            raise httpx.ReadTimeout('fixture preparation failed')
        self.runtime.get.side_effect = failure
        self.assertEqual(self.import_request().status_code, 503)
        self.assertEqual(before, snapshot(self.store))
        async def cancelled(lid):
            raise asyncio.CancelledError()
        self.runtime.get.side_effect = cancelled
        self.import_request()
        self.assertEqual(before, snapshot(self.store))

    def test_duplicate_and_unchanged_reads_do_not_grow_records(self):
        self.initial()
        self.assertEqual(self.import_request().status_code, 303)
        counts = {k:len(v) for k,v in snapshot(self.store).items()}
        self.assertEqual(self.import_request(True).status_code, 303)
        self.assertEqual(counts, {k:len(v) for k,v in snapshot(self.store).items()})
        before = snapshot(self.store)
        for _ in range(5):
            self.assertEqual(self.client.get('/api/account/leagues').status_code, 200)
        self.assertEqual(before, snapshot(self.store))


class CommissionerLineupTests(unittest.TestCase):
    setUp = diagnostics.CanonicalDiagnosticTests.setUp
    publish = diagnostics.CanonicalDiagnosticTests.publish

    def view(self, *, missing=False, zero=False, opponent=False, no_scoring=False, league='1313066632158924800'):
        self.publish([[('Alpha', 'QB', 0 if zero else 30)], [('Bravo', 'QB', 0 if zero else 20)], [('Charlie','QB',None if missing else (0 if zero else 10))]], ['QB', 'BN'], league=league)
        self.data['league']['name'] = 'Scoring league ' + league
        if no_scoring:
            self.data['league'].pop('scoring_settings')
        engine = IntelligenceOrchestrator(cache=IntelligenceCache())
        with patch('services.global_evidence.retained_global_evidence', return_value=None), patch('src.core.projection_intelligence.projection_service.snapshot', side_effect=self.service.snapshot), patch('src.core.projection_intelligence.projection_service.week_snapshot', side_effect=self.service.week_snapshot), patch('services.commissioner.intelligence_orchestrator', engine):
            return build_commissioner_desk(self.data, league, active_roster_id=2 if opponent else 1)

    def test_actual_source_dimension_truthful_label_population_and_ordinal(self):
        view = self.view()
        html = front_office_summary(view)
        self.assertIn('Optimal Projected Lineup', html)
        self.assertNotIn('championship readiness', html)
        self.assertNotIn('Current Contending Grade', html)
        self.assertNotIn('0% confidence', html)
        self.assertIn('83rd percentile', html)
        self.assertIn('30', html)
        self.assertIn('Week 1', html)
        self.assertIn('3 of 3 franchises', html)
        self.assertIn('Competitive Window', html)

    def test_partial_comparison_zero_and_two_leagues(self):
        for league in ('1313066632158924800', '1319750579458686976'):
            html = front_office_summary(self.view(missing=True, league=league))
            self.assertIn('2 of 3 franchises', html)
            self.assertIn(league, html)
            html = front_office_summary(self.view(zero=True, opponent=True, league=league))
            self.assertIn('0 projected points', html)
            self.assertIn('50th percentile', html)
            self.assertNotIn('championship readiness', html)

    def test_missing_scoring_withholds_lineup_not_a_zero(self):
        html = front_office_summary(self.view(no_scoring=True))
        self.assertIn('Unavailable projected points', html)
        self.assertIn('Percentile unavailable', html)
        self.assertIn('Lineup-relative grade unavailable', html)
        self.assertNotIn('0 projected points', html)

    def test_rendered_phone_disclosure_and_no_overflow(self):
        view = self.view()
        app = FastAPI()
        from fastapi.responses import HTMLResponse
        @app.get('/commissioner', response_class=HTMLResponse)
        def route():
            return '<meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:16px system-ui;background:#16191b;color:white}main{padding:12px}*{box-sizing:border-box}</style>' + COMMISSIONER_DESK_CSS + '<main>' + front_office_summary(view) + '</main>'
        client = TestClient(app)
        self.addCleanup(client.close)
        evidence = []
        with sync_playwright() as p:
            browser = launch_chromium(p)
            try:
                for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                    page = browser.new_page(viewport={'width':width,'height':height})
                    page.route('**/*', lambda route: route.fulfill(status=200,content_type='text/html',body=client.get('/commissioner').text))
                    page.goto('https://isolated.test/commissioner')
                    card = page.locator('.cd-office-main')
                    self.assertIn('83rd percentile',card.inner_text())
                    self.assertNotIn('confidence',card.inner_text())
                    collapsed_height = card.bounding_box()['height']
                    disclosure = card.locator('summary').first
                    disclosure.focus()
                    page.keyboard.press('Enter')
                    self.assertTrue(card.locator('details').first.evaluate('(e)=>e.open'))
                    geometry = page.evaluate('({width:innerWidth, scroll:document.documentElement.scrollWidth})')
                    self.assertLessEqual(geometry['scroll'],width)
                    evidence.append({**geometry,'height':height,'collapsed_height':collapsed_height,'expanded_height':card.bounding_box()['height']})
                    page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_COMMISSIONER_EVIDENCE'):
            Path(os.environ['DTOS_COMMISSIONER_EVIDENCE']).write_text(json.dumps(evidence,indent=2))



class AdditionalImportControls(unittest.TestCase):
    setUp = AtomicImportTests.setUp
    sleeper = AtomicImportTests.sleeper
    link = AtomicImportTests.link
    initial = AtomicImportTests.initial
    import_request = AtomicImportTests.import_request
    def test_store_authority_revision_rollback_and_independent_account(self):
        self.initial()
        revision = self.store.account_by_username('new-manager')['updated_at']
        series = asyncio.run(self.service.complete_series({'league_id':'200','season':'2026','name':'Second league','sport':'nfl'}))
        arguments = dict(session_token=self.token, expected_account_revision=revision, sleeper_user_id='new-user', league=series.current_league, series_id=series.series_id, seasons=series.seasons, roster_id=2, franchise_name='New manager')
        other,_ = self.service.create_account('other-user','Other','isolated password')
        other_token,_ = self.service.new_session(other)
        for changes in ({'expected_account_revision':'obsolete'}, {'session_token':other_token}, {'sleeper_user_id':'foreign-owner'}, {'league':{}}, {'roster_id':None}):
            before = snapshot(self.store)
            self.assertFalse(self.store.commit_import(self.account,**(arguments|changes)))
            self.assertEqual(before,snapshot(self.store))
        self.assertTrue(self.store.commit_import(self.account,**arguments))
        with closing(self.store.connect()) as c:
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(self.store.memberships(other),[])

    def test_simultaneous_imports_only_one_revision_can_commit(self):
        self.initial()
        entered = threading.Barrier(2)
        async def prepare(lid):
            if lid == '200':
                await asyncio.to_thread(entered.wait,10)
        self.runtime.get.side_effect = prepare
        with ThreadPoolExecutor(2) as pool:
            responses = [f.result(15).status_code for f in [pool.submit(self.import_request,False),pool.submit(self.import_request,True)]]
        self.assertEqual(sorted(responses),[303,409])
        self.assertEqual(len(self.store.memberships(self.account)),3)
        self.assertEqual(len(self.store.series(self.account)),3)

    def test_expired_session_and_foreign_csrf_cannot_commit(self):
        self.initial()
        before = snapshot(self.store)
        self.assertEqual(self.client.post('/account/leagues/import',data={'csrf_token':'foreign','league_id':'200'}).status_code,403)
        self.assertEqual(before,snapshot(self.store))
        async def expire(lid):
            with self.store.transaction() as c:
                c.execute("UPDATE account_sessions SET expires_at='2000-01-01' WHERE account_id=?",(self.account,))
            before.clear()
            before.update(snapshot(self.store))
        self.runtime.get.side_effect = expire
        self.assertEqual(self.import_request().status_code,303)
        self.assertEqual(before,snapshot(self.store))


class PercentileFormatTests(unittest.TestCase):
    def test_ordinal_matrix(self):
        from src.ui.intelligence_presentation import percentile_label
        for number,suffix in [(0,'th'),(1,'st'),(2,'nd'),(3,'rd'),(4,'th'),(11,'th'),(12,'th'),(13,'th'),(21,'st'),(22,'nd'),(23,'rd'),(83,'rd'),(100,'th')]:
            self.assertEqual(percentile_label(number),f'{number}{suffix} percentile')
        self.assertEqual(percentile_label(None),'Percentile unavailable')

class ImportPhoneTests(unittest.TestCase):
    setUp = AtomicImportTests.setUp
    sleeper = AtomicImportTests.sleeper
    link = AtomicImportTests.link
    initial = AtomicImportTests.initial
    browser = onboarding.PublicOnboardingTests.browser

    def test_native_import_conflict_status_and_retry_control(self):
        self.initial()
        for width,height in ((320,432),(375,667),(390,844),(1280,900)):
            entered,resume = threading.Event(),threading.Event()
            async def prepare(lid):
                if lid == '200':
                    entered.set()
                    if not await asyncio.to_thread(resume.wait,10):
                        raise AssertionError('Browser import barrier not released')
            self.runtime.get.side_effect = prepare
            with self.browser(width,height) as page:
                page.goto(self.origin+'/account/leagues')
                form = page.locator('form[action="/account/leagues/import"]')
                form.locator('input[name="league_id"]').fill('200')
                try:
                    form.get_by_role('button',name='Add to DTOS').click(no_wait_after=True)
                    self.assertTrue(entered.wait(10))
                    response = self.client.post('/api/account/active-league',json={'league_id':'100'},headers={'X-CSRF-Token':self.csrf})
                    self.assertEqual(response.status_code,200)
                    before = snapshot(self.store)
                    with page.expect_response(lambda r:r.url.endswith('/account/leagues/import') and r.status==409):
                        resume.set()
                    page.wait_for_load_state()
                    self.assertIn('newer league choice',page.locator('body').inner_text().lower())
                    retry = page.get_by_role('link',name='Your leagues · retry import')
                    retry.focus()
                    self.assertTrue(retry.evaluate('e=>e===document.activeElement'))
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                    self.assertEqual(before,snapshot(self.store))
                    retry.click()
                    self.assertEqual(page.url,self.origin+'/account/leagues')
                finally:
                    resume.set()


if __name__ == '__main__':
    unittest.main()
