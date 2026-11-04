"""Sparse projection retention through the active canonical event pipeline."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.models import ProvenanceType
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.store import IntelligenceCheckpointStore


class ProjectionEventRetentionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'memory.sqlite3'
        self.store = IntelligenceCheckpointStore(self.path)
        self.pipeline = CheckpointPipeline(IntelligenceMemoryService(self.store))
        self.data = {'league': {'league_id': 'A', 'season': 2026}, 'week': 2, 'scoring_settings': {}}
        scope = self.pipeline._context(self.data, provenance=ProvenanceType.LIVE_CAPTURED)
        self.data['projection_intelligence'] = {
            'league_id': 'A', 'generated_at': '2026-09-01T10:00:00+00:00',
            'season': 2026, 'week': 2, 'scoring_settings': {},
            'scoring_profile_id': scope['scoring_profile_id'],
            'projection_snapshot_id': 'projection:accepted',
            'players': {'1': {'canonical_projection': 0, 'season': 2026, 'week': 2,
                'generated_at': '2026-09-01T10:00:00+00:00',
                'source_timestamp': '2026-08-31T10:00:00+00:00',
                'scoring_profile_id': scope['scoring_profile_id'],
                'projection_snapshot_id': 'projection:accepted',
                'sleeper_evidence_fingerprint': 'source:accepted'}}}
        self.event = {'transaction_id': 'trade:1', 'type': 'trade', 'status': 'complete',
                      'created': '2026-09-01T11:00:00+00:00', 'adds': {'1': 2}}

    def captured(self):
        return self.store.checkpoints(asset_id='player:1', league_id='A')

    def test_completed_event_retains_only_affected_fact_and_replay_is_stable(self):
        self.pipeline.ingest_transactions(self.data, [self.event])
        rows = self.captured()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0].observations), 1)
        self.assertEqual(rows[0].observations[0].normalized_value, 0)
        before = self.path.read_bytes()
        for n in range(100):
            self.data['projection_intelligence']['players']['1']['canonical_projection'] = n
            self.pipeline.ingest_transactions(self.data, [self.event])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.captured()[0].observations[0].normalized_value, 0)

    def test_uncompleted_or_unsupported_events_do_not_retain_projection(self):
        for status, kind in [(None, 'trade'), ('failed', 'waiver'), ('pending', 'trade'), ('complete', 'commissioner')]:
            event = {**self.event, 'transaction_id': str(status) + kind, 'status': status, 'type': kind}
            self.pipeline.ingest_transactions(self.data, [event])
        self.assertTrue(all(not row.observations for row in self.captured()))

    def test_future_missing_naive_or_invalid_time_cannot_backfill_projection(self):
        for event_time in ['2026-09-01T09:59:59+00:00', None, 'bad', '2026-09-01T11:00:00']:
            self.assertEqual(self.pipeline._event_projection_observations(
                self.data, 'player:1', event_time=event_time), ())

    def test_wrong_league_season_or_scoring_cannot_enter_checkpoint(self):
        for field, value in [('season', 2025), ('week', 3), ('scoring_profile_id', 'other'),
                             ('generated_at', None), ('projection_snapshot_id', None),
                             ('sleeper_evidence_fingerprint', None)]:
            data = copy.deepcopy(self.data)
            data['projection_intelligence']['players']['1'][field] = value
            self.assertEqual(self.pipeline._event_projection_observations(
                data, 'player:1', event_time=self.event['created']), ())
        data = copy.deepcopy(self.data)
        data['projection_intelligence']['league_id'] = 'B'
        self.assertEqual(self.pipeline._event_projection_observations(
            data, 'player:1', event_time=self.event['created']), ())

    def test_refresh_without_event_has_no_historical_projection_checkpoint(self):
        for _ in range(100):
            self.pipeline.ingest_transactions(self.data, [])
        self.assertEqual(len(self.captured()), 0)

    def test_actual_projection_publisher_identity_and_restart(self):
        from src.core.projection_intelligence.service import ProjectionService
        self.data['players'] = [{'id': '1', 'position': 'QB'}]
        self.data['scoring_settings'] = {'pass_yd': .04}
        service = ProjectionService(Path(self.directory.name) / 'projection.sqlite3', league_id='A')
        with patch('src.core.projection_intelligence.service._now', return_value='2026-09-01T10:00:00+00:00'):
            service.publish_horizon({2: [{'player_id': '1', 'season': 2026, 'week': 2,
                                           'stats': {'pass_yd': 250}}]},
                                    data=self.data, league_id='A', season=2026, current_week=2)
        self.pipeline.ingest_transactions(self.data, [self.event])
        row = self.captured()[0]
        self.assertEqual(row.observations[0].normalized_value, 10)
        restarted = IntelligenceCheckpointStore(self.path)
        self.assertEqual(restarted.checkpoints(league_id='A')[0], row)
