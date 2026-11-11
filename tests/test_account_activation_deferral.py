"""Typed activation outcomes through real routes, restoration and ownership."""
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
from time import monotonic
import unittest
from unittest.mock import Mock, patch

from services import league_preparation as preparation
from src.core.league_runtime import LeagueRuntime, LeagueRuntimeError, RuntimeState
from src.platform import runtime_errors
from src.platform.lifecycle import HeavyWorkDeferred, lifecycle_coordinator
from tests import test_cold_league_recovery as cold
from tests.test_import_commissioner_integrity import snapshot
from tests.test_league_runtime import league_data

LIMIT = 2 * 1024**3


def record(name, observations, page=None):
    target = os.environ.get('DTOS_ACTIVATION_EVIDENCE')
    if not target:
        return
    path = Path(target)
    path.mkdir(parents=True, exist_ok=True)
    meta = dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                working_tree_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),
                physical_safari_tested=False, scope='Disposable authenticated native route/manager/guard controls; modeled telemetry identified, not live Granite',
                observations=observations)
    (path/(name+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
    if page:
        page.screenshot(path=str(path/(name+'.png')),full_page=True)


class ActivationDeferralHTTPTests(unittest.TestCase):
    upstream = cold.ColdLeagueRecoveryTests.upstream

    def setUp(self):
        cold.ColdLeagueRecoveryTests.setUp(self)
        self.store.activate(self.account,'100')
        self.path = Path(self.folder.name)/'prepared.json'
        self.path.write_text(json.dumps({'data':league_data('200'),'last_sync':datetime.now(timezone.utc).isoformat()}))
        self.enterContext(patch.object(preparation,'league_cache_file',return_value=self.path))
        self.hydrations = []
        async def hydrate(runtime):
            self.hydrations.append(runtime.league_id)
            if not await preparation.restore_cached_runtime_owned(runtime,lambda _:None,expected_season=2026):
                raise LeagueRuntimeError('private incompatible publication details')
            return runtime.state['data']
        self.manager._hydrator = hydrate

    def post(self,api=False):
        if api:
            return self.client.post('/api/account/active-league',json={'league_id':'200'},headers={'X-CSRF-Token':self.csrf})
        return self.client.post('/account/leagues/200/activate',data={'csrf_token':self.csrf},follow_redirects=False)

    def test_memory_deferral_stays_typed_in_html_and_api(self):
        before = snapshot(self.store)
        with patch.object(preparation,'memory_snapshot',return_value={'cgroup_current_bytes':LIMIT-200*1024**2,'cgroup_limit_bytes':LIMIT}), patch.object(preparation,'load_cache_json') as decode:
            html,api = self.post(),self.post(True)
            decode.assert_not_called()
        self.assertEqual((html.status_code,api.status_code),(503,503))
        self.assertIn('League preparation is waiting',html.text)
        self.assertNotIn('League preparation did not finish',html.text)
        self.assertIn('minute',html.text)
        self.assertIn('No Trade search',html.text)
        self.assertEqual((api.json()['status'],api.json()['code']),('deferred','league_preparation_waiting'))
        for response in (html,api):
            self.assertEqual(response.headers['retry-after'],'60')
            self.assertIn('no-store',response.headers['cache-control'])
            self.assertIn('private',response.headers['cache-control'])
        self.assertEqual(snapshot(self.store),before)
        self.assertEqual(self.hydrations,['200'])
        self.assertEqual(self.manager.resident('200').status,RuntimeState.DEFERRED)
        self.assertEqual(self.source_requests,[])
        record('typed-capacity',dict(html=503,api=api.json(),retry_after='60',modeled_headroom_bytes=200*1024**2,
               account_unchanged=True,source_requests=0,actual_hydrations=1))

    def test_cooldown_never_repeats_restoration_or_changes_account(self):
        before = snapshot(self.store)
        with patch.object(preparation,'memory_snapshot',return_value={'cgroup_current_bytes':LIMIT-200*1024**2,'cgroup_limit_bytes':LIMIT}), patch.object(preparation,'reclaim_unused_analytical_memory',return_value={}) as cleanup:
            first,second = self.post(),self.post()
        self.assertEqual((first.status_code,second.status_code),(503,503))
        self.assertEqual(second.headers.get('retry-after'),'60')
        self.assertEqual(self.hydrations,['200'])
        cleanup.assert_called_once_with()
        self.assertEqual(snapshot(self.store),before)

    def test_unknown_memory_and_real_lease_conflict_remain_deferred(self):
        before = snapshot(self.store)
        with patch.object(preparation,'memory_snapshot',return_value={}), patch.object(preparation,'load_cache_json') as decode, patch.object(preparation,'reclaim_unused_analytical_memory') as cleanup:
            response = self.post(True)
            decode.assert_not_called()
            cleanup.assert_not_called()
        self.assertEqual(response.json()['status'],'deferred')
        with patch('src.core.league_runtime.manager.monotonic',return_value=monotonic()+61), lifecycle_coordinator.phase('sleeper_sync'), patch.object(preparation,'load_cache_json') as decode:
            response = self.post(True)
            decode.assert_not_called()
        self.assertEqual(response.json()['status'],'deferred')
        self.assertEqual(self.manager.resident('200').status,RuntimeState.DEFERRED)
        self.assertEqual(snapshot(self.store),before)

    def test_real_safe_restore_and_explicit_retry_can_activate(self):
        with lifecycle_coordinator.phase('sleeper_sync'):
            self.assertEqual(self.post().status_code,503)
        with patch('src.core.league_runtime.manager.monotonic',return_value=monotonic()+61):
            response = self.post()
        self.assertEqual(response.status_code,303,response.text)
        self.assertEqual(self.store.context_for_session(self.token).active_league_id,'200')
        self.assertEqual(self.manager.resident('200').status,RuntimeState.WARM)
        self.assertEqual(self.manager.resident('200').state['data'],league_data('200'))
        self.assertEqual(self.hydrations,['200','200'])
        self.assertEqual(self.source_requests,[])
        record('real-recovery',dict(initial=503,explicit_retry=303,warm=True,source_values_preserved=True,source_requests=0,
               limitation='Small compatible fixture, actual enforced memory telemetry; not private Granite payload or live acceptance'))

    def test_incompatible_failure_stays_distinct_and_private(self):
        payload = json.loads(self.path.read_text())
        payload['data']['league']['league_id'] = '300'
        self.path.write_text(json.dumps(payload))
        before = snapshot(self.store)
        response = self.post(True)
        self.assertEqual(response.status_code,503)
        self.assertNotEqual(response.json()['status'],'deferred')
        self.assertNotIn('private incompatible',response.text)
        self.assertNotIn('retry-after',response.headers)
        self.assertEqual(self.manager.resident('200').status,RuntimeState.FAILED)
        self.assertEqual(snapshot(self.store),before)
        self.assertEqual(self.source_requests,[])

    def test_foreign_league_rejected_before_preparation(self):
        before = snapshot(self.store)
        response = self.client.post('/account/leagues/999/activate',data={'csrf_token':self.csrf})
        self.assertEqual(response.status_code,403)
        self.assertEqual(self.hydrations,[])
        self.assertEqual(snapshot(self.store),before)

    def test_cause_location_is_logged_without_exception_message(self):
        with patch.object(preparation,'memory_snapshot',return_value={}), self.assertLogs('dtos.request',level='WARNING') as logs:
            self.post()
        failures = [r for r in logs.records if getattr(r,'event',None)=='league_runtime_failure']
        self.assertEqual(len(failures),1)
        diag = failures[0].diagnostic
        self.assertEqual((diag['operation'],diag['exception_type']),('activation_deferred','HeavyWorkDeferred'))
        self.assertTrue(any(r['file']=='league_preparation.py' and r['function']=='restore_cached_runtime' for r in diag['frames']))
        self.assertNotIn('Saved league preparation',str(diag))
        self.assertNotIn(self.token,str(diag))


class AdmissionLogTests(unittest.TestCase):
    def test_final_existing_plan_and_actual_cleanup_counts_are_bounded(self):
        from src.platform.cache_restoration_admission import restoration_admission
        from src.platform.fois_admission import WORKING_RESERVE_BYTES,SAFETY_MARGIN_BYTES
        memory = dict(cgroup_current_bytes=1502986240,cgroup_limit_bytes=LIMIT,cgroup_anonymous_bytes=875569152,
                      cgroup_inactive_file_bytes=599330816,secret='private source payload')
        plan = restoration_admission(35839104,memory,False,fois_working_bytes=WORKING_RESERVE_BYTES,fois_safety_bytes=SAFETY_MARGIN_BYTES)
        recovery = dict(attempted=True,before_bytes=1503500000,after_bytes=1502986240,expired_entries=0,
                        idle_worker_retired=False,allocator_trimmed=True,secret='private cleanup detail')
        with self.assertLogs('dtos.request',level='INFO') as logs:
            runtime_errors.log_restoration_admission(file_bytes=35839104,memory=memory,plan=plan,recovery=recovery)
        self.assertEqual(len(logs.records),1)
        diag = logs.records[0].diagnostic
        self.assertEqual(diag['reason'],'insufficient_headroom')
        self.assertEqual(diag['required_bytes'],707643392)
        self.assertEqual(diag['headroom_bytes'],LIMIT-memory['cgroup_current_bytes'])
        self.assertEqual(diag['cleanup']['expired_entries'],0)
        self.assertEqual(diag['cleanup']['before_bytes'],recovery['before_bytes'])
        self.assertEqual(diag['cleanup']['after_bytes'],recovery['after_bytes'])
        self.assertFalse(diag['would_admit'])
        self.assertNotIn('private',json.dumps(diag))
        self.assertNotIn('secret',json.dumps(diag))
        self.assertLess(len(json.dumps(diag)),2048)

    def test_unknown_inputs_remain_unknown(self):
        with self.assertLogs('dtos.request',level='INFO') as logs:
            runtime_errors.log_restoration_admission(file_bytes=True,memory={'cgroup_current_bytes':True},plan={'reason':'private reason'})
        diag = logs.records[0].diagnostic
        for key in ['file_bytes','current_bytes','would_admit','reason']:
            self.assertIsNone(diag[key])
        self.assertFalse(diag['cleanup']['attempted'])
        self.assertIsNone(diag['cleanup']['expired_entries'])

    def test_known_negative_headroom_is_preserved(self):
        with self.assertLogs('dtos.request',level='INFO') as logs:
            runtime_errors.log_restoration_admission(file_bytes=0,memory={},plan={'headroom_bytes':-1,'reason':'insufficient_headroom','would_admit':False})
        self.assertEqual(logs.records[0].diagnostic['headroom_bytes'],-1)

    def test_optional_sink_failure_cannot_change_admission(self):
        from tests import test_league_entry_coordination as entry
        helper = entry.CachedPublicationTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        with patch.object(preparation,'memory_snapshot',return_value={}), patch.object(logging.getLogger('dtos.request'),'info',side_effect=OSError('sink unavailable')), patch.object(preparation,'load_cache_json') as decode:
            with self.assertRaises(HeavyWorkDeferred):
                preparation.restore_cached_runtime(LeagueRuntime('200'),Mock())
            decode.assert_not_called()


class ActivationDeferralPhoneTests(unittest.TestCase):
    setUp = cold.ColdLeagueRecoveryTests.setUp
    upstream = cold.ColdLeagueRecoveryTests.upstream

    def test_normal_form_is_accessible_and_never_retries_automatically(self):
        self.store.activate(self.account,'100')
        self.discovery_failed = True
        path = Path(self.folder.name)/'phone-cache.json'
        path.write_text(json.dumps({'data':league_data('200'),'last_sync':datetime.now(timezone.utc).isoformat()}))
        self.enterContext(patch.object(preparation,'league_cache_file',return_value=path))
        before = snapshot(self.store)
        rows = []
        with lifecycle_coordinator.phase('sleeper_sync'):
            for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                with cold.onboarding.PublicOnboardingTests.browser(self,width,height) as page:
                    page.goto(self.origin+'/account/leagues',wait_until='networkidle')
                    requests_before = list(self.source_requests)
                    with page.expect_response(lambda r:'/account/leagues/200/activate' in r.url and r.request.method=='POST') as posted:
                        page.locator('form[action="/account/leagues/200/activate"] button').click()
                    page.wait_for_load_state('networkidle')
                    self.assertEqual(posted.value.status,503)
                    self.assertEqual(posted.value.headers.get('retry-after'),'60')
                    self.assertTrue(page.get_by_role('heading',name='League preparation is waiting').is_visible())
                    self.assertNotIn('League preparation did not finish',page.locator('body').inner_text())
                    self.assertIn('No Trade search',page.locator('body').inner_text())
                    link = page.get_by_role('link',name='Your leagues',exact=True)
                    self.assertGreaterEqual(link.bounding_box()['height'],44)
                    link.focus()
                    self.assertNotEqual(link.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                    self.assertEqual(self.source_requests,requests_before)
                    self.assertEqual(snapshot(self.store),before)
                    row=dict(viewport=[width,height],status=503,retry_after='60',no_overflow=True,no_new_source_requests=True,account_unchanged=True)
                    rows.append(row)
                    record('phone-'+str(width),row,page)
                    link.press('Enter')
                    page.wait_for_load_state('networkidle')
                    self.assertTrue(page.get_by_role('heading', name='Your leagues', exact=True).is_visible())
                    self.assertEqual(snapshot(self.store),before)
        record('browser',rows)
