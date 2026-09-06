"""Focused no-secret transport inventory and fixture execution boundaries."""
import unittest
from unittest.mock import patch

from tools.validation import dins_split_boundary as split


class SplitBoundaryTests(unittest.TestCase):
    def test_resource_inventory_does_not_authorize_external_or_mutating_targets(self):
        parser = split.Resources()
        parser.feed('<link href="/static/css/theme.css?v=1"><img src="https://sleepercdn.com/a.jpg">'
                    '<a href="/teams/4">Team</a><a href="/sync">No</a>'
                    '<a href="https://dtos.fixture:8768/teams/5">Team</a>'
                    '<a href="https://private.invalid/account">No</a>')
        self.assertEqual(parser.targets, {"/static/css/theme.css?v=1", "/teams/4", "/teams/5"})

    def test_capture_rejects_receiving_any_inspection_credential(self):
        with patch.dict("os.environ", {"DTOS_INSPECTION_AUTH_TOKEN": "fixture-value"}):
            with self.assertRaisesRegex(AssertionError, "must not receive"):
                split.capture()

    def test_fixture_orchestrator_cannot_run_in_render(self):
        with patch.dict("os.environ", {"RENDER": "true"}):
            with self.assertRaisesRegex(RuntimeError, "fixture-only"):
                split.main()


if __name__ == "__main__":
    unittest.main()
