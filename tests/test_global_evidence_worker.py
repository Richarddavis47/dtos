import json
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

import httpx

from src.global_evidence_worker import run_job


class GlobalEvidenceWorkerTests(unittest.TestCase):
    def test_worker_import_does_not_load_application_or_legacy_warehouse(self):
        result = subprocess.run([sys.executable, '-c',
            "import sys; import src.global_evidence_worker; "
            "assert 'dtos_app' not in sys.modules; "
            "assert 'src.core.data_platform.defaults' not in sys.modules"],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_isolated_job_uses_only_public_sources_and_reclaims_temporary_input(self):
        def source(request):
            self.assertNotIn('authorization', request.headers)
            self.assertNotIn('cookie', request.headers)
            if request.url.path.endswith('/players/nfl'):
                return httpx.Response(200, json={'1': {'player_id': '1'}})
            if request.url.path.endswith('db_playerids.csv'):
                return httpx.Response(200, text='sleeper_id,gsis_id\n1,00-1\n')
            if request.url.path.endswith('games.csv'):
                return httpx.Response(200, text='game_id,season,week,gameday,gametime,home_team,away_team\ng1,2025,1,2025-09-07,13:00,BUF,NYJ\n')
            if request.url.path.endswith('stats_player_week_2025.csv'):
                return httpx.Response(200, text='player_id,season,week,game_id,receptions\n00-1,2025,1,g1,5\n')
            raise AssertionError('Unexpected provider route')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'global.sqlite3'
            with httpx.Client(transport=httpx.MockTransport(source)) as client:
                result = run_job({'protocol': 1, 'season': 2025, 'database': str(path),
                                  'temporary_directory': directory}, client)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['production']['created'], 1)
            self.assertTrue(path.is_file())
            self.assertTrue({item.name for item in Path(directory).iterdir()}.issubset(
                {'global.sqlite3', 'global.sqlite3.storage-lock'}))
            self.assertLess(len(json.dumps(result)), 8192)

    def test_private_or_unexpected_input_is_rejected(self):
        with httpx.Client() as client:
            with self.assertRaises(ValueError):
                run_job({'protocol': 1, 'season': 2025, 'database': '/not-used', 'league_id': 'private'}, client)

    def test_missing_season_file_preserves_schedule_without_claiming_production(self):
        from unittest.mock import patch
        from src.core.data_platform.normalization.identity import PlayerIdentityResolver
        with tempfile.TemporaryDirectory() as directory, httpx.Client(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'1': {}}))) as client:
            response = httpx.Response(404, request=httpx.Request('GET', 'https://source.test/season'))
            with patch('src.global_evidence_worker.load_crosswalk', return_value=(PlayerIdentityResolver(), {})), \
                 patch('src.global_evidence_worker.ingest_schedule', return_value=({'games': 285}, {})), \
                 patch('src.global_evidence_worker.ingest_production', side_effect=httpx.HTTPStatusError(
                     'missing', request=response.request, response=response)):
                result = run_job({'protocol': 1, 'season': 2026,
                    'database': str(Path(directory) / 'global.sqlite3'), 'temporary_directory': directory}, client)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['production']['status'], 'unavailable')
            self.assertEqual(result['schedule']['games'], 285)
