"""Presentation-only rank availability; no ranking or value methodology changes."""
import unittest
from types import SimpleNamespace
from components.asset_intelligence import _scoped_rank_summary
from components.commissioner import front_office_summary
from src.ui.intelligence_presentation import exact_rank
from tests.html_document import _Document, _class, _elements, _text


class RankPresentationTests(unittest.TestCase):
    def test_non_ordinals_are_never_numeric_ranks(self):
        for value in (None, '', 0, '0', 'null', float('nan'), 'NaN', float('inf'), -1, 1.5, True):
            with self.subTest(value=value):
                self.assertEqual(exact_rank(value), 'Not ranked — insufficient evidence')
        self.assertEqual(exact_rank(3, 10), '#3 of 10')
        for value in (0, 'null', float('nan'), -1):
            html = _scoped_rank_summary({'global_market': {
                'overall': {'rank': value}, 'position': {'rank': value}}})
            self.assertIn('Overall rank unavailable', html)
            self.assertIn('Position rank unavailable', html)

    def test_commissioner_missing_ranks_do_not_imply_last_place(self):
        dimension = SimpleNamespace(grade='Unavailable', score=None, rank=None,
                                    league_size=10, percentile=None)
        html = front_office_summary({
            'active_front_office': SimpleNamespace(owner_name='Manager', team_name='Team', roster_id=1),
            'front_office_summary': dict(current_outlook=dimension, future_outlook=dimension,
                depth=dimension, asset_health=dimension, confidence=0,
                competitive_window='Unavailable', window_explanation='Insufficient evidence',
                record='0–0', power_ranking=None)})
        document = _Document(html).root
        # Current lineup rank is explicitly withheld. Unknown future and power
        # ranks do not become numeric tiles or imply last place.
        office = _class(document, 'cd-office')
        self.assertIn('Lineup comparison not ready', _text(_class(office, 'cd-office-main')))
        self.assertIn('League rank is withheld until a supported comparison is ready.', html)
        metrics = [item for item in _elements(office, direct=True) if 'cd-metric' in item['attrs'].get('class', '').split()]
        labels = [_text(child) for item in metrics for child in _elements(item, direct=True) if child['tag'] == 'span']
        self.assertEqual(labels, ['Record'])
        self.assertNotIn('Future outlook', labels)
        self.assertNotIn('Projected lineup rank', labels)
        self.assertIn('Outlook not established', html)
        self.assertNotIn('#None', html)
        self.assertNotIn('#10', html)
        self.assertIn('Selected league · Projection week not established', html)
        self.assertIn('Roster projection coverage is not established.', html)
        self.assertNotIn('0% confidence', html)

    def test_missing_position_and_universe_are_not_numbers(self):
        html = _scoped_rank_summary({'global_market': {'overall': {'rank': 15}}})
        self.assertIn('Global provider Market', html)
        self.assertIn('#15 overall', html)
        self.assertIn('Position rank unavailable', html)
        self.assertIn('Ranked-universe coverage unavailable', html)
        self.assertNotIn('#None', html)
        self.assertNotIn('0 ranked players', html)

    def test_independent_position_rank_is_not_hidden_by_missing_overall(self):
        html = _scoped_rank_summary({'league_adjusted': {'position': {'rank': 3, 'position': 'QB'}}})
        self.assertIn('Overall rank unavailable', html)
        self.assertIn('QB #3', html)

    def test_source_supported_zero_universe_is_preserved(self):
        html = _scoped_rank_summary({'global_market': {'overall': {'ranked_count': 0}}})
        self.assertIn('0 ranked players', html)
