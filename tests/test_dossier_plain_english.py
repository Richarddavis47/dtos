"""Real dossier producer → HTTP text, with accepted facts and reports left intact."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import os
import unittest
from unittest.mock import patch

from components.asset_intelligence import player_dossier
from services.asset_explanations import player_profile_explanation
from services.asset_intelligence import build_player_dossier
from src.core.asset_intelligence.models import AssetEvaluation, Evidence
from src.core.data_platform import data_platform
from src.core.data_platform.storage import SnapshotWarehouse
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from tests import test_player_api as api_fixtures


FORBIDDEN = ('Long-term scalar unavailable', 'No evidence-backed strength exceeds the v1 baseline',
             'No current evidence-backed weakness exceeds the v1 threshold', 'Consult canonical_evidence.schedule')


class DossierPlainEnglishTests(unittest.TestCase):
    def setUp(self):
        self.engine = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache())
        self.enterContext(patch('services.asset_intelligence.intelligence_orchestrator', self.engine))
        self.enterContext(patch.object(data_platform, 'warehouse', SnapshotWarehouse()))
        self.fixture = api_fixtures.PlayerApiContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.client.close)
        self.fixture.data['league']['name'] = 'Example Dynasty'

    def page(self):
        response = self.fixture.client.get('/players/player%20one?front_office=1&from_team=1')
        self.assertEqual(response.status_code, 200)
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, response.text)
        return response.text

    def test_missing_outlook_is_not_a_negative_grade_on_real_html(self):
        html = self.page()
        self.assertIn('A reliable multi-season outlook is not available.', html)
        self.assertIn('not a negative grade', html)
        self.assertIn('No specific weakness is established', html)
        self.assertIn('Player One', html)
        self.assertIn('/teams/1#full-roster', html)
        folder = os.getenv('DTOS_DOSSIER_EVIDENCE')
        if folder:
            root = Path(folder)
            root.mkdir(parents=True, exist_ok=True)
            (root / 'after-player.html').write_text(html)

    def test_missing_age_differs_from_observed_age_or_injury_concerns(self):
        self.fixture.data['players']['player one'].pop('age')
        missing = self.page()
        self.assertIn('Age-related assessment is incomplete because age is missing.', missing)
        self.assertNotIn('age-related warning, not a prediction', missing)
        self.fixture.data['players']['player one'].update(age=36, injury_status='Out')
        negative = self.page()
        self.assertIn('age-related warning, not a prediction of retirement', negative)
        self.assertIn('A current injury designation increases observable availability risk.', negative)
        self.assertNotIn('No specific weakness is established', negative)

    def test_supported_strength_is_not_replaced_by_missing_evidence_fallback(self):
        # Controlled admitted source evidence exercises the real report producer.
        # No actual player's historical performance is manufactured or persisted.
        supported = AssetEvaluation('Intrinsic dynasty utility', None, 0,
            'Recorded production is available; future seasons remain uncertain.',
            (Evidence('Observed production', '20 league points/game', 3,
                      'Recorded production supports a useful current contribution.', 'Disposable admitted fixture'),))
        with patch('src.core.asset_intelligence.players.player_evaluator.dynasty_value', return_value=supported):
            html = self.page()
        self.assertIn('Recorded production supports a useful current contribution.', html)
        self.assertNotIn('This dossier has not established a clear player advantage', html)
        self.assertIn('Recorded production is available; future seasons remain uncertain.', html)

    def test_known_bye_and_missing_bye_are_not_interchanged(self):
        unavailable = self.page()
        self.assertIn('His bye week is not confirmed in this player record.', unavailable)
        self.assertIn('missing schedule information does not mean he has no bye', unavailable)
        self.fixture.data['players']['player one']['bye_week'] = 14
        supported = self.page()
        self.assertIn('<b>Bye:</b> 14', supported)
        self.assertIn('Bye: 14', supported)
        self.assertNotIn('His bye week is not confirmed', supported)

    def test_rendering_does_not_mutate_numbers_identity_or_call_expensive_services(self):
        report, team, teams = build_player_dossier(self.fixture.data, 'player one', 1)
        before = deepcopy(asdict(report))
        data_before = deepcopy(self.fixture.data)
        with patch.object(self.engine, 'analyze', side_effect=AssertionError('render analysis')), \
                patch.object(data_platform, 'fetch', side_effect=AssertionError('render provider')):
            for _ in range(10):
                player_dossier(report, team, teams)
                player_profile_explanation(report, league_id='league-1')
        self.assertEqual(asdict(report), before)
        self.assertEqual(self.fixture.data, data_before)
        self.assertEqual(report.profile.player_id, 'player one')

    def test_available_zero_evidence_is_preserved_not_reclassified_missing(self):
        from src.ui.player_dossier_text import availability_text, outlook_text
        from src.core.asset_intelligence import AssetContext, evaluate_player
        context = AssetContext('league-1', 1, {}, canonical_projection={
            'league_id': 'league-1', 'week': 2, 'players': {'p': {'week': 2, 'weekly_projected_points': 0}}})
        report = evaluate_player({'id': 'p', 'position': 'QB'}, context)
        projection = next(e for e in report.core_values.redraft.evidence if e.factor == 'Canonical weekly projection')
        self.assertTrue(projection.available)
        self.assertEqual(projection.observed_value, '0')
        self.assertIn('weekly projection', outlook_text(report.long_term_outlook))
        self.assertEqual(availability_text('projection', 'Available · Sleeper week 2 · 0 points'),
                         'Available · Sleeper week 2 · 0 points')

    def test_present_but_unverified_age_does_not_claim_missing_birth_evidence(self):
        from src.ui.player_dossier_text import weaknesses_text
        report, _, _ = build_player_dossier(self.fixture.data, 'player one', 1)
        evidence = (Evidence('Age-decline risk', 'Not verified', 0,
                             'Unsupported position context.', 'Disposable fixture', False),)
        report = replace(report, risk=replace(report.risk, evidence=evidence))
        self.assertIsNotNone(report.profile.age)
        text = ' '.join(weaknesses_text(report))
        self.assertIn('could not be verified', text)
        self.assertNotIn('age is missing', text)


if __name__ == '__main__':
    unittest.main()
