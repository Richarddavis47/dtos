"""v1.10.63 authenticated Trade smoke-contract regressions."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tools.validation.smoke_http import inspection_roster_id, validate_trade_manager_context


class TradeSmokeContractTests(unittest.TestCase):
    def test_authenticated_membership_controls_trade_without_chooser(self) -> None:
        validate_trade_manager_context(
            b"<h2>Trade Center</h2>", {"active_front_office": 7}, 7,
        )

    def test_authenticated_membership_rejects_wrong_or_manual_context(self) -> None:
        with self.assertRaisesRegex(AssertionError, "does not match"):
            validate_trade_manager_context(b"Trade Center", {"active_front_office": 8}, 7)
        with self.assertRaisesRegex(AssertionError, "asked to choose"):
            validate_trade_manager_context(b"Choose your franchise", {"active_front_office": 7}, 7)

    def test_unresolved_context_requires_resolution_and_never_guesses(self) -> None:
        validate_trade_manager_context(
            b"Choose your franchise",
            {"status": "manager_context_required", "active_front_office": None},
            None,
        )
        with self.assertRaisesRegex(AssertionError, "guessed"):
            validate_trade_manager_context(
                b"Choose your franchise",
                {"status": "manager_context_required", "active_front_office": 1},
                None,
            )

    def test_inspection_context_requires_complete_membership_identity(self) -> None:
        complete = {
            "DTOS_INSPECTION_AUTH_TOKEN": "opaque",
            "DTOS_INSPECTION_LEAGUE_ID": "league-a",
            "DTOS_INSPECTION_ROSTER_ID": "42",
        }
        with patch.dict(os.environ, complete, clear=True):
            self.assertEqual(inspection_roster_id(), 42)
        for missing in complete:
            values = {key: value for key, value in complete.items() if key != missing}
            with self.subTest(missing=missing), patch.dict(os.environ, values, clear=True):
                self.assertIsNone(inspection_roster_id())


if __name__ == "__main__":
    unittest.main()
