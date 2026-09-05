import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, unquote, urlsplit

from tools.validation.capture_restart_evidence import capture, provider_digest, validate_origin


class RestartCaptureTests(unittest.TestCase):
    def test_canonical_absent_brain_is_evidence_not_a_fabricated_record(self):
        reader = self.reader()
        def absent(path):
            if path.startswith("/api/brain/assets/"):
                body = json.dumps({"detail": "The asset is not available in the synchronized Brain snapshot."}).encode()
                raise HTTPError(path, 404, "Not Found", {}, io.BytesIO(body))
            return reader(path)
        with tempfile.TemporaryDirectory() as folder:
            result = capture(absent, Path(folder) / "capture.json")
            self.assertTrue(result["capture"]["complete"])

    def test_production_shaped_canonical_records_fit_bounded_capture(self):
        from tools.validation import generate_sanitized_market_fixture as fixture
        from src.core.valuation.universe import ValuationUniverse
        from src.core.brain import brain_service
        from src.core.asset_market.engine import _summary
        with tempfile.TemporaryDirectory() as folder, patch.object(fixture, "ASSET_COUNT", 1009):
            data = fixture._cache(Path(folder) / "fixture.json")
            # The lifecycle fixture intentionally seeds one controlled Brain asset.
            # Restart evidence must also fit a populated production Brain universe.
            template = data["valuation_intelligence"]["assets"]["player:10213"]
            data["valuation_intelligence"]["assets"] = {
                "player:" + player_id: {**copy.deepcopy(template), "asset_id": "player:" + player_id}
                for player_id in data["players"]
            }
            valuation = list(ValuationUniverse.streaming(data, {}).iter_assets())
            brain = brain_service(data)
            market = [_summary(asset, brain.asset(asset["asset_id"])) for asset in valuation]
            base = self.reader()
            def read(path):
                parsed = urlsplit(path)
                query = parse_qs(parsed.query)
                rows = {"/api/valuation/assets": valuation, "/api/market/assets": market}.get(parsed.path)
                if rows is not None:
                    offset = int(query["offset"][0])
                    limit = int(query["limit"][0])
                    return {"total": len(rows), "assets": rows[offset:offset + limit]}
                if path.startswith("/api/brain/assets/"):
                    return {"asset": brain.asset(unquote(path.split("/assets/", 1)[1]))}
                result = base(path)
                if path == "/api/market/health":
                    result["semantic_identity"]["provider_evidence_digest"] = provider_digest(valuation)
                return result
            output = Path(folder) / "capture.json"
            result = capture(read, output)
            self.assertEqual(result["capture"]["asset_count"], len(valuation))
            self.assertGreater(len(valuation), 1000)
            self.assertLess(output.stat().st_size, 64 * 1024 * 1024)

    def test_credentials_are_bound_to_configured_origin(self):
        trusted = "https://dtos.onrender.com"
        validate_origin(trusted, trusted)
        for candidate in ("https://example.com", trusted + "/redirect",
                          "http://dtos.onrender.com", "https://user@dtos.onrender.com",
                          trusted + "?next=evil", trusted + "#fragment"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_origin(candidate, trusted)

    def reader(self, *, move=False, wrong_league=False):
        boundaries = 0

        def read(path):
            nonlocal boundaries
            if path == "/api/account":
                boundaries += 1
                return {"status": "authenticated", "account": {"username": "private"},
                        "active_league": {"league_id": "A", "roster_id": 1}}
            if path == "/api/market/health":
                return {"status": "ready", "market_generation": "generation",
                        "semantic_identity": {"brain_semantic_output_digest": "b" * 64,
                            "asset_universe_digest": "a" * 64, "ownership_dependency_digest": "c" * 64,
                            "provider_evidence_digest": provider_digest([{"asset_id": "player:1", "providers": []}])},
                        "cache": {"requested_generation": "next" if move and boundaries > 1 else "same"}}
            if path == "/api/brain/health":
                return {"generated_at": "brain-generation"}
            if path == "/api/projections/health":
                return {"active_snapshot_id": "projection"}
            if path.startswith("/api/projections?"):
                return {"projection": {"league_id": "B" if wrong_league else "A", "players": []},
                        "pagination": {"total": 0}}
            if path.startswith("/api/valuation/normalization-inputs"):
                return {"league_id": "A", "synchronization_generation": "sync",
                        "total": 1, "records": [{"provider": "FantasyCalc", "source_confidence": 85}]}
            if path.startswith("/api/valuation/assets?"):
                return {"total": 1, "assets": [{"asset_id": "player:1", "providers": []}]}
            if path.startswith("/api/market/assets?"):
                return {"total": 1, "assets": [{"asset_id": "player:1", "value": 500}]}
            if path == "/api/brain/assets/player%3A1":
                return {"asset": {"asset_id": "player:1", "value": 500}}
            if path == "/api/valuation/calibration":
                return {"state": "calibrated"}
            if path == "/api/valuation/providers":
                return {"generation_timestamp": "providers", "providers": []}
            raise AssertionError(path)
        return read

    def test_complete_capture_persists_only_sanitized_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "before.json"
            result = capture(self.reader(), path)
            self.assertTrue(result["capture"]["complete"])
            self.assertEqual(json.loads(path.read_text()), result)
            self.assertNotIn('"private"', path.read_text())

    def test_moving_boundary_is_retained_before_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "before.json"
            with self.assertRaisesRegex(ValueError, "boundary moved"):
                capture(self.reader(move=True), path)
            self.assertFalse(json.loads(path.read_text())["capture"]["complete"])

    def test_foreign_projection_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "before.json"
            with self.assertRaisesRegex(ValueError, "another league"):
                capture(self.reader(wrong_league=True), path)
            evidence = json.loads(path.with_suffix(".failure.json").read_text())
            self.assertFalse(evidence["capture"]["complete"])
            self.assertTrue(evidence["requests"])
            self.assertNotIn('"private"', json.dumps(evidence))

    def test_pagination_failure_is_not_silently_truncated(self):
        reader = self.reader()
        def broken(path):
            value = copy.deepcopy(reader(path))
            if path.startswith("/api/valuation/assets?"):
                value["assets"] = []
            return value
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "Incomplete restart pagination"):
                capture(broken, Path(folder) / "before.json")

    def test_unpublished_provider_inputs_cannot_be_a_stable_boundary(self):
        reader = self.reader()
        def changed(path):
            value = reader(path)
            if path.startswith("/api/valuation/assets?"):
                value["assets"][0]["providers"] = [{"confidence": 69}]
            return value
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "before.json"
            with self.assertRaisesRegex(ValueError, "differ from published"):
                capture(changed, path)
            evidence = json.loads(path.read_text())
            self.assertFalse(evidence["capture"]["provider_inputs_match_publication"])
            self.assertFalse(evidence["capture"]["complete"])

    def test_missing_semantic_identity_cannot_qualify_as_complete(self):
        reader = self.reader()
        def missing(path):
            result = reader(path)
            if path == "/api/market/health":
                result["semantic_identity"].pop("ownership_dependency_digest")
            return result
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "capture.json"
            with self.assertRaisesRegex(ValueError, "canonical semantic identities"):
                capture(missing, output)
            self.assertFalse(output.exists())
            self.assertTrue(output.with_suffix(".failure.json").exists())
