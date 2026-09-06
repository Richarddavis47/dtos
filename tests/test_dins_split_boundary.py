"""Focused no-secret transport inventory and fixture execution boundaries."""
import unittest
from unittest.mock import patch

from tools.validation import dins_split_boundary as split
from tools.inspection.loopback_relay import RelayPolicy


class SplitBoundaryTests(unittest.TestCase):
    def test_rendered_workspace_is_exact_and_never_a_generic_proxy(self):
        parser = split.Resources()
        parser.feed('<section data-front-office="1" data-workspace-endpoint="/api/trades/workspace"></section>')
        expected = "/api/trades/workspace?front_office=1"
        self.assertEqual(parser.targets, {expected})
        policy = RelayPolicy(sorted(parser.targets), "fixture-only-credential-at-least-32-chars", 10000)
        self.assertTrue(policy.permits("GET", expected))
        self.assertTrue(policy.permits("HEAD", expected))
        for target in ("/api/trades/workspace", expected + "&league=other", expected + "&account=other",
                       "/api/trades/workspace?front_office=2", "/api/account/leagues",
                       "/api/trades/evaluate", "https://example.org/", "/api/admin", "/sync"):
            self.assertFalse(policy.permits("GET", target), target)
        for method in ("POST", "PATCH", "DELETE", "CONNECT"):
            self.assertFalse(policy.permits(method, expected))

    def test_dynamic_endpoint_or_manager_injection_never_expands_inventory(self):
        for endpoint, manager in (("/api/account/leagues", "1"), ("https://evil.invalid/api", "1"),
                                  ("/api/trades/workspace", "1&league=other"),
                                  ("/api/trades/workspace", "-1"), ("/api/trades/workspace", "0")):
            parser = split.Resources()
            parser.feed(f'<section data-front-office="{manager}" data-workspace-endpoint="{endpoint}"></section>')
            self.assertEqual(parser.targets, set())

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
