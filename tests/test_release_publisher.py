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
        self.plan = dict(candidate='a' * 40, tree='b' * 40, canonical_entries=3, canonical_tests=2)
        result = dict(head=self.plan['candidate'], tree=self.plan['tree'], passed=True, exit_code=0,
                      cgroup_limit=2147483648, cpus=2, network='none',
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
        path = self.root / 'evidence.zip'
        p.make_zip(path, files)
        return path

    def test_complete_source_pinned_evidence(self):
        self.assertTrue(p.verify_canonical(self.archive(), self.plan)['passed'])

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


class ContextAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(Path('.github/release-plans/2221.json').read_text())
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
            return 'VERSION = "1.22.6"\nBUILD_NUMBER = 2221\n'
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
        self.plan = json.loads(Path('.github/release-plans/2221.json').read_text())
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

    def test_exact_twelve_jobs_are_required(self):
        with patch.object(p, 'api', side_effect=self.api):
            records, product = p.verify_runs(self.plan)
        self.assertEqual(len(records), 12)
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


if __name__ == '__main__':
    unittest.main()
