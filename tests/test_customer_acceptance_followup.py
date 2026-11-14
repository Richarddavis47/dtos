"""Presentation-only acceptance: material facts remain visible and inspectable."""
import unittest
from src.ui import recommendation_panel
from src.ui.customer_experience import plain_reason
from src.ui.front_office_brief import cards

class CustomerAcceptanceFollowupTests(unittest.TestCase):
    def test_backup_points_translation_preserves_qualification(self):
        raw = 'Useful legal-replacement production falls 2.25 points per supported week; participation is unknown.'
        shown = plain_reason(raw)
        self.assertIn('projected points from eligible backups', shown)
        self.assertIn('2.25 points per supported week; participation is unknown.', shown)
        html = recommendation_panel(title='Review', recommendation=raw, confidence=55,
            primary_reason=raw, evidence=(raw,), expected_impact='Unknown',
            action_label='Review trade', action_href='/trades', limitations=('Incoming Player is on IR.',))
        self.assertIn(raw, html)
        self.assertLess(html.index('Incoming Player is on IR.'), html.index('<details>'))
        self.assertIn('Original assessment record', html)

        from src.ui.home_trade_opportunities import cards as home_cards
        home = home_cards([dict(home_offer='fixture-only', evaluation=dict(
            recommendation='REJECT', major_drawback=raw,
            why_you_would_do_it='No supported gain.', dominant_reason=raw))], 1)
        primary, details = home.split('<details>', 1)
        self.assertNotIn('legal-replacement', primary)
        self.assertIn('projected points from eligible backups', primary)
        self.assertIn('2.25 points per supported week; participation is unknown.', primary)
        self.assertIn(raw, details)

    def test_repeated_brief_explanation_does_not_erase_a_distinct_risk(self):
        item = dict(family='need', title='Receiver cover', reason='WR cover is limited.',
                    drawback='Player A is out.', details=['WR cover is limited.', 'Player A is out.',
                    'Player B has no projection.', 'Player B has no projection.'],
                    href='/trades', action='Explore WR trades')
        html = cards([item])
        self.assertEqual(html.count('WR cover is limited.'), 1)
        self.assertEqual(html.count('Player A is out.'), 1)
        self.assertEqual(html.count('Player B has no projection.'), 1)
        self.assertIn('<details>', html)

    def test_duplicate_player_notes_keep_zero_and_distinct_risks(self):
        from src.ui.player_projections import player_projection_panel
        view = dict(player_id='fixture', week=8, weeks=[8], season=2026,
                    league_id='fixture', generation='fixture-generation', value=0,
                    display='0', availability='available', confidence=100,
                    reason='Player A is out.', participation_note='Player A is out.',
                    eligibility_note='Player B has no projection.')
        html = player_projection_panel(view)
        default = html.split('<details', 1)[0]
        self.assertEqual(default.count('Player A is out.'), 1)
        self.assertIn('Player B has no projection.', default)
        self.assertIn('>0</strong>', default)
        self.assertEqual(view['value'], 0)
