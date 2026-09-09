"""Read-only global evidence derivation stays scoped to the selected league."""
import tempfile
import unittest
from pathlib import Path

from services.global_evidence import canonical_player_evidence
from src.core.data_platform.global_evidence import GlobalEvidenceStore
from src.core.data_platform.global_production import GlobalProduction
from src.core.data_platform.normalization.identity import PlayerIdentityResolver


class CanonicalPlayerEvidenceTests(unittest.TestCase):
    def test_scoring_is_league_scoped_and_seasons_do_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'global.sqlite3'
            store = GlobalEvidenceStore(path)
            GlobalProduction(store).publish_batch(
                [{'provider': 'nflverse', 'provider_player_id': 'gsis-1', 'game_id': 'game',
                  'season': 2025, 'week': 1, 'raw_stats': {'rec': 5}}],
                identities=PlayerIdentityResolver({'1': {'gsis_id': 'gsis-1'}}),
                game_dates={'game': '2025-09-01T00:00:00Z'},
                retrieved_at='2026-01-01T00:00:00Z')
            for league_id, multiplier in [('A', 1), ('B', .5)]:
                data = {'league': {'league_id': league_id, 'season': '2025'},
                        'scoring_settings': {'rec': multiplier}}
                result = canonical_player_evidence('1', data, expected_league_id=league_id,
                    path=path, as_of='2026-02-01T00:00:00Z')
                self.assertEqual(result['production']['ppg'], 5 * multiplier)
                self.assertEqual(result['provider_calls'], 0)
                data['league']['season'] = '2026'
                result = canonical_player_evidence('1', data, expected_league_id=league_id,
                    path=path, as_of='2026-02-01T00:00:00Z')
                self.assertIsNone(result['production']['ppg'])
            self.assertEqual(store.counts(), {'production': 1})
            store.record_source_check('nflverse/production/2025', source_identity='later',
                checked_at='2026-03-01T00:00:00Z', status='complete', details={})
            data = {'league': {'league_id': 'A', 'season': '2025'}, 'scoring_settings': {'rec': 1}}
            historical = canonical_player_evidence('1', data, expected_league_id='A',
                path=path, as_of='2026-02-01T00:00:00Z')
            self.assertIsNone(historical['source_check'])
            self.assertEqual(historical['production']['ppg'], 5)
            self.assertNotEqual(historical['availability_detail']['reason'], 'observation_after_as_of')
            data['players'] = {'1': {'team': 'FUTURE'}}
            historical = canonical_player_evidence('1', data, expected_league_id='A',
                path=path, as_of='2026-02-01T00:00:00Z')
            self.assertEqual(historical['schedule']['reason'], 'team_identity_at_boundary_unavailable')
            self.assertNotEqual(historical['schedule']['team_basis'], 'current_sleeper_catalog')

    def test_context_mismatch_fails_closed_and_missing_settings_are_not_zero(self):
        data = {'league': {'league_id': 'A', 'season': '2025'}}
        with self.assertRaises(ValueError):
            canonical_player_evidence('1', data, expected_league_id='B')
        self.assertEqual(canonical_player_evidence('1', data, expected_league_id='A')['reason'],
                         'league_scoring_unknown')

    def test_read_does_not_create_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'absent.sqlite3'
            data = {'league': {'league_id': 'A', 'season': '2025'}, 'scoring_settings': {'rec': 1}}
            result = canonical_player_evidence('1', data, expected_league_id='A', path=path)
            self.assertEqual(result['availability'], 'not_connected')
            self.assertFalse(path.exists())
