"""Canonical Projection Intelligence v1.10.0 regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.projections import create_projections_router
from src.core.projection_intelligence.scoring import fantasy_points
from src.core.projection_intelligence.service import ProjectionInputError, ProjectionService, provider_registry
from src.core.projection_intelligence.sleeper_provider import (
    SOURCE_CLASSIFICATION, SleeperProjectionSchemaError, freshness_state,
    parse_projection_feed,
)


def fixture() -> dict:
    return {
        "league": {"season": 2026, "scoring_settings": {"pass_yd": .04, "pass_td": 6, "pass_int": -2, "rush_yd": .1, "rush_td": 6, "rec": 1, "rec_yd": .1, "rec_td": 6, "bonus_rec_te": .5}},
        "week": 4,
        "teams": [{"roster_id": 1, "players": [
            {"id": "10", "position": "QB", "season_average": 20, "status": "Active", "roster_slot": "Starter"},
            {"id": "20", "position": "TE", "recent_points": [8, 12, 14], "status": "Questionable", "roster_slot": "Starter"},
            {"id": "30", "position": "WR", "season_average": 15, "bye_week": 4},
        ]}],
    }


class ProjectionIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = ProjectionService(Path(self.temporary.name) / "projections.sqlite3")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_league_scoring_uses_raw_stats_and_te_premium(self) -> None:
        stats = {"rec": 5, "rec_yd": 80, "rec_td": 1}
        self.assertEqual(fantasy_points(stats, {"rec": 1, "rec_yd": .1, "rec_td": 6}, "TE"), 19)
        self.assertEqual(fantasy_points(stats, {"rec": 1, "rec_yd": .1, "rec_td": 6, "bonus_rec_te": .5}, "TE"), 21.5)

    def test_snapshot_is_idempotent_and_immutable(self) -> None:
        first = self.service.generate(fixture(), "league")
        second = self.service.generate(fixture(), "league")
        self.assertEqual(first, second)
        self.assertEqual(first["projection_snapshot_id"], second["projection_snapshot_id"])
        self.assertEqual(first["players"]["10"]["projection_snapshot_id"], first["projection_snapshot_id"])

    def test_production_mapping_and_sequence_normalize_identically(self) -> None:
        sequence = fixture()
        players = [dict(player) for player in sequence["teams"][0]["players"]]
        sequence["players"] = players
        mapping = fixture()
        mapping["players"] = {player["id"]: dict(player) for player in players}
        first = self.service.generate(sequence, "league")
        other = ProjectionService(Path(self.temporary.name) / "mapping.sqlite3")
        second = other.generate(mapping, "league")
        self.assertEqual(set(first["players"]), set(second["players"]))
        self.assertEqual(other.health()["normalization"]["container_type"], "mapping")

    def test_mapping_key_supplies_id_and_payload_id_may_stand_alone(self) -> None:
        data = fixture()
        data["teams"] = []
        data["players"] = {"10": {"position": "QB"}, "20": {"id": "20", "position": "TE"}}
        snapshot = self.service.generate(data, "league")
        self.assertEqual(set(snapshot["players"]), {"10", "20"})

    def test_conflicting_mapping_identity_fails_closed_and_is_sanitized(self) -> None:
        data = fixture()
        data["teams"] = []
        data["players"] = {"10": {"id": "other", "position": "QB"}}
        with self.assertRaises(ProjectionInputError):
            self.service.generate(data, "league")
        health = self.service.health()
        self.assertEqual(health["status"], "failed")
        self.assertEqual(health["last_error_type"], "ProjectionInputError")
        self.assertNotIn(str(self.service._database_file), health["last_error_message"])

    def test_malformed_values_are_skipped_without_duplicate_roster_projection(self) -> None:
        data = fixture()
        data["players"] = {"10": dict(data["teams"][0]["players"][0]), "bad": "not-a-player"}
        snapshot = self.service.generate(data, "league")
        self.assertEqual(len(snapshot["players"]), 3)
        health = self.service.health()
        self.assertEqual(health["normalization"]["malformed_records"], 1)
        self.assertGreaterEqual(health["normalization"]["duplicate_references"], 1)

    def test_empty_mapping_is_valid_but_nonempty_all_malformed_is_not(self) -> None:
        data = fixture()
        data["teams"] = []
        data["players"] = {}
        self.assertEqual(self.service.generate(data, "league")["players"], {})
        data["players"] = {"bad": "value"}
        with self.assertRaises(ProjectionInputError):
            self.service.generate(data, "league")

    def test_relevant_universe_filters_retired_or_irrelevant_players(self) -> None:
        data = fixture()
        data["teams"] = []
        data["players"] = {"10": {"position": "QB"}, "retired": {"position": "WR", "status": "Inactive"}}
        data["relevant_player_universe"] = {"member_ids": ["10"]}
        snapshot = self.service.generate(data, "league")
        self.assertEqual(set(snapshot["players"]), {"10"})

    def test_bye_is_not_zero_and_injury_lowers_confidence(self) -> None:
        snapshot = self.service.generate(fixture(), "league")
        self.assertIsNone(snapshot["players"]["30"]["weekly_projected_points"])
        self.assertEqual(snapshot["players"]["30"]["status"], "bye")
        healthy = fixture()
        healthy["teams"][0]["players"][1]["status"] = "Active"
        healthy_snapshot = ProjectionService(Path(self.temporary.name) / "healthy.sqlite3").generate(healthy, "league")
        self.assertLess(snapshot["players"]["20"]["projection_confidence"], healthy_snapshot["players"]["20"]["projection_confidence"])

    def test_provider_provenance_never_misattributes_sleeper(self) -> None:
        registry = {item["provider_id"]: item for item in provider_registry()}
        self.assertEqual(registry["sleeper_projections"]["availability_state"], "optional")
        self.assertEqual(registry["sleeper_projections"]["source_classification"], SOURCE_CLASSIFICATION)
        self.assertEqual(registry["dtos_forward_production"]["provider_name"], "DTOS Forward Production Model")

    def test_sleeper_bulk_feed_parses_and_scores_actual_league_rules(self) -> None:
        payload = [{
            "player_id": "10", "season": "2026", "week": 4, "team": "WAS",
            "player": {"position": "QB"},
            "stats": {"pass_yd": 250, "pass_td": 2, "pass_int": 1, "rush_yd": 40, "pts_ppr": 19.5},
            "company": "fixture",
        }]
        rows, fingerprint, report = parse_projection_feed(
            payload, season=2026, week=4,
            scoring={"pass_yd": .04, "pass_td": 6, "pass_int": -2, "rush_yd": .1},
        )
        self.assertEqual(rows["10"]["league_projection"], 24)
        self.assertEqual(rows["10"]["displayed_projection"], 19.5)
        self.assertEqual(report, {"received": 1, "accepted": 1, "malformed": 0, "duplicates": 0})
        self.assertEqual(len(fingerprint), 64)

    def test_sleeper_parser_fails_closed_on_schema_change(self) -> None:
        with self.assertRaises(SleeperProjectionSchemaError):
            parse_projection_feed({"players": []}, season=2026, week=4, scoring={})
        with self.assertRaises(SleeperProjectionSchemaError):
            parse_projection_feed([{"unexpected": True}], season=2026, week=4, scoring={})

    def test_external_snapshot_is_durable_idempotent_and_consensus_is_attributed(self) -> None:
        data = fixture()
        payload = [{
            "player_id": "10", "season": "2026", "week": 4,
            "player": {"position": "QB"}, "stats": {"pass_yd": 250, "pass_td": 2, "pts_ppr": 18},
        }]
        self.assertTrue(self.service.ingest_sleeper(payload, data=data, league_id="league", season=2026, week=4, response_bytes=100))
        first = self.service.snapshot()
        self.assertFalse(self.service.ingest_sleeper(payload, data=data, league_id="league", season=2026, week=4, response_bytes=100))
        self.assertEqual(self.service.snapshot(), first)
        health = self.service.health()
        self.assertEqual(health["projection_refreshes"], 2)
        self.assertEqual(health["projection_semantic_changes"], 1)
        self.assertEqual(health["projection_no_change_refreshes"], 1)
        self.assertEqual(
            health["projection_semantic_digest"], first["projection_snapshot_id"],
        )
        row = first["players"]["10"]
        self.assertEqual(row["sources"], ["dtos_forward_production", "sleeper_projections"])
        self.assertIsNotNone(row["sleeper_projection"])
        restored = ProjectionService(Path(self.temporary.name) / "projections.sqlite3")
        self.assertEqual(restored.health()["external_provider"]["semantic_fingerprint"], first["sleeper_evidence_snapshot_id"])

    def test_no_change_refresh_republishes_snapshot_into_replaced_state(self) -> None:
        original = fixture()
        payload = [{
            "player_id": "10", "season": 2026, "week": 4,
            "player": {"position": "QB"}, "stats": {"pts_ppr": 18},
        }]
        self.assertTrue(self.service.ingest_sleeper(
            payload, data=original, league_id="league", season=2026, week=4,
        ))
        snapshot = self.service.snapshot()
        replacement = fixture()
        self.assertNotIn("projection_intelligence", replacement)
        self.assertFalse(self.service.ingest_sleeper(
            payload, data=replacement, league_id="league", season=2026, week=4,
        ))
        self.assertIs(replacement["projection_intelligence"], snapshot)

    def test_offline_restart_restores_canonical_snapshot_and_original_freshness(self) -> None:
        data = fixture()
        payload = [{
            "player_id": "10", "season": 2026, "week": 4,
            "player": {"position": "QB"}, "stats": {"pts_ppr": 18},
        }]
        self.service.ingest_sleeper(
            payload, data=data, league_id="league", season=2026, week=4,
        )
        before = self.service.snapshot()
        before_updated = self.service.health()["external_provider"]["last_success"]
        restored = ProjectionService(Path(self.temporary.name) / "projections.sqlite3")
        cached_data: dict = {}
        self.assertTrue(restored.restore_into(cached_data))
        self.assertEqual(restored.snapshot(), before)
        self.assertEqual(cached_data["projection_intelligence"], before)
        health = restored.health()
        self.assertEqual(health["snapshot_restores"], 1)
        self.assertEqual(health["restore_failures"], 0)
        self.assertEqual(health["external_requests"], 0)
        self.assertEqual(health["external_provider"]["last_success"], before_updated)

    def test_external_failure_retains_snapshot_and_marks_stale(self) -> None:
        data = fixture()
        payload = [{"player_id": "10", "season": 2026, "week": 4, "player": {"position": "QB"}, "stats": {"pts_ppr": 18}}]
        self.service.ingest_sleeper(payload, data=data, league_id="league", season=2026, week=4)
        retained = self.service.snapshot()
        self.service.fail_external_refresh(RuntimeError("provider unavailable"))
        self.assertEqual(self.service.snapshot(), retained)
        self.assertEqual(self.service.health()["external_provider"]["status"], "Stale")

    def test_single_flight_refresh_and_freshness_states(self) -> None:
        self.assertTrue(self.service.begin_external_refresh())
        self.assertFalse(self.service.begin_external_refresh())
        self.service.fail_external_refresh(RuntimeError("bounded failure"))
        self.assertEqual(freshness_state(None), "Unavailable")

    def test_read_routes_do_not_generate_or_call_external_providers(self) -> None:
        snapshot = self.service.generate(fixture(), "league")
        app = FastAPI()
        app.include_router(create_projections_router(service=self.service))
        client = TestClient(app)
        generations = self.service.health()["generations"]
        self.assertEqual(client.get("/api/projections/health").status_code, 200)
        self.assertEqual(client.get("/api/projections/providers").status_code, 200)
        player = client.get("/api/projections/players/10")
        self.assertEqual(player.status_code, 200)
        self.assertEqual(player.json()["projection"]["projection_snapshot_id"], snapshot["projection_snapshot_id"])
        self.assertEqual(self.service.health()["generations"], generations)
        self.assertEqual(self.service.health()["external_requests"], 0)

    def test_provider_failure_retains_last_valid_snapshot(self) -> None:
        snapshot = self.service.generate(fixture(), "league")
        with self.assertRaises(ValueError):
            self.service.generate({"season": "invalid", "teams": []}, "league")
        self.assertEqual(self.service.snapshot(), snapshot)
        self.assertEqual(self.service.health()["status"], "stale")
        recovered = self.service.generate(fixture(), "league")
        self.assertEqual(recovered, snapshot)
        self.assertEqual(self.service.health()["status"], "ready")
        self.assertIsNone(self.service.health()["last_error_type"])

    def test_accuracy_records_actual_without_rewriting_snapshot(self) -> None:
        snapshot = self.service.generate(fixture(), "league")
        expected = snapshot["players"]["10"]["weekly_projected_points"]
        self.service.record_actual(snapshot["projection_snapshot_id"], "10", expected + 2)
        accuracy = self.service.accuracy()
        self.assertEqual(accuracy["samples"], 1)
        self.assertEqual(accuracy["mae"], 2)
        self.assertEqual(self.service.snapshot(), snapshot)


if __name__ == "__main__":
    unittest.main()
