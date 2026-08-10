import unittest

from src.ui.intelligence_presentation import (
    available, exact_rank, historical_availability, human_status,
    matchup_state, technical_details,
)


class IntelligencePresentationTests(unittest.TestCase):
    def test_statuses_are_human_readable(self):
        self.assertEqual("Completed with pending season", human_status("completed_with_pending"))
        self.assertEqual("Identity not verified", human_status("unresolved"))

    def test_missing_values_explain_availability(self):
        self.assertEqual("Provider has not published this field", available(None, reason="Provider has not published this field"))

    def test_rank_is_explicit(self):
        self.assertEqual("#2 of 10", exact_rank(2, 10))
        self.assertIn("insufficient evidence", exact_rank(None))

    def test_historical_availability_uses_seasons(self):
        self.assertEqual("2021–2025 complete; 2026 pending provider evidence", historical_availability({"completed_seasons": [2021, 2022, 2023, 2024, 2025], "pending_seasons": [2026]}))

    def test_technical_details_are_collapsed_and_escaped(self):
        html = technical_details((("Canonical ID", "<player>"),))
        self.assertIn("<details", html)
        self.assertIn("Technical Details", html)
        self.assertIn("&lt;player&gt;", html)

    def test_preseason_zero_is_not_a_tie(self):
        self.assertEqual("Not Started", matchup_state(left=0, right=0, week=1, season_started=False))
        self.assertEqual("Tied", matchup_state(left=10, right=10, week=8))


if __name__ == "__main__":
    unittest.main()
