import asyncio
import json
import os
import subprocess
import sys
import socket
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import unittest

from tools.storage_maintenance import app


class StorageMaintenanceTests(unittest.TestCase):
    def invoke(self, scope, events=()):
        messages = []
        events = iter(events)

        async def receive():
            return next(events)

        async def send(message):
            messages.append(message)

        asyncio.run(app(scope, receive, send))
        return messages

    def test_health_is_liveness_not_readiness(self):
        for path in ('/health', '/healthz'):
            messages = self.invoke({'type': 'http', 'path': path, 'method': 'GET'})
            self.assertEqual(messages[0]['status'], 200)
            self.assertFalse(json.loads(messages[1]['body'])['application_ready'])

    def test_all_application_paths_unavailable_no_data(self):
        for path in ('/', '/ready', '/api/leagues/resources', '/market', '/picks', '/fois'):
            messages = self.invoke({'type': 'http', 'path': path, 'method': 'GET'})
            self.assertEqual(messages[0]['status'], 503)
            self.assertIn((b'cache-control', b'no-store'), messages[0]['headers'])
            self.assertEqual(json.loads(messages[1]['body'])['status'], 'maintenance')

    def test_start_stop_and_websocket_have_no_application_work(self):
        messages = self.invoke({'type': 'lifespan'},
                               [{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}])
        self.assertEqual([m['type'] for m in messages],
                         ['lifespan.startup.complete', 'lifespan.shutdown.complete'])
        self.assertEqual(self.invoke({'type': 'websocket'}),
                         [{'type': 'websocket.close', 'code': 1013}])

    def test_isolated_import_never_loads_application_or_storage(self):
        script = (
            "import sys; before=set(sys.modules); import tools.storage_maintenance; "
            "assert not any(m == 'dtos_app' or m == 'config' or m == 'sqlite3' "
            "or m.startswith(('services.', 'src.')) for m in set(sys.modules)-before)"
        )
        subprocess.run([sys.executable, '-c', script], check=True, timeout=20)

    def test_explicit_process_restart_serves_no_application_data(self):
        # Real ASGI server lifecycle. This proves maintenance isolation, not
        # Render's separate responsibility to quiesce the previous app/children.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = os.environ.copy()
            for name in ('CACHE_FILE', 'DATA_WAREHOUSE_FILE', 'HISTORY_DB_FILE',
                         'PROJECTION_DB_FILE', 'INTELLIGENCE_CHECKPOINT_FILE',
                         'METADATA_DB_FILE', 'ACCOUNT_DB_FILE', 'GLOBAL_EVIDENCE_FILE'):
                environment['DTOS_' + name] = str(root / (name.lower() + '.sqlite3'))
            environment['DTOS_HISTORY_STORAGE_ROOT'] = str(root)
            for _ in range(2):
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                process = subprocess.Popen(
                    [sys.executable, '-m', 'uvicorn', 'tools.storage_maintenance:app',
                     '--host', '127.0.0.1', '--port', str(port), '--log-level', 'error'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=environment,
                )
                try:
                    url = f'http://127.0.0.1:{port}'
                    for attempt in range(100):
                        if process.poll() is not None:
                            self.fail('Maintenance process exited before startup')
                        try:
                            with urlopen(url + '/health', timeout=.3) as response:
                                self.assertFalse(json.load(response)['application_ready'])
                            break
                        except URLError:
                            time.sleep(.05)
                    else:
                        self.fail('Maintenance startup timeout')
                    for method in ('GET', 'POST', 'DELETE', 'HEAD'):
                        with self.assertRaises(HTTPError) as caught:
                            urlopen(Request(url + '/api/leagues/resources', method=method), timeout=2)
                        with caught.exception as response:
                            self.assertEqual(response.code, 503)
                            self.assertEqual(response.headers['Cache-Control'], 'no-store')
                            body = response.read()
                            if method == 'HEAD':
                                self.assertEqual(body, b'')
                            else:
                                self.assertEqual(json.loads(body), {'status': 'maintenance', 'application_ready': False})
                finally:
                    process.terminate()
                    process.wait(timeout=10)
                self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
