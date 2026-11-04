import unittest
from src.ui.event_presentation import event_presentation


class EventPresentationTests(unittest.TestCase):
    def item(self):
        return {'qualifies': True, 'kind': 'current_state', 'identity': 'A:1:2:coverage',
                'family': 'team_lineup', 'reference': 'team/1/week/2', 'generation': 'g',
                'source_methodology': 'm', 'week': 2, 'unsupported_slots': ['QB'],
                'reason': 'COVERAGE', 'confidence': 'partial', 'title': 'Incomplete projection',
                'why': 'Required slot evidence missing.', 'href': '/teams/1'}

    def test_state_has_no_fabricated_prior_or_clock(self):
        event = event_presentation(self.item(), league_id='A', roster_id=1)
        self.assertIsNone(event.prior)
        self.assertEqual(event.comparability, 'not_applicable_current_state')
        self.assertEqual(event.as_of, 'prepared-week:2')

    def test_change_requires_pair_and_scope(self):
        item = self.item()
        for update in ({'kind': 'change_event'}, {'league_id': 'B'}, {'href': '//external.invalid'}):
            with self.assertRaises(ValueError):
                event_presentation({**item, **update}, league_id='A', roster_id=1)
