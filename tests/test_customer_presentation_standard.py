"""Display-only shared contracts; source data and clocks remain unchanged."""
import unittest
from src.ui.customer_experience import plain_reason, readable_time, source_details
from src.ui.design_system import account_page_header, page_header, manager_navigation


class CustomerPresentationStandardTests(unittest.TestCase):
    def test_aware_clocks_use_explicit_utc_without_changing_exact_source(self):
        raw = '2026-11-13T01:05:33.123456-05:00'
        self.assertEqual(readable_time(raw), 'Nov 13, 2026 · 06:05 UTC')
        html = page_header('League History', league_name='Fixture', last_updated=raw)
        self.assertIn(raw, html)
        self.assertIn('Nov 13, 2026 · 06:05 UTC', html)
        self.assertIn('Exact sync time', html)

    def test_date_only_naive_unknown_clocks_do_not_gain_precision(self):
        self.assertEqual(readable_time('2026-11-13'), 'Nov 13, 2026')
        self.assertEqual(readable_time('2026-11-13 06:05 UTC'), 'Nov 13, 2026 · 06:05 UTC')
        self.assertIn('timezone not recorded', readable_time('2026-11-13T01:05:00'))
        for value in (None, '', 'unknown', 'not a date'):
            self.assertEqual(readable_time(value), 'Time not recorded')

    def test_disclosures_are_closed_and_source_text_is_not_reinterpreted(self):
        html = source_details('<p>RETAINED / NOT REVALIDATED · -2.35 · 0</p>', summary='Sources <and> limits')
        self.assertIn('<summary>Sources &lt;and&gt; limits</summary>', html)
        self.assertNotIn(' open', html)
        self.assertIn('RETAINED / NOT REVALIDATED · -2.35 · 0', html)

    def test_translation_preserves_specific_missing_and_unrelated_facts(self):
        self.assertEqual(plain_reason('Compatible league/week/scoring projection publication unavailable.'),
                         'Projections are not ready for this league, week and scoring.')
        self.assertEqual(plain_reason('No DEF projection for Week 10; zero is 0; -2.35'),
                         'No DEF projection for Week 10; zero is 0; -2.35')

    def test_account_and_primary_navigation_keep_existing_boundaries(self):
        self.assertIn('Your account', account_page_header('Sign in', purpose='Return to your team.'))
        primary = manager_navigation('League').split('</nav>', 1)[0]
        self.assertEqual(primary.count('<a '), 5)
        for label in ('Home', 'My Team', 'Trade', 'League', 'Market'):
            self.assertIn(label + '</a>', primary)
        self.assertNotIn('/fois', primary)
