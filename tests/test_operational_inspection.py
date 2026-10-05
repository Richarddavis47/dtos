"""Private HTTPS inspection security, bounds, graph parity and physical immutability."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.operations_inspect import create_operations_inspection_router
from src.core.fois import state_storage as fois_state
from src.core.fois.repository import SCHEMA as FOIS_SCHEMA
from src.core.projection_intelligence import state_storage
from src.platform import operational_inspection as evidence
from src.platform.account_context import AccountContextMiddleware
from src.platform.inspection_security import (
    OPERATIONS,
    PREFIX,
    OperationalInspectionBoundary,
)
from src.platform.league_context import LeagueContextMiddleware
from src.platform.market_warming import AssetMarketWarmingMiddleware
from tools.projection_reachability import InspectionLimit, analyze, unpack

TOKEN = 'local-test-inspection-credential'
HEADERS = {'X-DTOS-Inspection-Auth': TOKEN}


class OperationalInspectionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.projection = self.root / 'projection.sqlite3'
        self.fois = self.root / 'fois.sqlite3'
        with sqlite3.connect(self.projection) as db:
            db.executescript(state_storage.SCHEMA + '''
                CREATE TABLE projection_snapshots(snapshot_id TEXT PRIMARY KEY,league_id TEXT,
                  season INTEGER,week INTEGER,generated_at TEXT,payload TEXT);
                CREATE TABLE projection_publication_heads(league_id TEXT PRIMARY KEY,snapshot_id TEXT);
                CREATE TABLE projection_previous_heads(league_id TEXT PRIMARY KEY,snapshot_id TEXT);
                CREATE TABLE projection_checkpoint_roots(snapshot_id TEXT PRIMARY KEY);
                CREATE TABLE projection_retention_policy(version TEXT PRIMARY KEY);
                INSERT INTO projection_retention_policy VALUES('projection-retention-v1');
                CREATE TABLE projection_source_history(observation_id INTEGER PRIMARY KEY,season INTEGER,
                  week INTEGER,observed_at TEXT,fingerprint TEXT,payload TEXT);
            ''')
            for index in range(5):
                body = {'projection_snapshot_id': f'snapshot-{index}', 'league_id': 'league-fixture',
                        'season': 2026, 'week': 2, 'generated_at': f'2026-09-{20+index}',
                        'scoring_profile_id': 'ppr', 'model_version': '1', 'contract_version': '1',
                        'sleeper_evidence_snapshot_id': 'source-fingerprint',
                        'players': {'private-player': {'canonical_projection': 1, 'secret': 'PRIVATE_PLAYER_PAYLOAD'}},
                        'account': 'PRIVATE_ACCOUNT', 'token': 'PRIVATE_TOKEN'}
                if index == 4:
                    body['horizon_snapshot_ids'] = {'2': 'snapshot-3'}
                db.execute('INSERT INTO projection_snapshots VALUES(?,?,?,?,?,?)',
                           (body['projection_snapshot_id'], body['league_id'], 2026, 2,
                            body['generated_at'], state_storage.encode(db, body)))
            db.execute("INSERT INTO projection_publication_heads VALUES('league-fixture','snapshot-4')")
            db.execute("INSERT INTO projection_previous_heads VALUES('league-fixture','snapshot-2')")
            db.execute("INSERT INTO projection_checkpoint_roots VALUES('snapshot-0')")
            source = {'$storage': 'projection-provenance-v1', 'envelope': {'account': 'PRIVATE_SOURCE_ACCOUNT'}}
            db.execute('INSERT INTO projection_source_history VALUES(1,2026,2,?,?,?)',
                       ('2026-09-19', 'source-fingerprint', json.dumps(source)))
        with sqlite3.connect(self.fois) as db:
            db.executescript(FOIS_SCHEMA + fois_state.SCHEMA + '''
                CREATE TABLE fois_retention_policy(version TEXT PRIMARY KEY,legacy_max_rowid INTEGER);
                INSERT INTO fois_retention_policy VALUES('fois-retention-v1',0);
                CREATE TABLE fois_assessment_roots(snapshot_id TEXT PRIMARY KEY,reason TEXT);
            ''')
            db.execute('INSERT INTO fois_semantic_states VALUES(?,?,?,?,?)',
                       ('state', 'fois-state-v1', b'PRIVATE_FOIS_PAYLOAD', 20, 'PRIVATE_FOIS_LEAGUE'))
        for path in (self.projection, self.fois):
            path.with_name(path.name + '.storage-lock').write_bytes(b'\0')
        self.stores = evidence.InspectionStores(self.projection, self.fois, self.root,
                         {'projection': self.projection, 'fois': self.fois}, self.root / 'cache.json',
                         self.root / 'seasons', self.root / '.storage-accounting.json')
        self.accounts, self.manager, self.market = Mock(), Mock(), Mock()
        self.accounts.store.context_for_session.side_effect = AssertionError('Session read')
        self.manager.resident.side_effect = AssertionError('Runtime touch')
        self.manager.get.side_effect = AssertionError('Runtime preparation')
        self.market.begin_warming_guard.side_effect = AssertionError('Market preparation')
        app = FastAPI()
        app.include_router(create_operations_inspection_router(stores=self.stores))
        app.add_middleware(LeagueContextMiddleware, manager=self.manager, default_league_id='default', import_enabled=True)
        app.add_middleware(AssetMarketWarmingMiddleware, cache=self.market, data_provider=Mock(),
                           state={}, store=Mock(), league_id='default', build_allowed=Mock())
        app.add_middleware(AccountContextMiddleware, service=self.accounts, required=True)
        app.add_middleware(OperationalInspectionBoundary)
        self.app = app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.env = patch.dict(os.environ, {'DTOS_INSPECTION_AUTH_TOKEN': TOKEN,
                                          'DTOS_INSPECTION_LEAGUE_ID': 'foreign', 'DTOS_INSPECTION_ROSTER_ID': '1'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cooldown = patch('routes.operations_inspect.GRAPH_COOLDOWN_SECONDS', 0)
        self.cooldown.start()
        self.addCleanup(self.cooldown.stop)
        patcher = patch('routes.operations_inspect._NEXT_GRAPH_READ', 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, operation, **kwargs):
        return self.client.get(PREFIX + '/' + operation, headers=HEADERS, **kwargs)

    def test_unauthorized_requests_have_no_resource_disclosure(self):
        for operation in (*OPERATIONS, 'unsupported', '%2e%2e%2fsecrets', 'nested/unknown'):
            for method in ('GET', 'POST', 'DELETE', 'OPTIONS'):
                response = self.client.request(method, PREFIX + '/' + operation)
                self.assertEqual(response.status_code, 401, (operation, method, response.text))
                self.assertEqual(response.json(), {'detail': 'Inspection authorization required'})
                self.assertIn('no-store', response.headers['cache-control'])

    def test_malformed_and_duplicate_auth_rejected(self):
        for value in ('', 'wrong', 'Bearer ' + TOKEN, TOKEN + ' ', 'é', 'x' * 4097):
            # Latin-1 through bytes also exercises non-ASCII without httpx parsing.
            response = self.client.get(PREFIX + '/identity', headers=[(b'x-dtos-inspection-auth', value.encode('latin-1'))])
            self.assertEqual(response.status_code, 401)
        response = self.client.get(PREFIX + '/identity', headers=[('X-DTOS-Inspection-Auth', TOKEN)] * 2)
        self.assertEqual(response.status_code, 401)

    def test_missing_or_malformed_server_token_fails_closed(self):
        for expected in ('', 'white space', 'é'):
            with patch.dict(os.environ, {'DTOS_INSPECTION_AUTH_TOKEN': expected}):
                self.assertEqual(self.get('identity').status_code, 401)

    def test_cookie_bearer_and_query_tokens_do_not_authorize(self):
        for kwargs in ({'headers': {'Cookie': 'dtos_session=public-user'}},
                       {'headers': {'Authorization': 'Bearer ' + TOKEN}},
                       {'params': {'inspection_token': TOKEN}}):
            self.assertEqual(self.client.get(PREFIX + '/identity', **kwargs).status_code, 401)

    def test_every_fixed_operation_succeeds_without_preparation(self):
        with patch('src.platform.storage_accounting.periodic_storage_accounting', side_effect=AssertionError('Collection')):
            for operation in OPERATIONS:
                response = self.get(operation)
                self.assertEqual(response.status_code, 200, (operation, response.text))
                self.assertIn('no-store', response.headers['cache-control'])
                self.assertEqual(response.headers['vary'], 'X-DTOS-Inspection-Auth')
        self.accounts.store.context_for_session.assert_not_called()
        self.manager.resident.assert_not_called()
        self.manager.get.assert_not_called()
        self.market.begin_warming_guard.assert_not_called()

    def test_database_files_and_directory_remain_byte_identical(self):
        def capture():
            entries = {}
            for path in self.root.rglob('*'):
                contents = path.read_bytes() if path.is_file() else None
                entries[str(path.relative_to(self.root))] = (
                    contents,
                    hashlib.sha256(contents).hexdigest() if contents is not None else None,
                    path.stat().st_mtime_ns,
                )
            return entries

        before = capture()
        for operation in OPERATIONS:
            self.assertEqual(self.get(operation).status_code, 200)
        after = capture()
        self.assertEqual(before, after)
        self.assertFalse(list(self.root.glob('*-wal')) + list(self.root.glob('*-shm')) + list(self.root.glob('*-journal')))

    def test_reachability_matches_existing_tool_including_digest(self):
        with sqlite3.connect(self.projection.as_uri() + '?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            expected = analyze(db)
        response = self.get('projection-reachability')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), expected)

    def test_inventory_pagination_and_relationships(self):
        response = self.get('projection-inventory', params={'limit': 2, 'offset': 2})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['total'], 5)
        self.assertEqual(result['next_offset'], 4)
        self.assertEqual([r['snapshot_id'] for r in result['snapshots']], ['snapshot-2', 'snapshot-3'])
        self.assertTrue(result['snapshots'][0]['rollback_head'])
        self.assertTrue(result['snapshots'][1]['horizon_member'])
        self.assertFalse(result['snapshots'][0]['source_available'])
        self.assertTrue(result['snapshots'][0]['provenance_available'])
        self.assertEqual(len(result['snapshots'][0]['envelope_sha256']), 64)
        allowed = {'snapshot_id', 'league_id', 'season', 'week', 'scoring_profile_id',
                   'classification', 'publication_head', 'rollback_head', 'historical_root',
                   'horizon_member', 'horizon_root', 'source_available', 'provenance_available',
                   'source_fingerprint', 'envelope_sha256'}
        for row in result['snapshots']:
            self.assertEqual(set(row), allowed)
            self.assertTrue(all(value is None or isinstance(value, (str, int, bool))
                                for value in row.values()))
        self.assertLessEqual(len(response.content), 256 * 1024)

    def test_inventory_bounds_enforced(self):
        for params in ({'limit': 0}, {'limit': 101}, {'offset': -1}, {'offset': 4097},
                       {'limit': 'foo'}, {'offset': '1.5'}, [('limit', '1'), ('limit', '2')]):
            self.assertEqual(self.get('projection-inventory', params=params).status_code, 400)
        self.assertEqual(self.get('projection-inventory', params={'offset': 4096}).json()['snapshots'], [])

    def test_arbitrary_sql_paths_and_writes_impossible(self):
        for operation in OPERATIONS:
            for key in ('sql', 'path', 'database', 'command', 'refresh', 'league', 'league_id', 'details'):
                response = self.get(operation, params={key: 'DROP TABLE projection_snapshots; /etc/passwd'})
                self.assertEqual(response.status_code, 400)
        for operation in ('shell', 'sql', 'files', 'refresh', 'restart', 'deploy', 'migrate', 'unsupported'):
            self.assertEqual(self.get(operation).status_code, 404)
        self.assertEqual(self.client.post(PREFIX + '/identity', headers=HEADERS, json={'sql': 'VACUUM'}).status_code, 405)
        self.manager.get.assert_not_called()

    def test_sqlite_is_query_only_and_has_authorizer(self):
        budget = evidence.Budget(time.monotonic() + 3)
        with evidence.read_connection(self.projection, evidence.PROJECTION_TABLES, budget) as reader:
            self.assertEqual(reader.db.execute('PRAGMA page_count').fetchone()[0] > 0, True)
            for statement in ('CREATE TABLE evil(x)', "INSERT INTO projection_retention_policy VALUES('evil')",
                              "ATTACH ':memory:' AS other", 'PRAGMA query_only=OFF', 'PRAGMA journal_mode=WAL',
                              'SELECT load_extension(\'evil\')'):
                with self.assertRaises(sqlite3.DatabaseError, msg=statement):
                    reader.db.execute(statement)
            reader.db.set_authorizer(None)
            self.assertEqual(reader.db.execute('PRAGMA query_only').fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                reader.db.execute("INSERT INTO projection_retention_policy VALUES('evil')")

    def test_sensitive_fields_omitted(self):
        for operation in OPERATIONS:
            text = self.get(operation).text
            for sensitive in ('PRIVATE_', TOKEN, str(self.root), 'private-player', 'csrf', 'owner_id', 'gm_id'):
                self.assertNotIn(sensitive, text)
        self.assertNotIn(PREFIX, json.dumps(self.app.openapi()))

    def test_malformed_graph_errors_are_sanitized_and_digested(self):
        with sqlite3.connect(self.projection) as db:
            db.execute('CREATE TABLE PRIVATE_SECRET_TABLE(secret TEXT)')
        report = self.get('projection-reachability').json()
        self.assertFalse(report['graph_valid'])
        self.assertNotIn('PRIVATE_SECRET_TABLE', json.dumps(report))
        digest = report.pop('report_sha256')
        self.assertEqual(digest, hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest())

    def test_missing_symlink_and_wal_stores_fail_without_new_files(self):
        missing = replace(self.stores, fois=self.root / 'absent.sqlite3')
        with self.assertRaises(OSError):
            evidence.fois_storage(missing, evidence.Budget(time.monotonic() + 3))
        self.assertFalse(missing.fois.exists())
        alias = self.root / 'alias.sqlite3'
        alias.symlink_to(self.fois)
        with self.assertRaises(InspectionLimit):
            evidence.fois_storage(replace(self.stores, fois=alias), evidence.Budget(time.monotonic() + 3))
        with sqlite3.connect(self.fois) as db:
            db.execute('PRAGMA journal_mode=WAL')
        before = {p.name for p in self.root.iterdir()}
        self.assertEqual(self.get('fois-storage').status_code, 503)
        self.assertEqual(before, {p.name for p in self.root.iterdir()})

    def test_existing_journal_is_not_recovered(self):
        journal = self.fois.with_name(self.fois.name + '-journal')
        journal.write_bytes(b'not-a-real-journal')
        self.assertEqual(self.get('fois-storage').status_code, 503)
        self.assertEqual(journal.read_bytes(), b'not-a-real-journal')

    def test_decoding_bomb_and_deadline_fail_closed(self):
        blob = base64.b64encode(zlib.compress(b' ' * 100_000)).decode()
        with self.assertRaises(InspectionLimit):
            unpack(json.dumps({'$storage': 'projection-players-v1', 'data': blob}), max_decoded_bytes=1000)
        with self.assertRaises(InspectionLimit):
            evidence.projection(self.stores, evidence.Budget(time.monotonic() - 1))
        with self.assertRaises(InspectionLimit):
            evidence.projection(self.stores, evidence.Budget(time.monotonic() + 3, max_snapshots=1))

    def test_concurrency_cooldown_and_response_limits(self):
        from routes import operations_inspect
        operations_inspect._DIAGNOSTIC_LOCK.acquire()
        try:
            self.assertEqual(self.get('identity').status_code, 429)
        finally:
            operations_inspect._DIAGNOSTIC_LOCK.release()
        with patch('routes.operations_inspect._NEXT_GRAPH_READ', time.monotonic() + 30):
            self.assertEqual(self.get('projection-reachability').status_code, 429)
        with patch('routes.operations_inspect.MAX_RESPONSE_BYTES', 10):
            self.assertEqual(self.get('identity').status_code, 503)

    def test_imports_and_calls_cannot_initialize_services(self):
        script = '''
import sqlite3
from unittest.mock import patch
with patch.object(sqlite3, 'connect', side_effect=AssertionError('Import created database')):
    import routes.operations_inspect
    import src.platform.operational_inspection
import sys
for module in ('services.fois', 'services.sleeper', 'src.core.projection_intelligence.service',
               'src.core.fois.service', 'src.core.asset_market.engine', 'dtos_app'):
    assert module not in sys.modules, module
'''
        subprocess.run([sys.executable, '-c', script], check=True, timeout=20)

    def test_monitoring_reads_existing_counters_without_collection_or_identifiers(self):
        from datetime import datetime, timezone

        from src.platform.durable_storage_monitor import COUNTERS, DurableStorageMonitor

        totals = dict.fromkeys(COUNTERS, 1000)
        totals['disk_free'] = 512 * evidence.MIB
        monitor = DurableStorageMonitor(self.stores.monitor)
        monitor.record(totals, {'PRIVATE_LEAGUE_ID': {'current_bytes': 1, 'canonical_history_bytes': 2, 'event_count': 0}},
                       now=datetime(2026, 10, 1, tzinfo=timezone.utc))
        before = self.stores.monitor.read_bytes()
        result = self.get('retention')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['monitoring']['counters'], totals)
        self.assertEqual(before, self.stores.monitor.read_bytes())
        self.assertNotIn('PRIVATE_LEAGUE_ID', result.text)
        self.assertNotIn(hashlib.sha256(b'PRIVATE_LEAGUE_ID').hexdigest(), result.text)

    def test_unknown_fois_schema_and_missing_fence_fail_closed(self):
        with sqlite3.connect(self.fois) as db:
            db.execute('CREATE TABLE PRIVATE_ACCOUNT_STORE(token TEXT)')
        result = self.get('fois-storage')
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('PRIVATE_ACCOUNT_STORE', result.text)
        fence = self.projection.with_name(self.projection.name + '.storage-lock')
        fence.unlink()
        self.assertEqual(self.get('projection-reachability').status_code, 503)
        self.assertFalse(fence.exists())

    @unittest.skipIf(os.name == 'nt', 'fcntl is a Linux maintenance-fence assertion')
    def test_maintenance_fence_is_shared_nonblocking_and_unmodified(self):
        import fcntl

        fence = self.projection.with_name(self.projection.name + '.storage-lock')
        with fence.open('rb') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                self.assertEqual(self.get('projection-reachability').status_code, 503)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        self.assertEqual(fence.read_bytes(), b'\0')

    def test_large_metadata_and_monitor_budget_are_rejected(self):
        with sqlite3.connect(self.projection) as db:
            db.execute('UPDATE projection_snapshots SET league_id=?', ('x' * 129,))
        self.assertEqual(self.get('projection-inventory').status_code, 503)
        self.stores.monitor.write_bytes(b'x' * (evidence.MIB + 1))
        self.assertEqual(self.get('retention').status_code, 503)
        self.assertEqual(self.get('identity', params={'unknown': 'x' * 256}).status_code, 400)

    def test_inventory_source_availability_respects_publication_boundary(self):
        with sqlite3.connect(self.projection) as db:
            db.execute('UPDATE projection_source_history SET payload=?',
                       (json.dumps({'players': {'private-player': 'PRIVATE_SOURCE_PAYLOAD'}}),))
            db.execute('INSERT INTO projection_source_history VALUES(2,2026,2,?,?,?)',
                       ('2026-09-22', 'different-source', json.dumps({'players': {}})))
        result = self.get('projection-inventory').json()
        self.assertTrue(result['snapshots'][0]['source_available'])
        self.assertFalse(result['snapshots'][4]['source_available'])
        self.assertFalse(result['snapshots'][4]['provenance_available'])
        self.assertNotIn('PRIVATE_SOURCE_PAYLOAD', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
