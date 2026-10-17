"""Real authenticated import rejection and recovery, without production writes."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from tests import test_public_readiness as onboarding
from tests.test_import_commissioner_integrity import snapshot


class UnmatchedImportRecoveryTests(unittest.TestCase):
    setUp = onboarding.PublicOnboardingTests.setUp
    sleeper = onboarding.PublicOnboardingTests.sleeper
    link = onboarding.PublicOnboardingTests.link
    browser = onboarding.PublicOnboardingTests.browser

    def initial(self):
        self.link()
        response = self.client.post('/account/leagues/100', data={'csrf_token': self.csrf}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.runtime.get.reset_mock()
        self.no_membership = True

    def reject(self, discovered):
        return self.client.post('/account/leagues/200' if discovered else '/account/leagues/import',
                                data={'csrf_token': self.csrf, 'league_id': '200'}, follow_redirects=False)

    def test_both_rejections_have_functional_authenticated_recovery_and_no_writes(self):
        self.initial()
        before = snapshot(self.store)
        for discovered in (False, True):
            with self.subTest(discovered=discovered):
                response = self.reject(discovered)
                self.assertEqual(response.status_code, 200)
                self.assertIn('could not confidently match your team', response.text)
                self.assertIn('href="/account/leagues">Your leagues</a>', response.text)
                self.assertIn('href="/account/sleeper">Review Sleeper identity</a>', response.text)
                self.assertEqual(response.headers['cache-control'], 'no-store, private')
                leagues = self.client.get('/account/leagues')
                self.assertEqual(leagues.status_code, 200)
                self.assertIn('First league', leagues.text)
                self.assertIn('Switch front office', leagues.text)
                identity = self.client.get('/account/sleeper')
                self.assertEqual(identity.status_code, 200)
                self.assertIn('Sleeper username', identity.text)
                self.assertEqual(snapshot(self.store), before)
        self.runtime.get.assert_not_called()

    def test_recovery_discovery_failure_still_exposes_own_saved_connection(self):
        self.initial()
        before = snapshot(self.store)
        for discovered in (False, True):
            with self.subTest(discovered=discovered):
                self.source_failures.clear()
                self.assertEqual(self.reject(discovered).status_code, 200)
                self.source_failures.add('/leagues/nfl/')
                response = self.client.get('/account/leagues')
                self.assertEqual(response.status_code, 200)
                self.assertIn('Saved connection', response.text)
                self.assertIn('First league', response.text)
                self.assertNotIn('Second league', response.text)
                self.assertNotIn('private provider', response.text)
                self.assertEqual(snapshot(self.store), before)

    def test_recovery_session_expiration_requires_sign_in(self):
        self.initial()
        self.assertEqual(self.reject(False).status_code, 200)
        self.store.revoke_session(self.token)
        before = snapshot(self.store)
        for destination in ('/account/leagues', '/account/sleeper'):
            response = self.client.get(destination, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers['location'], '/account/sign-in')
        self.assertEqual(snapshot(self.store), before)

    def test_invalid_csrf_cannot_reach_either_import_or_recover_by_granting_ownership(self):
        self.initial()
        before = snapshot(self.store)
        for path in ('/account/leagues/import', '/account/leagues/200'):
            response = self.client.post(path, data={'csrf_token': 'foreign', 'league_id': '200'})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['status'], 'csrf_rejected')
        self.assertEqual(snapshot(self.store), before)
        self.runtime.get.assert_not_called()

    def test_explicit_retry_can_import_after_supported_mapping_returns(self):
        self.initial()
        for discovered in (False, True):
            with self.subTest(discovered=discovered):
                self.no_membership = True
                self.assertEqual(self.reject(discovered).status_code, 200)
                self.no_membership = False
                response = self.reject(discovered)
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.headers['location'], '/')
                context = self.store.context_for_session(self.token)
                self.assertEqual(context.active_league_id, '200')
                self.assertEqual(context.controlled_roster_id, 2)
                self.assertEqual(len(self.store.memberships(self.account)), 2)

    def test_native_browser_both_forms_recovery_links_keyboard_and_phones(self):
        self.initial()
        before = snapshot(self.store)
        files = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in Path(self.folder.name).iterdir() if p.is_file()}
        hashes = files()
        rows = []
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            for discovered in (False, True):
                with self.subTest(width=width, discovered=discovered), self.browser(width, height) as page:
                    for destination, label in (('/account/leagues', 'Your leagues'),
                                               ('/account/sleeper', 'Review Sleeper identity')):
                        page.goto(self.origin + '/account/leagues', wait_until='networkidle')
                        if discovered:
                            page.get_by_role('heading', name='Second league', exact=True).locator('..').get_by_role('button', name='Add to DTOS', exact=True).click()
                        else:
                            page.get_by_label('Sleeper league ID', exact=True).fill('200')
                            page.get_by_role('button', name='Add to DTOS', exact=True).last.click()
                        page.get_by_role('heading', name='We found the league, but could not confidently match your team.', exact=True).wait_for()
                        action = page.get_by_role('link', name=label, exact=True)
                        self.assertEqual(action.get_attribute('href'), destination)
                        action.focus()
                        self.assertTrue(action.evaluate('e=>e===document.activeElement'))
                        self.assertGreaterEqual(float(action.evaluate('e=>parseFloat(getComputedStyle(e).outlineWidth)')), 2)
                        box = action.bounding_box()
                        self.assertGreaterEqual(box['height'], 44)
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        rows.append({'width': width, 'height': height, 'discovered': discovered,
                                     'action': label, 'bounds': box, 'overflow': False})
                        with page.expect_navigation(wait_until='networkidle'):
                            if destination.endswith('/sleeper'):
                                page.keyboard.press('Enter')
                            else:
                                action.click()
                        self.assertEqual(page.url, self.origin + destination)
                        if destination.endswith('/sleeper'):
                            self.assertTrue(page.get_by_label('Sleeper username', exact=True).is_visible())
                        else:
                            self.assertTrue(page.get_by_role('heading', name='First league', exact=True).is_visible())
        self.assertEqual(snapshot(self.store), before)
        self.assertEqual(files(), hashes)
        self.runtime.get.assert_not_called()
        if target := os.environ.get('DTOS_UNMATCHED_RECOVERY_EVIDENCE'):
            Path(target).write_text(json.dumps(rows, indent=2))
