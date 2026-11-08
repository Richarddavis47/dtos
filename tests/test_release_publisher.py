"""Fail-closed release admission and byte integrity, without remote mutations."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.release import publish as p


class ArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.plan = dict(candidate='a' * 40, tree='b' * 40, canonical_entries=3, local_canonical_entries=3, canonical_tests=2, python_version='3.14.3')
        result = dict(head=self.plan['candidate'], tree=self.plan['tree'], passed=True, exit_code=0,
                      cgroup_limit=2147483648, cpus=2, network='none', python='3.14.3 (fixture)',
                      final_memory={'cgroup_memory_events': {'oom_kill': 0}})
        events = [{'event': x} for x in ['start', 'stop', 'start', 'stop']]
        trace = [{'event': 'validation_child_completed', 'return_code': 0} for _ in range(10)]
        trace.append({'event': 'validator_final_summary', 'gates': 10})
        self.files = {'result.json': json.dumps(result).encode(),
                      'tests.jsonl': '\n'.join(map(json.dumps, events)).encode(),
                      'canonical-trace.jsonl': '\n'.join(map(json.dumps, trace)).encode()}

    def archive(self, alter=None):
        files = copy.deepcopy(self.files)
        if alter:
            alter(files)
        manifest = [{'name': n, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
                    for n, b in files.items()]
        files['manifest.json'] = json.dumps(manifest).encode()
        files['SHA256SUMS'] = ''.join(row['sha256']+'  '+row['name']+'\n' for row in manifest).encode()
        path = self.root / 'evidence.zip'
        p.make_zip(path, files)
        return path

    def local_files(self):
        files = copy.deepcopy(self.files)
        files['manifest.json'] = json.dumps([
            dict(name=n, bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
            for n, b in files.items()
        ]).encode()
        files['SHA256SUMS'] = ''.join(row['sha256']+'  '+row['name']+'\n' for row in json.loads(files['manifest.json'])).encode()
        return {'local-canonical/' + n: b for n, b in files.items()}

    def test_canonical_checksum_sidecar_cannot_disagree_with_manifest(self):
        path = self.archive()
        with zipfile.ZipFile(path) as archive:
            files = {n:archive.read(n) for n in archive.namelist()}
        files['SHA256SUMS'] = b'0' * 64 + b'  tests.jsonl\n'
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            p.verify_canonical(path, self.plan)

    def test_local_checksum_sidecar_is_required(self):
        files = self.local_files()
        del files['local-canonical/SHA256SUMS']
        path = self.root / 'recovery.zip'
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, 'checksum list missing'):
            p.verify_local_recovery(path, self.plan)

    def test_complete_source_pinned_evidence(self):
        self.assertTrue(p.verify_canonical(self.archive(), self.plan)['passed'])

    def test_prior_attempts_require_their_own_source_association_and_payload_manifest(self):
        for mutation in ('none', 'source', 'scope', 'payload', 'extra', 'duplicate'):
            with self.subTest(mutation=mutation):
                payload = b'Original failed attempt, not a passing gate.'
                entry = dict(name='prior-local/failed.log', bytes=len(payload),
                             sha256=hashlib.sha256(payload).hexdigest())
                meta = dict(candidate=self.plan['candidate'], tree=self.plan['tree'],
                            scope='prior-attempts-only', files=[entry])
                files = {entry['name']: payload}
                if mutation == 'source':
                    meta['candidate'] = 'wrong'
                if mutation == 'scope':
                    meta['scope'] = 'final-validation'
                if mutation == 'payload':
                    files[entry['name']] += b'changed'
                if mutation == 'extra':
                    files['unlisted.log'] = b'unlisted'
                if mutation == 'duplicate':
                    meta['files'].append(entry.copy())
                files['prior-manifest.json'] = json.dumps(meta).encode()
                target = self.root / 'prior.zip'
                p.make_zip(target, files)
                plan = self.plan | {'prior_evidence_sha256': p.digest(target)}
                if mutation == 'none':
                    p.verify_prior_evidence(target, plan)
                else:
                    with self.assertRaises(RuntimeError):
                        p.verify_prior_evidence(target, plan)

    def test_prior_archive_hash_cannot_be_substituted(self):
        target = self.archive()
        with self.assertRaisesRegex(RuntimeError, 'archive changed'):
            p.verify_prior_evidence(target, self.plan | {'prior_evidence_sha256': '0' * 64})

    def test_wrong_source_and_resource_limit_fail(self):
        for field, value in [('head', 'c' * 40), ('tree', 'd' * 40), ('cgroup_limit', 0), ('passed', False)]:
            with self.subTest(field=field):
                def alter(files):
                    result = json.loads(files['result.json'])
                    result[field] = value
                    files['result.json'] = json.dumps(result).encode()
                with self.assertRaises(RuntimeError):
                    p.verify_canonical(self.archive(alter), self.plan)

    def test_failure_skip_and_incomplete_tests_fail(self):
        for events in [[{'event': 'start'}], [{'event': 'failure'}], [{'event': 'skip'}]]:
            with self.subTest(events=events), self.assertRaises(RuntimeError):
                p.verify_canonical(self.archive(lambda f: f.update({'tests.jsonl': '\n'.join(map(json.dumps, events)).encode()})), self.plan)

    def test_missing_gate_completion_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'gate execution'):
            p.verify_canonical(self.archive(lambda f: f.update({'canonical-trace.jsonl': b'{"event":"validator_final_summary","gates":10}'})), self.plan)

    def test_payload_changed_after_manifest_fails(self):
        path = self.archive()
        with zipfile.ZipFile(path) as z:
            files = {n: z.read(n) for n in z.namelist()}
        files['tests.jsonl'] += b'\n'
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            p.verify_canonical(path, self.plan)

    def test_path_escape_and_symlink_fail(self):
        for name in ['../escape', '/absolute', 'dir\\escape']:
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                p.make_zip(self.root / 'bad.zip', {name: b'bad'})
        path = self.root / 'link.zip'
        with zipfile.ZipFile(path, 'w') as z:
            info = zipfile.ZipInfo('link')
            info.external_attr = 0o120777 << 16
            z.writestr(info, '/outside')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            p.verify_zip(path)

    def test_credential_shaped_payload_holds_publication(self):
        with self.assertRaisesRegex(RuntimeError, 'Credential'):
            p.make_zip(self.root / 'secret.zip', {'secret.log': b'ghp_' + b'X' * 36})

    def test_complete_local_validation_is_required_in_recovery(self):
        path = self.root / 'recovery.zip'
        p.make_zip(path, self.local_files())
        self.assertTrue(p.verify_local_recovery(path, self.plan)['passed'])

    def test_incomplete_local_validation_holds_publication(self):
        path = self.root / 'recovery.zip'
        files = self.local_files()
        files['local-canonical/tests.jsonl'] = b'{"event":"start"}'
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, 'Local regression incomplete'):
            p.verify_local_recovery(path, self.plan)

    def test_local_manifest_and_every_payload_are_required(self):
        for mutation in ('missing','population','payload'):
            files = self.local_files()
            plan = self.plan.copy()
            if mutation == 'missing':
                del files['local-canonical/manifest.json']
            elif mutation == 'population':
                plan['local_canonical_entries'] = 99
            else:
                files['local-canonical/tests.jsonl'] += b'\n'
            path = self.root / 'recovery.zip'
            p.make_zip(path, files)
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                p.verify_local_recovery(path, plan)

    def test_older_python_cannot_replace_production_canonical(self):
        def alter(files):
            result = json.loads(files['result.json'])
            result['python'] = '3.12.3 (older local runtime)'
            files['result.json'] = json.dumps(result).encode()
        with self.assertRaisesRegex(RuntimeError, 'Python runtime mismatch'):
            p.verify_canonical(self.archive(alter), self.plan)

    def test_older_python_cannot_replace_local_canonical(self):
        files = self.local_files()
        result = json.loads(files['local-canonical/result.json'])
        result['python'] = '3.12.3 (older local runtime)'
        files['local-canonical/result.json'] = json.dumps(result).encode()
        path = self.root / 'recovery.zip'
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, 'Python runtime mismatch'):
            p.verify_local_recovery(path, self.plan)


class RemoteAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.expected = {'proof.json': (12, 'a' * 64)}
        self.release = {'assets': [dict(name='proof.json', state='uploaded', size=12, digest='sha256:' + 'a' * 64)]}

    def test_exact_readback_metadata(self):
        self.assertEqual(set(p.verify_remote_assets(self.release, self.expected, True)), {'proof.json'})

    def test_missing_partial_unexpected_duplicate_and_corrupt_assets(self):
        p.verify_remote_assets({'assets': []}, self.expected, False)
        for release in [{'assets': []}, {'assets': self.release['assets'] * 2},
                        {'assets': [dict(self.release['assets'][0], digest='sha256:' + 'b' * 64)]},
                        {'assets': [dict(self.release['assets'][0], name='other')]},
                        {'assets': [dict(self.release['assets'][0], state='new')]}]:
            with self.subTest(release=release), self.assertRaises(RuntimeError):
                p.verify_remote_assets(release, self.expected, True)

    def test_log_escape_bytes_are_retained_in_file_only(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(p.subprocess, 'run') as run:
            p.download('repos/owner/repo/actions/jobs/1/logs', Path(folder) / 'log')
            self.assertIn('--allow-escape-sequences', run.call_args.args[0])
            self.assertIsNotNone(run.call_args.kwargs['stdout'])
            p.download('repos/owner/repo/actions/artifacts/2/zip', Path(folder) / 'zip')
            self.assertNotIn('--allow-escape-sequences', run.call_args.args[0])


class ContextAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(Path('.github/release-plans/2240.json').read_text())
        self.publisher = 'c' * 40
        self.merge = 'd' * 40
        self.env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=self.plan['repository'],
                        GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_ACTOR=self.plan['actor'],
                        GITHUB_REF=self.plan['publisher_ref'], GITHUB_SHA=self.publisher, GITHUB_RUN_ID='99')
        self.pr = dict(base={'ref': 'main', 'repo': {'full_name': self.plan['repository']}},
                       head={'repo': {'full_name': self.plan['repository']}, 'sha': self.plan['candidate'], 'ref': self.plan['source_branch']},
                       state='open', merged=False, merged_at=None, merge_commit_sha=None)
        self.current_main = self.plan['baseline']
        self.tree = self.plan['tree']
        self.merge_tree = self.plan['tree']
        self.changes = 'tools/release/publish.py'

    def api(self, path):
        if '/git/ref/heads/release/' in path:
            return {'object': {'sha': self.publisher}}
        if path.endswith('/git/ref/heads/main'):
            return {'object': {'sha': self.current_main}}
        if '/actions/runs/' in path:
            return {'head_sha': self.publisher, 'event': 'workflow_dispatch', 'path': '.github/workflows/canonical-release-recovery.yml'}
        if '/pulls/' in path:
            return self.pr
        if '/releases/tags/' in path:
            return {'immutable': True, 'draft': False}
        self.fail('Unexpected API ' + path)

    def command(self, *args):
        if args[1:3] == ('rev-parse', 'HEAD'):
            return self.publisher
        if args[1] == 'diff':
            return self.changes
        if args[1] == 'rev-parse':
            return self.merge_tree if args[2].startswith(self.merge) else self.tree
        if args[1] == 'show':
            return f'VERSION = "{self.plan["version"]}"\nBUILD_NUMBER = {self.plan["build"]}\n'
        self.fail('Unexpected command')

    def check(self, operation):
        with patch.dict(os.environ, self.env), patch.object(p, 'api', side_effect=self.api), \
             patch.object(p, 'command', side_effect=self.command), patch.object(p.subprocess, 'run'):
            return p.verify_context(self.plan, operation)

    def test_prepare_accepts_only_unchanged_open_candidate(self):
        self.check('prepare')

    def test_publish_refuses_unmerged_candidate(self):
        with self.assertRaisesRegex(RuntimeError, 'merged at current main'):
            self.check('publish')

    def test_merged_identical_tree_is_required(self):
        self.pr.update(merged=True, merged_at='2026-11-01', merge_commit_sha=self.merge)
        self.current_main = self.merge
        self.check('publish')
        self.merge_tree = 'e' * 40
        with self.assertRaisesRegex(RuntimeError, 'Merged application differs'):
            self.check('publish')

    def test_advanced_main_does_not_publish_old_merge(self):
        self.pr.update(merged=True, merged_at='2026-11-01', merge_commit_sha=self.merge)
        self.current_main = 'e' * 40
        with self.assertRaisesRegex(RuntimeError, 'merged at current main'):
            self.check('publish')

    def test_candidate_revision_change_is_rejected(self):
        self.pr['head']['sha'] = 'e' * 40
        with self.assertRaisesRegex(RuntimeError, 'Candidate PR changed'):
            self.check('prepare')

    def test_wrong_actor_event_ref_and_repository_fail(self):
        for key in ['GITHUB_ACTOR', 'GITHUB_EVENT_NAME', 'GITHUB_REF', 'GITHUB_REPOSITORY']:
            original = self.env[key]
            self.env[key] = 'untrusted'
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.check('prepare')
            self.env[key] = original

    def test_tooling_branch_cannot_smuggle_application_changes(self):
        self.changes = 'src/platform/fois_admission.py'
        with self.assertRaisesRegex(RuntimeError, 'application changes'):
            self.check('prepare')

    def test_rejected_context_has_no_upload_or_tag_side_effect(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(p, 'verify_context', side_effect=RuntimeError('unmerged')), \
             patch.object(p, 'collect') as collect, patch.object(p, 'api') as api:
            with self.assertRaisesRegex(RuntimeError, 'unmerged'):
                p.prepare_or_publish(self.plan, Path(folder), 'publish')
            collect.assert_not_called()
            api.assert_not_called()


class RunAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(Path('.github/release-plans/2240.json').read_text())
        self.plan['runs'] = [run | {'id':100000+index*1000} for index,run in enumerate(self.plan['runs'])]
        self.checks = [dict(name=name, head_sha=self.plan['candidate'], status='completed', conclusion='success', app={'slug': 'github-actions'})
                       for run in self.plan['runs'] for name in run['jobs']]
        self.bad_source = False

    def api(self, path):
        if '/check-runs?' in path:
            return {'check_runs': self.checks}
        run = next(x for x in self.plan['runs'] if str(x['id']) in path)
        if '/jobs?' in path:
            return {'jobs': [dict(name=n, status='completed', conclusion='success', id=i + run['id']) for i, n in enumerate(run['jobs'])]}
        return dict(head_sha='wrong' if self.bad_source else self.plan['candidate'], head_repository={'full_name': self.plan['repository']},
                    event='pull_request', path=run['path'], name=run['name'], status='completed', conclusion='success')

    def test_exact_thirteen_jobs_are_required(self):
        with patch.object(p, 'api', side_effect=self.api):
            records, product = p.verify_runs(self.plan)
        self.assertEqual(len(records), 13)
        self.assertIsNotNone(product)

    def test_later_failed_missing_and_wrong_source_checks_reject(self):
        for change in ['failed', 'missing', 'source']:
            with self.subTest(change=change):
                original = copy.deepcopy(self.checks)
                if change == 'failed':
                    self.checks[0]['conclusion'] = 'failure'
                elif change == 'missing':
                    self.checks.pop()
                else:
                    self.checks[0]['head_sha'] = 'wrong'
                with patch.object(p, 'api', side_effect=self.api), self.assertRaisesRegex(RuntimeError, 'Latest required check'):
                    p.verify_runs(self.plan)
                self.checks = original

    def test_successful_run_from_another_commit_is_rejected(self):
        self.bad_source = True
        with patch.object(p, 'api', side_effect=self.api), self.assertRaisesRegex(RuntimeError, 'run source mismatch'):
            p.verify_runs(self.plan)

    def test_publish_cannot_omit_preparation_certificate(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(p, 'api') as api:
            with self.assertRaisesRegex(RuntimeError, 'explicit successful preparation'):
                p.verify_preparation(self.plan, Path(folder), {}, None)
            api.assert_not_called()


class TradeResourceIntegrityTests(unittest.TestCase):
    def test_exact_source_and_complete_real_work_are_required(self):
        plan = {'candidate': 'a'*40, 'tree': 'b'*40}
        valid = dict(head=plan['candidate'], tree=plan['tree'], passed=True, complete=True,
            kernel_peak=2_000_000_000, working_tree_clean=True, cleanup={'harness_scratch_exists_after': False, 'trade_lease_available': True}, one_qb_http_evaluation={'passed': True},
            operations=[{'full_evaluations': 180, 'business_digest': 'same'}]*2,
            actual_cancel={'evaluations_started': 1},
            file_cache_recovery={'completed_evaluations': 180, 'content_still_valid': True},
            states=[{'cgroup_limit_bytes': 2147483648, 'cgroup_memory_events': {'oom':0, 'oom_kill':0}}],
            liveness=[{'milliseconds': 20, 'server_duration_ms': 20, 'client_elapsed_ms': 30}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'trade.zip'
            for update in ({}, {'head': 'wrong'}, {'complete': False}, {'kernel_peak': 2147483649},
                           {'operations': []}, {'working_tree_clean': False}, {'cleanup': {}}, {'liveness': [{'milliseconds':501}]}):
                files = {'result.json': json.dumps(valid | update).encode(), 'raw.log': b'controlled', 'preparation.log': b'fixture'}
                files['SHA256SUMS'] = ''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in files.items()).encode()
                p.make_zip(path, files)
                if update:
                    with self.assertRaises(RuntimeError):
                        p.verify_trade_resource(path, plan)
                else:
                    self.assertTrue(p.verify_trade_resource(path, plan)['passed'])


class LeagueEntryIntegrityTests(unittest.TestCase):
    def test_handoff_requires_exact_source_and_no_credentials(self):
        plan = {'candidate':'a'*40,'tree':'b'*40}
        body = (plan['candidate']+' '+plan['tree']).encode()
        self.assertEqual(p.verify_handoff(body,plan),body)
        for bad in (b'old source',body+b'ghp_'+b'X'*40,b'X'*(128*1024+1)):
            with self.assertRaises(RuntimeError):
                p.verify_handoff(bad,plan)

    def test_real_execution_deferral_recovery_ownership_and_liveness_are_required(self):
        plan = {'candidate':'a'*40, 'tree':'b'*40}
        labels = ['active_fois_worker','before_large_restore_with_fois','after_large_restore_with_fois',
                  'unsafe_pressure','active_fois_outstanding_reserve','same_pressure_after_fois_release',
                  'pressure_relieved','recovered_restore','cleanup']
        valid = dict(head=plan['candidate'],tree=plan['tree'],passed=True,complete=True,working_tree_clean=True,
            warm_cold_saved_http='passed', one_qb_k_def_http_evaluation='passed',pressure_deferred=True,
            recovery_completed=True,worker_reaped=True,cgroup_lifetime_peak=2_000_000_000,
            active_fois_commitment_deferred=True,after_fois_release_same_pressure_completed=True,
            samples=[dict(label=n,cgroup_limit_bytes=2147483648,cgroup_current_bytes=1_000_000_000,
                          cgroup_memory_events={'oom':0,'oom_kill':0}) for n in labels],
            liveness=[{'server_ms':20,'client_ms':30}]*5)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'entry.zip'
            for update in ({}, {'head':'wrong'}, {'complete':False}, {'working_tree_clean':False},
                           {'pressure_deferred':False}, {'recovery_completed':False}, {'worker_reaped':False},
                           {'active_fois_commitment_deferred':False}, {'after_fois_release_same_pressure_completed':False},
                           {'one_qb_k_def_http_evaluation':'deferred'}, {'samples':[]}, {'liveness':[]},
                           {'cgroup_lifetime_peak':2147483649}):
                files={'result.json':json.dumps(valid|update).encode(),'raw.log':b'controlled','preparation.log':b'fixture'}
                files['SHA256SUMS']=''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in files.items()).encode()
                p.make_zip(target,files)
                if update:
                    with self.assertRaises(RuntimeError):
                        p.verify_league_entry(target,plan)
                else:
                    self.assertTrue(p.verify_league_entry(target,plan)['passed'])


class PreflightIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name) / 'preflight.zip'
        self.plan = {'candidate': 'a' * 40, 'tree': 'b' * 40}
        self.result = dict(head=self.plan['candidate'], tree=self.plan['tree'], passed=True, complete=True,
            enforced_limit=2147483648, swap_limit=0, kernel_peak_bytes=2000000000,
            scratch_removed=True, children_after=[], runtime_population_unchanged=True,
            no_private_payload_decoded=True, guarded_operation_calls=[0] * 5,
            final_memory={'cgroup_limit_bytes':2147483648, 'cgroup_memory_events':{'oom':0,'oom_kill':0}},
            cases=[], liveness=[])
        for name, verdict, reserved, raw_mib, padding in (
            ('healthy', 'would_admit', False, 900, 0),
            ('capacity_deferred', 'would_defer', False, 1800, 1000000000),
            ('pressure_relieved', 'would_admit', False, 900, 0),
            ('fois_reserve_protected', 'would_defer', True, 1150, 500000000),
            ('fois_released_same_pressure', 'would_admit', False, 1150, 500000000),
        ):
            working = 16 * 23048708
            safety, fois = (256 * 1024**2, 512 * 1024**2) if reserved else (128 * 1024**2, 0)
            response = dict(verdict=verdict, reason='sufficient_headroom' if verdict == 'would_admit' else 'insufficient_headroom',
                advisory_only=True, non_atomic=True, recheck_required=True,
                assessment_scope='saved_cache_resource_and_coordination_admission_only',
                process={'pid':123,'lifecycle_scope':'serving_process_only','other_worker_idleness':'not_established'},
                cache={'size_bytes':23048708,'generation_pinned':True,'path_matches_pinned_generation_at_end':True,
                       'payload_readability':'not_checked','content_compatibility':'not_evaluated'},
                lifecycle={'available':True,'cache_lease_conflict':False,'heavy_work':{'fois_generation':reserved}},
                memory={'scope':'shared_container','cgroup_limit_bytes':2147483648,'cgroup_current_bytes':raw_mib*1024**2,
                        'memory_events':{'oom':0,'oom_kill':0}},
                capacity={'telemetry_valid':True,'working_bytes':working,'safety_bytes':safety,'fois_working_bytes':fois,
                          'required_bytes':working+safety+fois,'effective_limit_bytes':2147483648,
                          'headroom_bytes':2147483648-raw_mib*1024**2,'would_admit':verdict=='would_admit'})
            self.result['cases'].append({'name':name,'response':response,'harness_padding_bytes':padding})
            self.result['liveness'].append({'case':name,'server_ms':10,'client_ms':15})

    def write(self, result=None, *, corrupt_checksum=False):
        files = {'result.json':json.dumps(result or self.result).encode(), 'raw.log':b'Fixture-only original observer log.'}
        files['SHA256SUMS'] = ''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in files.items()).encode()
        if corrupt_checksum:
            files['raw.log'] += b'changed'
        p.make_zip(self.target, files)
        return self.target

    def test_exact_five_case_metadata_acceptance(self):
        self.assertTrue(p.verify_preflight(self.write(), self.plan)['passed'])

    def test_source_resource_cleanup_and_completion_are_required(self):
        for update in ({'head':'old'}, {'tree':'other'}, {'passed':False}, {'complete':False},
                       {'enforced_limit':0}, {'swap_limit':1}, {'kernel_peak_bytes':2147483649},
                       {'scratch_removed':False}, {'children_after':[99]}, {'runtime_population_unchanged':False},
                       {'no_private_payload_decoded':False}, {'guarded_operation_calls':[0,0,1,0,0]},
                       {'final_memory':{'cgroup_limit_bytes':2147483648,'cgroup_memory_events':{'oom_kill':1}}},
                       {'cases':[]}, {'liveness':[]}):
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(self.result | update), self.plan)

    def test_advisory_scope_compatibility_and_reservations_are_required(self):
        for field, key, value in (
            ('process','lifecycle_scope','whole_service'), ('process','other_worker_idleness','idle'),
            ('cache','size_bytes',1), ('cache','generation_pinned',False),
            ('cache','path_matches_pinned_generation_at_end',False),
            ('cache','content_compatibility','verified'), ('cache','payload_readability','read'),
            ('lifecycle','cache_lease_conflict',True), ('lifecycle','available',False),
            ('memory','scope','process_only'), ('capacity','required_bytes',1),
            ('capacity','effective_limit_bytes',4294967296), ('capacity','working_bytes',1),
        ):
            data = copy.deepcopy(self.result)
            data['cases'][0]['response'][field][key] = value
            with self.subTest(field=field,key=key), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(data), self.plan)
        for key in ('advisory_only','non_atomic','recheck_required'):
            data = copy.deepcopy(self.result)
            data['cases'][0]['response'][key] = False
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(data), self.plan)

    def test_fois_recovery_requires_same_pressure_and_live_reservation(self):
        for change in ('pressure','reservation','verdict','duplicate','liveness','oom'):
            data = copy.deepcopy(self.result)
            if change == 'pressure':
                data['cases'][4]['harness_padding_bytes'] = 0
            if change == 'reservation':
                data['cases'][3]['response']['lifecycle']['heavy_work']['fois_generation'] = False
            if change == 'verdict':
                data['cases'][1]['response']['verdict'] = 'would_admit'
            if change == 'duplicate':
                data['cases'][4]['name'] = 'healthy'
            if change == 'liveness':
                data['liveness'][0]['server_ms'] = 500
            if change == 'oom':
                data['cases'][0]['response']['memory']['memory_events']['oom'] = 1
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(data), self.plan)

    def test_changed_original_payload_holds_preflight(self):
        with self.assertRaisesRegex(RuntimeError,'checksum'):
            p.verify_preflight(self.write(corrupt_checksum=True),self.plan)


class CurrentHistoryArtifactTests(unittest.TestCase):
    def test_only_complete_exact_source_browser_evidence_is_accepted(self):
        plan = dict(candidate='a' * 40, tree='b' * 40)
        rows = [dict(league_control=league, width=w, height=h,
                     retrieved=[1, 2, 3, 5, 6, 7, 8], failed=[4], keyboard=True,
                     touch_emulated=w < 1000, overflow=False, extra_disclosure_requests=0)
                for league in ('Granite-shaped', 'Day-shaped', 'Arkham-shaped')
                for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))]
        report = dict(head=plan['candidate'], tree=plan['tree'], working_tree_clean=True, records=rows)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'current-history.zip'
            for change in ('control', 'source', 'dirty', 'missing', 'duplicate', 'coverage',
                           'failure', 'keyboard', 'touch', 'overflow', 'requests', 'screenshots'):
                with self.subTest(change=change):
                    data = copy.deepcopy(report)
                    if change == 'source':
                        data['tree'] = 'c' * 40
                    if change == 'dirty':
                        data['working_tree_clean'] = False
                    if change == 'missing':
                        data['records'].pop()
                    if change == 'duplicate':
                        data['records'][-1] = data['records'][0]
                    for key, field, value in (('coverage', 'retrieved', [1]), ('failure', 'failed', []),
                                              ('keyboard', 'keyboard', False), ('touch', 'touch_emulated', False),
                                              ('overflow', 'overflow', True), ('requests', 'extra_disclosure_requests', 1)):
                        if change == key:
                            data['records'][0][field] = value
                    files = {'browser.json': json.dumps(data).encode()}
                    files.update({str(i) + '.png': b'\x89PNG\r\n\x1a\n' for i in range(12)})
                    if change == 'screenshots':
                        del files['0.png']
                    p.make_zip(path, files)
                    if change == 'control':
                        self.assertEqual(p.verify_current_history(path, plan), report)
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_current_history(path, plan)


class HistoryFollowThroughArtifactTests(unittest.TestCase):
    def test_exact_source_complete_chain_context_and_cleanup_are_required(self):
        plan = dict(candidate='a'*40, tree='b'*40)
        h = '/history/team/100:franchise:4'
        root = '/trades/history/1234'
        pick = '/picks/PICK-2026-R2-ORIG7?from_trade=1234'
        player = '/players/13346?from_trade=1234'
        later = '/trades/history/5678?from_trade=1234'
        chain = [h,h+'?events_page=2',root,pick,player,later,root,later,player,pick,root,
                 h+'?events_page=2',h,h+'?events_page=2',h+'?events_page=2','/history/team/200:franchise:1']
        rows=[]
        for w,hgt in ((320,432),(375,667),(390,844),(1280,900)):
            rows.extend([dict(control='Day retained chain plus disposable pagination',width=w,height=hgt,
                chain=chain,original='1234',pick='PICK-2026-R2-ORIG7',later='5678',keyboard=True,
                touch_emulated=w<500,overflow=False,extra_disclosure_requests=0,pagination_return=True,forward_reload=True),
                dict(control='Arkham retained history and scope reset',width=w,height=hgt,
                     overflow=False,source_qualified=True,old_league_replay=False)])
        report=dict(head=plan['candidate'],tree=plan['tree'],working_tree_clean=True,records=rows,
                    errors=[],server_thread_reaped=True,
                    requests=[dict(path='/api/account/navigation-context',status=200)])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'history.zip'
            for change in ('control','source','dirty','missing','duplicate','chain','origin','pagination',
                           'reload','scope','browser-error','cleanup','heavy-request','context','screenshots'):
                with self.subTest(change=change):
                    data=copy.deepcopy(report)
                    if change=='source':
                        data['tree']='c'*40
                    if change=='dirty':
                        data['working_tree_clean']=False
                    if change=='missing':
                        data['records'].pop()
                    if change=='duplicate':
                        data['records'][-1]=data['records'][0]
                    if change=='chain':
                        data['records'][0]['chain'][11]='/league'
                    if change=='origin':
                        data['records'][0]['original']='9999'
                    if change=='pagination':
                        data['records'][0]['pagination_return']=False
                    if change=='reload':
                        data['records'][0]['forward_reload']=False
                    if change=='scope':
                        data['records'][1]['old_league_replay']=True
                    if change=='browser-error':
                        data['errors']=['failed']
                    if change=='cleanup':
                        data['server_thread_reaped']=False
                    if change=='heavy-request':
                        data['requests'].append(dict(path='/sync',status=200))
                    if change=='context':
                        data['requests']=[]
                    files={'browser.json':json.dumps(data).encode()}
                    files.update({str(i)+'.png':b'\x89PNG\r\n\x1a\n' for i in range(8)})
                    if change=='screenshots':
                        del files['0.png']
                    p.make_zip(path,files)
                    if change=='control':
                        self.assertEqual(p.verify_history_followthrough(path,plan),report)
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_history_followthrough(path,plan)


class MarketHistoryArtifactTests(unittest.TestCase):
    def test_complete_cache_transition_compatibility_and_cleanup_required(self):
        plan = dict(candidate='a'*40, tree='b'*40)
        memory = dict(cgroup_limit_bytes=2147483648, cgroup_memory_events=dict(oom=0, oom_kill=0))
        rows = [dict(league=league, viewport=[w, h], before=dict(magnitude=100, checkpoint_count=2),
                     updated=dict(magnitude=120, checkpoint_count=3,
                                  comparison_start_at='2026-06-01T12:00:00Z',
                                  comparison_end_at='2026-08-31T12:00:00+00:00',
                                  comparison_scope='historical_to_current', comparison_units='0-1000', confidence='low'),
                     boundary=dict(magnitude=None, checkpoint_count=4, direction='not_comparable',
                                   comparison_reasons=['INCOMPATIBLE_OBSERVATION_BOUNDARY']),
                     price_publication_unchanged=True, overflow=False, keyboard=True,
                     disclosure_extra_requests=0, source_catalogue_not_participation=True)
                for league in ('1314695233040052224', '1319750579458686976')
                for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))]
        report = dict(head=plan['candidate'], tree=plan['tree'], working_tree_clean=True,
                      records=rows, errors=[], browser_closed=True,
                      before_memory=memory, after_memory=memory,
                      requests=[dict(path='/market?selected=player%3A1', status=200)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'market.zip'
            for change in ('control', 'source', 'dirty', 'missing', 'duplicate', 'before', 'magnitude',
                           'dates', 'scope', 'units', 'confidence', 'boundary', 'publication', 'overflow',
                           'keyboard', 'requests', 'provider', 'error', 'cleanup', 'memory', 'oom',
                           'heavy', 'screenshots'):
                with self.subTest(change=change):
                    data = copy.deepcopy(report)
                    row = data['records'][0]
                    if change == 'source':
                        data['tree'] = 'c'*40
                    if change == 'dirty':
                        data['working_tree_clean'] = False
                    if change == 'missing':
                        data['records'].pop()
                    if change == 'duplicate':
                        data['records'][-1] = copy.deepcopy(row)
                    if change == 'before':
                        row['before']['magnitude'] = 120
                    for key, field, value in (('magnitude', 'magnitude', 100), ('dates', 'comparison_start_at', None),
                                              ('scope', 'comparison_scope', None), ('units', 'comparison_units', None),
                                              ('confidence', 'confidence', 'high')):
                        if change == key:
                            row['updated'][field] = value
                    if change == 'boundary':
                        row['boundary']['magnitude'] = 120
                    for key, field, value in (('publication', 'price_publication_unchanged', False),
                                              ('overflow', 'overflow', True), ('keyboard', 'keyboard', False),
                                              ('requests', 'disclosure_extra_requests', 1),
                                              ('provider', 'source_catalogue_not_participation', False)):
                        if change == key:
                            row[field] = value
                    if change == 'error':
                        data['errors'] = ['failed']
                    if change == 'cleanup':
                        data['browser_closed'] = False
                    if change == 'memory':
                        data['before_memory']['cgroup_limit_bytes'] = None
                    if change == 'oom':
                        data['after_memory']['cgroup_memory_events']['oom_kill'] = 1
                    if change == 'heavy':
                        data['requests'].append(dict(path='/sync', status=200))
                    files = {'browser.json': json.dumps(data).encode()}
                    files.update({str(i)+'.png': b'\x89PNG\r\n\x1a\n' for i in range(24)})
                    if change == 'screenshots':
                        del files['0.png']
                    p.make_zip(path, files)
                    if change == 'control':
                        self.assertEqual(p.verify_market_history(path, plan), report)
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_market_history(path, plan)


class RestorationAdmissionEvidenceTests(unittest.TestCase):
    def test_incomplete_or_weakened_restoration_records_cannot_publish(self):
        result = dict(head='a'*40, tree='b'*40, working_tree_clean=True, passed=True,
            scratch_removed=True, explicit_retry_completed=True,
            expired_released_active_and_fresh_preserved=True, fois_reserve_preserved=True,
            before_plan={'would_admit':False,'required_bytes':500},
            recovery={'would_admit':True,'required_bytes':500,'expired_entries':3},
            raw_bytes_released=200, unsafe_pressure_deferred={'would_admit':False},
            fois_reserved_plan={'would_admit':False,'required_bytes':1000},
            kernel_lifetime_peak_bytes=1800000000,
            samples=[{'cgroup_limit_bytes':2147483648,'cgroup_memory_events':{'oom':0,'oom_kill':0}}],
            cleanup_processes=[], liveness=[{'server_ms':2,'client_ms':3}]*4)
        mutations = {'source':lambda r:r.update(head='wrong'),
            'incomplete':lambda r:r.update(passed=False),
            'dirty':lambda r:r.update(working_tree_clean=False),
            'scratch':lambda r:r.update(scratch_removed=False),
            'retry':lambda r:r.update(explicit_retry_completed=False),
            'active':lambda r:r.update(expired_released_active_and_fresh_preserved=False),
            'reserve':lambda r:r['recovery'].update(required_bytes=400),
            'defer':lambda r:r['unsafe_pressure_deferred'].update(would_admit=True),
            'fois':lambda r:r['fois_reserved_plan'].update(required_bytes=500),
            'memory':lambda r:r.update(kernel_lifetime_peak_bytes=2147483649),
            'oom':lambda r:r['samples'][0]['cgroup_memory_events'].update(oom_kill=1),
            'worker':lambda r:r.update(cleanup_processes=[{'resource_tracker':False}]),
            'liveness':lambda r:r.update(liveness=[])}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'control.zip'
            for name, change in mutations.items():
                with self.subTest(name=name):
                    row = copy.deepcopy(result)
                    change(row)
                    p.make_zip(path, {'evidence/result.json':json.dumps(row).encode()})
                    with self.assertRaises(RuntimeError):
                        p.verify_restoration_unused(path, {'candidate':'a'*40,'tree':'b'*40})


class NativeRestorationAdmissionTests(unittest.TestCase):
    def test_completed_generic_recovery_does_not_replace_native_actuals_parity(self):
        good = dict(passed=True,method='sleeper-matchup-actuals-v1',source_generation='native',
            admitted_generation='native',expected_first_scores=[0,-2.125],admitted_first_scores=[0,-2.125],
            league_id='fixture',season='2026',scoring_fingerprint='scoring',observations=2)
        with patch.object(p,'verify_restoration_unused',return_value={'native_actuals':good}):
            self.assertEqual(p.verify_actuals_restoration(None,None)['native_actuals'],good)
        for key,value in [('passed',False),('method','nflverse'),('source_generation',None),
                          ('admitted_generation','other'),('admitted_first_scores',[0,0]),
                          ('observations',0),('league_id',None)]:
            with self.subTest(key=key), patch.object(p,'verify_restoration_unused',return_value={'native_actuals':good | {key:value}}):
                with self.assertRaises(RuntimeError):
                    p.verify_actuals_restoration(None,None)


class PlanFinalizationTests(unittest.TestCase):
    def test_placeholder_or_incomplete_evidence_cannot_publish(self):
        plan = json.loads(Path('.github/release-plans/2240.json').read_text())
        with self.assertRaisesRegex(RuntimeError,'not finalized'):
            p.verify_plan(plan | {'finalized':False})
        ready = plan | dict(finalized=True,draft_id=1,canonical_tests=2,canonical_entries=3,
            local_canonical_entries=3,product_tests=4,recovery_sha256='a'*64,prior_evidence_sha256='b'*64,
            runs=[run | {'id':index+1} for index,run in enumerate(plan['runs'])],
            artifacts=[{'file':n} for n in ('current-production-coverage-original.zip','market-history-coverage-original.zip','canonical-original.zip','preflight-original.zip',
                'trade-resource-original.zip','actuals-restoration-original.zip','restoration-unused-original.zip','resident-refresh-original.zip','league-entry-original.zip','current-history-original.zip','history-followthrough-original.zip','lifecycle-ordinary.zip',
                'lifecycle-archive-warmed.zip','lifecycle-combined-read.zip','public-welcome-security.zip')])
        p.verify_plan(ready)
        for field in ('draft_id','canonical_tests','canonical_entries','local_canonical_entries','product_tests'):
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError,'Missing final release evidence'):
                p.verify_plan(ready | {field:None})
        with self.assertRaisesRegex(RuntimeError,'Missing mandatory release artifacts'):
            p.verify_plan(ready | {'artifacts':[]})
        for omitted in ('resident-refresh-original.zip', 'public-welcome-security.zip'):
            with self.subTest(omitted=omitted), self.assertRaisesRegex(RuntimeError, 'Missing mandatory'):
                p.verify_plan(ready | {'artifacts': [a for a in ready['artifacts'] if a['file'] != omitted]})
        with self.assertRaisesRegex(RuntimeError, 'duplicate'):
            p.verify_plan(ready | {'artifacts': ready['artifacts'] + [ready['artifacts'][0]]})




class CurrentProductionIntegrityTests(unittest.TestCase):
    def test_exact_coverage_missing_safety_and_rendered_controls_are_required(self):
        plan = dict(candidate='a'*40, tree='b'*40)
        complete = dict(fantasy_points=18, observation_count=8, scored_count=8, season=2026, weeks=list(range(1,9)))
        partial = dict(fantasy_points=None, observation_count=8, scored_count=7, missing_components=['conflicting_sleeper_scores'])
        records = [dict(league=league, viewport=[w,h], complete=complete, partial=partial, retained_failure=True,
                        keyboard=True, overflow=False, extra_disclosure_requests=0, touch_emulated=w<1000)
                   for league in ('1314695233040052224','1319750579458686976')
                   for w,h in ((320,432),(375,667),(390,844),(1280,900))]
        memory = dict(cgroup_limit_bytes=2147483648,cgroup_memory_events={'oom':0,'oom_kill':0})
        good = dict(head=plan['candidate'],tree=plan['tree'],working_tree_clean=True,records=records,
                    before_memory=memory,after_memory=memory,errors=[],browser_closed=True,requests=[{'path':'/market'}])
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'production.zip'
            for mutation in ('valid','source','dirty','population','partial_value','coverage','retained','overflow','heavy','oom','png','old_non_sleeper_gap'):
                report=copy.deepcopy(good)
                if mutation=='old_non_sleeper_gap':
                    report['records'][0]['partial'].update(scored_count=0,missing_components=['st_ff'])
                if mutation=='source':
                    report['head']='wrong'
                if mutation=='dirty':
                    report['working_tree_clean']=False
                if mutation=='population':
                    report['records'].pop()
                if mutation=='partial_value':
                    report['records'][0]['partial']['fantasy_points']=0
                if mutation=='coverage':
                    report['records'][0]['complete']['scored_count']=7
                if mutation=='retained':
                    report['records'][0]['retained_failure']=False
                if mutation=='overflow':
                    report['records'][0]['overflow']=True
                if mutation=='heavy':
                    report['requests'].append({'path':'/sync'})
                if mutation=='oom':
                    report['after_memory']['cgroup_memory_events']['oom_kill']=1
                files={'browser.json':json.dumps(report).encode()}
                files.update({str(i)+'.png':b'\x89PNG\r\n\x1a\nfixture' for i in range(23 if mutation=='png' else 24)})
                p.make_zip(target,files)
                with self.subTest(mutation=mutation):
                    if mutation=='valid':
                        self.assertEqual(len(p.verify_current_production(target,plan)['records']),8)
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_current_production(target,plan)


class PriorAttemptIdentityTests(unittest.TestCase):
    def test_history_uses_attempt_specific_endpoint_and_preserves_failure(self):
        record=dict(id=123,run_attempt=1,name='canonical',head_sha='a'*40,status='completed',conclusion='failure',html_url='https://github.com/owner/repo/actions/runs/123/attempts/1')
        with patch.object(p,'api',return_value=record) as reader:
            self.assertEqual(p.prior_attempt_record('repos/owner/repo',dict(id=123,attempt=1)),record)
        reader.assert_called_once_with('repos/owner/repo/actions/runs/123/attempts/1')

    def test_history_cannot_substitute_latest_success_for_failed_attempt(self):
        with patch.object(p,'api',return_value=dict(id=123,run_attempt=2,conclusion='success')):
            with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
                p.prior_attempt_record('repos/owner/repo',dict(id=123,attempt=1))

    def test_invalid_history_reference_does_not_issue_a_request(self):
        for value in (dict(id=True,attempt=1),dict(id=1,attempt=0),dict(id='1',attempt=1),dict(id=1,attempt=1,path='untrusted'),123):
            with self.subTest(value=value),patch.object(p,'api') as reader:
                with self.assertRaises(RuntimeError):
                    p.prior_attempt_record('repos/owner/repo',value)
                reader.assert_not_called()


class ResidentRefreshIntegrityTests(unittest.TestCase):
    def test_resource_source_cleanup_execution_and_checksums_are_required(self):
        plan = dict(candidate='a' * 40, tree='b' * 40)
        cases = [dict(name=name, failed_refresh=failed, reader=reader, completed=True,
            invalid_restore_preserved_current=True, repeated_switches=3,
            cancellation_writer_drained=True, old_released_without_reader=not reader,
            source_digest='c' * 64) for name, failed, reader in
            [('oneqb', False, False), ('oneqb', True, False), ('superflex', False, True)]]
        cases[-1].update(pressure_deferred=True, fois_protected=True, recovery_completed=True,
            relieved_fixture_bytes=64*1024**2, owner_release_plan=dict(telemetry_valid=True),
            recovery_plan=dict(would_admit=True))
        cases.append(dict(name='global-evidence', completed=True, old_released_without_reader=True,
            source_acquisition_mocked=True, source_restoration_completed=True, scheduler_cancelled=True,
            source_digest='c' * 64))
        good = dict(schema='resident-refresh-ownership-v2', head=plan['candidate'], tree=plan['tree'],
            passed=True, working_tree_clean=True, cgroup_limit=2147483648, swap_limit=0,
            cpus=2, network='none', children_after=[], scratch_removed=True,
            source_values_preserved=True, cases=cases,
            samples=[dict(cgroup_limit_bytes=2147483648, cgroup_memory_events=dict(oom_kill=0))],
            liveness=[dict(server_ms=4.0, client_ms=8.0)])
        mutations = {'none': lambda r: None, 'source': lambda r: r.update(head='wrong'),
            'tree': lambda r: r.update(tree='wrong'), 'limit': lambda r: r.update(cgroup_limit=1),
            'child': lambda r: r.update(children_after=[123]), 'scratch': lambda r: r.update(scratch_removed=False),
            'values': lambda r: r.update(source_values_preserved=False),
            'case': lambda r: r['cases'].pop(),
            'deferred-as-complete': lambda r: r['cases'][0].update(completed=False),
            'writer': lambda r: r['cases'][1].update(cancellation_writer_drained=False),
            'reader': lambda r: r['cases'][2].update(old_released_without_reader=True),
            'recovery': lambda r: r['cases'][2].update(recovery_completed=False),
            'fois': lambda r: r['cases'][2].update(fois_protected=False),
            'oom': lambda r: r['samples'][0]['cgroup_memory_events'].update(oom_kill=1),
            'live': lambda r: r['liveness'][0].update(server_ms=501),
            'global': lambda r: r['cases'][3].update(old_released_without_reader=False),
            'global-restoration': lambda r: r['cases'][3].update(source_restoration_completed=False),
            'sums': lambda r: None, 'incomplete-sums': lambda r: None}
        with tempfile.TemporaryDirectory() as folder:
            for name, change in mutations.items():
                with self.subTest(name=name):
                    result = copy.deepcopy(good)
                    change(result)
                    data = json.dumps(result).encode()
                    files = {'evidence/result.json': data, 'raw.log': b'original log'}
                    files['SHA256SUMS'] = ''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n'
                        for n,b in files.items()).encode()
                    if name == 'sums':
                        files['raw.log'] += b'changed'
                    if name == 'incomplete-sums':
                        files['SHA256SUMS'] = b''
                    target = Path(folder) / 'resident.zip'
                    p.make_zip(target, files)
                    if name == 'none':
                        self.assertTrue(p.verify_resident_refresh(target, plan)['passed'])
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_resident_refresh(target, plan)


class TradeTimeMarketPublisherTests(unittest.TestCase):

    def test_feature_source_phone_and_package_boundaries(self):
        import copy
        import tempfile
        import zipfile
        from pathlib import Path
        plan = {'candidate': 'candidate', 'tree': 'tree'}
        phone = dict(head='candidate', tree='tree', working_tree_clean=True, records=[dict(width=w, height=h, keyboard=True, overflow=False, touch_emulated=w < 500, source_value=321, age_seconds=3600, extra_disclosure_requests=0, errors=[]) for w, h in [(320, 432), (375, 667), (390, 844), (1280, 900)]])
        feature = dict(head='candidate', tree='tree', working_tree_clean=True, cases=[dict(case=k, selected_value=v, package_totals_displayed=False, retained_fixture_values=[{'value': v}]) for k, v in {'newer_incompatible': 400, 'newer_foreign': 400, 'partial_old': 275, 'zero': 0, 'conflicting': None}.items()])
        supplied = dict(provenance='Supplied Main Chat observation', exhaustive=False, complete_package_coverage='Not established', historical_league_format_parity='Not established')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'feature.zip'

            def write(ph, fe, sp):
                with zipfile.ZipFile(path, 'w') as z:
                    z.writestr('feature/browser.json', json.dumps(ph))
                    z.writestr('feature/feature.json', json.dumps(fe))
                    z.writestr('supplied-screen.json', json.dumps(sp))
            write(phone, feature, supplied)
            self.assertTrue(p.verify_trade_time_market(path, plan)['passed'])
            for field, value in [('head', 'other'), ('tree', 'other'), ('working_tree_clean', False)]:
                bad = copy.deepcopy(feature)
                bad[field] = value
                write(phone, bad, supplied)
                with self.assertRaises(RuntimeError):
                    p.verify_trade_time_market(path, plan)
            bad = copy.deepcopy(phone)
            bad['records'][0]['extra_disclosure_requests'] = 1
            write(bad, feature, supplied)
            with self.assertRaises(RuntimeError):
                p.verify_trade_time_market(path, plan)
            bad = copy.deepcopy(feature)
            bad['cases'][0]['package_totals_displayed'] = True
            write(phone, bad, supplied)
            with self.assertRaises(RuntimeError):
                p.verify_trade_time_market(path, plan)
            bad = copy.deepcopy(supplied)
            bad['exhaustive'] = True
            write(phone, feature, bad)
            with self.assertRaises(RuntimeError):
                p.verify_trade_time_market(path, plan)


if __name__ == '__main__':
    unittest.main()
