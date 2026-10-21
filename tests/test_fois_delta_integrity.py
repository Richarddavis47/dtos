"""Typed retained-delta admission and atomic, privately staged reconstruction."""
import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zlib

from src.core.fois import state_delta, state_storage as storage


def typed(value):
    if isinstance(value, dict):
        return (type(value), frozenset((typed(k), typed(v)) for k, v in value.items()))
    if isinstance(value, list):
        return (type(value), tuple(typed(v) for v in value))
    return (type(value), value)


def forge(db, before, target, operations):
    storage.encode(db, before)
    envelope = storage.encode(db, target)
    delta = {'base': storage.split(before)[0], 'depth': 1, 'changes': operations}
    db.execute('UPDATE fois_semantic_states SET format=?,payload=? WHERE state_id=?',
               (storage.DELTA_FORMAT, zlib.compress(storage.canonical(delta).encode()),
                json.loads(envelope)['state_id']))
    return envelope


class FOISDeltaIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript(storage.SCHEMA)
        self.addCleanup(self.db.close)
        self.base = {'league_id': 'A', 'score_key': 'A:gm:t:m', 'tenure_id': 't',
                     'model_version': 'm', 'object': {}, 'items': [{'123': 0}, None],
                     'refs': [{'id': str(n), 'value': hashlib.sha256(str(n).encode()).hexdigest()}
                              for n in range(200)]}

    def test_four_nonstring_object_paths_rejected_before_memo_admission(self):
        for bad in (123, True, None, 1.5):
            with self.subTest(component=bad, kind=type(bad).__name__):
                key = next(iter(json.loads(json.dumps({bad: 0}))))
                target = {**self.base, 'object': {key: {'zero': 0, 'missing': None}}}
                envelope = forge(self.db, self.base, target,
                                 [['set', ['object', bad], {'zero': 0, 'missing': None}]])
                before_rows = tuple(self.db.iterdump())
                reader = storage.SnapshotDecoder(self.db)
                for _ in range(2):
                    with self.assertRaisesRegex(ValueError, 'delta'):
                        reader.decode(envelope)
                    self.assertEqual(reader._states, {})
                    self.assertEqual(reader.retained_bytes, 0)
                self.assertEqual(tuple(self.db.iterdump()), before_rows)
                # A later genuinely corrected publication can recover through
                # this same reader; rejection must not cache coerced evidence.
                corrected = {'base': storage.split(self.base)[0], 'depth': 1,
                             'changes': [['set', ['object', key], {'zero': 0, 'missing': None}]]}
                self.db.execute('UPDATE fois_semantic_states SET payload=? WHERE state_id=?',
                                (zlib.compress(storage.canonical(corrected).encode()),
                                 json.loads(envelope)['state_id']))
                self.assertEqual(typed(reader.decode(envelope)), typed(target))
                valid = storage.encode(self.db, self.base)
                self.assertEqual(typed(reader.decode(valid)), typed(self.base))

    def test_canonical_string_keys_and_integer_indices_preserve_types_on_memo_hit(self):
        target = copy.deepcopy(self.base)
        target['object']['123'] = {'zero': 0, 'missing': None, 'flag': False}
        target['items'][0]['123'] = 9
        envelope = storage.encode(self.db, target, base_payload=self.base)
        row = self.db.execute('SELECT format FROM fois_semantic_states WHERE state_id=?',
                              (json.loads(envelope)['state_id'],)).fetchone()
        self.assertEqual(row[0], storage.DELTA_FORMAT)
        reader = storage.SnapshotDecoder(self.db)
        first, memo = reader.decode(envelope), reader.decode(envelope)
        self.assertEqual(typed(first), typed(memo))
        self.assertEqual(typed(first), typed(target))
        self.assertIs(type(next(iter(first['object']))), str)
        first['object']['123']['zero'] = 'local'
        first['refs'][0]['id'] = 'local'
        self.assertEqual(memo['object']['123']['zero'], 0)
        self.assertEqual(memo['refs'][0]['id'], '0')
        self.assertEqual(typed(reader.decode(envelope)), typed(target))

    def test_list_indices_require_exact_nonnegative_integers(self):
        for bad in (True, False, None, 0.0, '0', -1, 2):
            for action in ('set', 'del'):
                with self.subTest(component=bad, kind=type(bad).__name__, action=action):
                    op = [action, ['items', bad]] + ([0] if action == 'set' else [])
                    original = copy.deepcopy(self.base)
                    with self.assertRaisesRegex(ValueError, 'delta'):
                        state_delta.apply(self.base, [op], _owned=True)
                    self.assertEqual(typed(self.base), typed(original))

    def test_container_mismatches_and_missing_intermediates_fail_closed(self):
        for path in (['object', 0, 'nested'], ['items', '0', '123'],
                     ['items', 0, 123], ['items', 1, 'nested'],
                     ['absent', 'nested'], ['object', []], ['object', {}]):
            with self.subTest(path=path):
                before = copy.deepcopy(self.base)
                with self.assertRaisesRegex(ValueError, 'delta'):
                    state_delta.apply(self.base, [['set', path, 1]], _owned=True)
                self.assertEqual(typed(self.base), typed(before))

    def test_late_invalid_paths_cannot_partially_mutate_base_or_operation_values(self):
        batches = [
            [['set', ['items', 0, '123'], 8], ['del', ['refs', 0]],
             ['set', ['object', 123], 0]],
            [['set', [], {'nested': [{'zero': 0}]}],
             ['set', ['nested', 0, 'zero'], 8], ['del', ['absent']]],
            [['set', ['new'], {'nested': [0]}],
             ['set', ['new', 'nested', 0], 8], ['set', ['new', 'nested', 1], 0]],
        ]
        for ops in batches:
            for owned in (False, True):
                with self.subTest(owned=owned, ops=ops):
                    before, original_ops = copy.deepcopy(self.base), copy.deepcopy(ops)
                    with self.assertRaises(ValueError):
                        state_delta.apply(self.base, ops, _owned=owned)
                    self.assertEqual(typed(self.base), typed(before))
                    self.assertEqual(typed(ops), typed(original_ops))

    def test_valid_ordered_set_delete_and_root_replacement(self):
        operations = [['set', ['object', '123'], {'items': [0, 1]}],
                      ['set', ['object', '123', 'items', 1], 9],
                      ['del', ['object', '123', 'items', 0]]]
        expected = copy.deepcopy(self.base)
        expected['object']['123'] = {'items': [9]}
        for owned in (False, True):
            self.assertEqual(typed(state_delta.apply(self.base, operations, _owned=owned)),
                             typed(expected))
        replacement = [['set', [], {'nested': [0]}], ['set', ['nested', 0], 9]]
        self.assertEqual(state_delta.apply({}, replacement, _owned=True), {'nested': [9]})

    def test_malformed_instructions_fail_as_data_errors(self):
        for operations in (None, {}, [None], [[]], [['set', []]],
                           [['set', [], 0, 'extra']], [['del', []]],
                           [['del', ['object'], 1]], [['unknown', []]],
                           [['set', ('object',), 1]]):
            with self.subTest(operations=operations), self.assertRaisesRegex(ValueError, 'delta'):
                state_delta.apply(self.base, operations, _owned=True)

    def test_owned_staging_avoids_full_tree_copy_and_preserves_private_base(self):
        before = copy.deepcopy(self.base)
        with patch.object(state_delta, 'deepcopy', side_effect=AssertionError('no full-tree copy')):
            result = state_delta.apply(self.base, [['set', ['items', 0, '123'], 9]], _owned=True)
        self.assertEqual(typed(self.base), typed(before))
        self.assertIs(result['refs'], self.base['refs'])  # private, untouched tree is reused
        self.assertIsNot(result['items'], self.base['items'])
        self.assertIsNot(result['items'][0], self.base['items'][0])
        public = state_delta.apply(self.base, [['set', ['object', '123'], {'items': [0]}]])
        public['refs'][0]['id'] = 'local'
        self.assertEqual(self.base['refs'][0]['id'], '0')


class FOISDeltaHistoryHTTPTests(unittest.TestCase):
    def test_actual_authenticated_history_consumers_withhold_malformed_evidence(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes.fois import create_fois_router
        from src.core.accounts import AccountService, AccountStore
        from src.core.fois.engine import FOISEngine
        from src.core.fois.facts import FOISFacts, SeasonResult
        from src.core.fois.models import FOIS_MODEL_VERSION
        from src.core.fois.repository import FOISRepository
        from src.core.fois.service import FOISService
        from src.platform.account_context import AccountContextMiddleware, SESSION_COOKIE
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = FOISRepository(root / 'fois.db')
            score = FOISEngine().evaluate(FOISFacts('A', 'A:1', 'gm',
                (SeasonResult(2025, 9, 5, 2, league_size=10),), gm_id='gm', tenure_id='A:gm'))
            score = replace(score, evidence_integrity_version=None,
                            front_office_evidence={'refs': [{'id':str(n)} for n in range(80)]})
            repo.save(score, 'fixture-source')
            accounts = AccountStore(root / 'accounts.db')
            account_service = AccountService(accounts)
            account, _ = account_service.create_account('delta-fixture', 'Delta fixture', 'fixture delta password')
            accounts.link_sleeper(account, sleeper_user_id='gm', username='delta-fixture', display_name='Delta fixture')
            accounts.upsert_membership(account, {'league_id':'A','name':'Fixture','season':'2026'},
                                       'gm', 1, 'Fixture franchise', 'active')
            accounts.activate(account, 'A')
            token, _ = account_service.new_session(account)
            service = FOISService(repo)
            app = FastAPI()
            app.add_middleware(AccountContextMiddleware, service=account_service, required=True)
            app.include_router(create_fois_router(service=service, require_data=lambda:{}))
            paths = ['/fois/gms/gm?league_id=A', '/api/fois/leagues/A/gms/gm',
                     '/api/fois/leagues/A/gms/gm/timeline']
            with TestClient(app, raise_server_exceptions=False) as client, patch.object(
                service, 'generate', side_effect=AssertionError('reads cannot generate grades'),
            ):
                self.assertIn(client.get(paths[0], follow_redirects=False).status_code, (303, 401))
                client.cookies.set(SESSION_COOKIE, token)
                for path in paths:
                    self.assertEqual(client.get(path).status_code, 200)
                before = json.loads(json.dumps(asdict(score)))
                for bad in (123, True, None, 1.5):
                    with self.subTest(component=bad):
                        key = next(iter(json.loads(json.dumps({bad: 0}))))
                        target = copy.deepcopy(before)
                        target['front_office_evidence']['object'] = {key: 0}
                        with repo._connection() as db:
                            envelope = forge(db, before, target,
                                [['set', ['front_office_evidence', 'object'], {}],
                                 ['set', ['front_office_evidence', 'object', bad], 0]])
                            db.execute('UPDATE fois_snapshot_history SET payload=?', (envelope,))
                            db.commit()
                        source_hash = hashlib.sha256(repo.path.read_bytes()).hexdigest()
                        for read in (repo.timeline, repo.timeline_summary):
                            with self.assertRaisesRegex(ValueError, 'delta'):
                                read('A', 'gm', FOIS_MODEL_VERSION)
                        for path in paths:
                            response = client.get(path)
                            self.assertEqual(response.status_code, 503, path)
                            self.assertIn('invalid retained delta', response.json()['detail'])
                            self.assertIn('not been revalidated', response.json()['detail'])
                        self.assertEqual(hashlib.sha256(repo.path.read_bytes()).hexdigest(), source_hash)
                        self.assertEqual(repo.timeline('B', 'gm'), ())
