import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import dtos_app


class GlobalEvidenceBackgroundTests(unittest.IsolatedAsyncioTestCase):
    async def test_global_season_not_active_league_drives_single_job(self):
        delays = []

        async def sleep(delay):
            delays.append(delay)
            if len(delays) > 1:
                raise asyncio.CancelledError()

        with patch.dict(dtos_app.STATE, {'data': {'nfl_state': {'season': '2032'},
                                                'league': {'season': '2021', 'league_id': 'historical'}}}), \
             patch('dtos_app.asyncio.sleep', side_effect=sleep), \
             patch.object(dtos_app.lifecycle_coordinator, 'startup_complete', return_value=True), \
             patch('services.global_evidence_ingestion.ingest_in_background',
                   new=AsyncMock(return_value={'status': 'complete'})) as ingest:
            with self.assertRaises(asyncio.CancelledError):
                await dtos_app.refresh_global_evidence()
        self.assertEqual(ingest.await_count, 1)
        self.assertEqual(ingest.call_args.args[0], 2032)
        self.assertEqual(delays, [30, 21600])
