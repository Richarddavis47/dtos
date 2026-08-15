"""Regression contracts for durable Asset Market restart validation."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from collections import deque
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from tools.validation.generate_sanitized_market_fixture import (
    HISTORICAL_COUNT,
    LEAGUE_ID,
    _canonical_history_fixture,
    _history,
    _record_payload,
    _record_provider,
    fixture_valuation_intelligence,
    material_market_fixture_change,
    publish_fixture_market_revision,
)
from src.core.brain import brain_service
from src.core.historical_memory.store import HistoricalStore
from src.core.history_context.metadata import MinimalMetadataStore
from src.core.history_context.season_cache import SleeperSeasonCache
from tools.validation.linux_market_cgroup_gate import (
    StartupFailure,
    _archive_cache_assessment,
    _archive_cache_retained,
    _archive_material_threshold,
    _artifact_state,
    _application_fixture_contract,
    _configured_fixture_contract,
    _cpu_delta,
    _combined_read_audit,
    _diagnostic_request,
    _effective_memory_margin,
    _historical_leader_performance,
    _identity,
    _material_target_comparison,
    _material_target_search_path,
    _material_first_page_comparison,
    _nonsemantic_payload_comparison,
    _normalized_headers,
    _restart_reuse,
    _record_archive_assessment,
    _pad_to_production_baseline,
    _start_server,
    _startup_memory_within_limit,
    _warm_historical_archive,
)


DETAIL = "Asset Market generation is building safely in the background; retry shortly."


class ArchiveCacheValidationTests(unittest.TestCase):
    def test_cpu_stat_delta_rejects_counter_regression(self) -> None:
        before = {"usage_usec": 10, "nr_throttled": 2}
        self.assertEqual(
            _cpu_delta(before, {"usage_usec": 15, "nr_throttled": 2}),
            {"usage_usec": 5, "nr_throttled": 0},
        )
        with self.assertRaisesRegex(RuntimeError, "backwards"):
            _cpu_delta(before, {"usage_usec": 9, "nr_throttled": 2})

    def test_padding_race_uses_one_memory_read_per_iteration(self) -> None:
        from tools.validation import linux_market_cgroup_gate as gate

        with patch.object(
            gate, "_cgroup", side_effect=[gate.BASELINE - 1, gate.BASELINE + 1],
        ) as observer:
            padding = _pad_to_production_baseline()
        self.assertEqual([len(item) for item in padding], [1])
        self.assertEqual(observer.call_count, 2)

    @staticmethod
    def snapshot(inactive: object, *, size: int = 40 * 1024 * 1024) -> dict:
        return {
            "raw_cgroup_bytes": 900 * 1024 * 1024,
            "inactive_file_bytes": inactive,
            "anonymous_bytes": 400 * 1024 * 1024,
            "effective_working_set_bytes": (
                900 * 1024 * 1024 - inactive
                if isinstance(inactive, int) else None
            ),
            "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
            "archive_size_bytes": size,
            "accounting_mode": (
                "cgroup_working_set" if isinstance(inactive, int)
                else "conservative"
            ),
            "timestamp": 1.0,
            "lifecycle_phase": "fixture",
        }

    @staticmethod
    def coverage(status: str = "completed_with_pending") -> dict:
        return {
            "asset_event_count": 0,
            "counts_by_season": {
                str(season): {"player_week": count}
                for season, count in zip(
                    range(2021, 2026), (6146, 6145, 6145, 6145, 6145), strict=True,
                )
            },
            "canonical_progress": {
                "status": status, "completed_steps": 5, "total_steps": 6,
            },
            "read_model": {"query_count": 3, "rows_read": 30_726},
        }

    def test_archive_contract_counts_records_not_derived_graph_events(self) -> None:
        result = _archive_cache_assessment(
            self.snapshot(3 * 1024 * 1024),
            self.snapshot(3 * 1024 * 1024),
            coverage_status=200, coverage=self.coverage(),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["canonical_historical_record_count"], 30_726)

    def test_compact_fixture_skips_only_full_archive_gate(self) -> None:
        leader_body = json.dumps({"leaders": []})
        with (
            patch.dict(os.environ, {"DTOS_PRODUCTION_SHAPED_FIXTURE": "0"}),
            patch(
                "tools.validation.linux_market_cgroup_gate._request",
                side_effect=[(200, leader_body, 1.0)] * 12,
            ) as request,
        ):
            result = _historical_leader_performance()
        self.assertEqual(request.call_count, 12)
        self.assertEqual(result["full_season_2021"]["status"], "not_applicable")
        self.assertEqual(
            result["full_season_2021"]["reason"], "compact_player_week_fixture",
        )
        self.assertEqual(set(result["seasons"]), {
            "2021", "2022", "2023", "2024", "2025", "2026",
        })

    def test_production_archive_contract_uses_canonical_asset_events(self) -> None:
        coverage = self.coverage()
        coverage["asset_event_count"] = 30_726
        coverage["counts_by_season"] = {"2021": {"player_week": 25_308}}
        result = _archive_cache_assessment(
            self.snapshot(3 * 1024 * 1024),
            self.snapshot(3 * 1024 * 1024),
            coverage_status=200, coverage=coverage,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["verified_evidence_count"], 30_726)

    def test_archive_cache_mode_a_newly_warmed(self) -> None:
        result = _archive_cache_assessment(
            self.snapshot(1 * 1024 * 1024),
            self.snapshot(4 * 1024 * 1024),
            coverage_status=200, coverage=self.coverage(),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["establishment_mode"], "newly_warmed")

    def test_archive_cache_mode_b_already_resident(self) -> None:
        result = _archive_cache_assessment(
            self.snapshot(3 * 1024 * 1024),
            self.snapshot(3 * 1024 * 1024),
            coverage_status=200, coverage=self.coverage(),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["establishment_mode"], "already_resident")

    def test_tiny_unrelated_cache_fails_fixture_threshold(self) -> None:
        threshold = _archive_material_threshold(40 * 1024 * 1024)
        self.assertEqual(threshold, 2 * 1024 * 1024)
        result = _archive_cache_assessment(
            self.snapshot(128 * 1024), self.snapshot(160 * 1024),
            coverage_status=200, coverage=self.coverage(),
        )
        self.assertFalse(result["passed"])

    def test_coverage_failure_cannot_qualify_either_mode(self) -> None:
        result = _archive_cache_assessment(
            self.snapshot(4 * 1024 * 1024),
            self.snapshot(8 * 1024 * 1024),
            coverage_status=503, coverage=self.coverage(),
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["coverage_valid"])

    def test_evidence_is_recorded_before_failed_assertion(self) -> None:
        phases: dict[str, object] = {}
        with self.assertRaises(AssertionError):
            _record_archive_assessment(
                phases, self.snapshot(0), self.snapshot(0),
                coverage_status=200, coverage=self.coverage(), duration_ms=2.0,
                archive_scan={"record_count": 30_726},
            )
        self.assertIn("archive_warming", phases)
        self.assertFalse(phases["archive_warming"]["assessment"]["passed"])
        self.assertEqual(
            phases["archive_warming"]["archive_scan"]["record_count"], 30_726,
        )

    def test_malformed_metrics_fail_closed(self) -> None:
        result = _archive_cache_assessment(
            self.snapshot(None), self.snapshot(None),
            coverage_status=200, coverage=self.coverage(),
        )
        self.assertFalse(result["passed"])
        self.assertIn("metrics", result["reason"])

    def test_archive_cache_must_remain_before_replacement(self) -> None:
        threshold = _archive_material_threshold(40 * 1024 * 1024)
        self.assertTrue(_archive_cache_retained(
            self.snapshot(threshold), threshold,
        ))
        self.assertFalse(_archive_cache_retained(
            self.snapshot(threshold - 1), threshold,
        ))

    def test_startup_gate_uses_verified_effective_working_set(self) -> None:
        snapshot = self.snapshot(800 * 1024 * 1024)
        snapshot["raw_cgroup_bytes"] = 1_300 * 1024 * 1024
        snapshot["effective_working_set_bytes"] = 500 * 1024 * 1024
        self.assertTrue(_startup_memory_within_limit(snapshot))
        snapshot["effective_working_set_bytes"] = 1_300 * 1024 * 1024
        self.assertFalse(_startup_memory_within_limit(snapshot))

    def test_memory_reserve_uses_verified_effective_peak(self) -> None:
        limit = 2 * 1024**3
        self.assertEqual(
            _effective_memory_margin(limit, 1_300 * 1024**2),
            748 * 1024**2,
        )

    def test_generated_history_matches_application_league_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            _history(path)
            store = HistoricalStore(path)
            progress = store.canonical_enrichment_progress(
                LEAGUE_ID, tuple(range(2021, 2027)),
                provider="nflverse", importer_version="1.2",
            )
            with store.connection() as connection:
                count = int(connection.execute(
                    "SELECT count(*) FROM historical_records WHERE league_id=?",
                    (LEAGUE_ID,),
                ).fetchone()[0])
        self.assertEqual(count, HISTORICAL_COUNT)
        self.assertEqual(progress["completed_seasons"], list(range(2021, 2026)))
        self.assertEqual(progress["pending_seasons"], [2026])

    def test_production_fixture_player_week_evidence_matches_checkpoints(self) -> None:
        self.assertEqual(_record_provider("player_week"), "nflverse")
        self.assertEqual(_record_provider("valuation_snapshot"), "sanitized")
        player_id, _payload = _record_payload("player_week", 12_321)
        self.assertEqual(player_id, "v00104")

    def test_archive_warm_scans_real_history_without_decoding_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "CREATE TABLE historical_records (payload TEXT NOT NULL)"
                )
                connection.executemany(
                    "INSERT INTO historical_records VALUES (?)",
                    [("payload",), ("evidence",)],
                )
                connection.commit()
            with patch.dict(os.environ, {"DTOS_HISTORY_DB_FILE": str(path)}):
                result = _warm_historical_archive()
        self.assertEqual(result["record_count"], 2)
        self.assertGreater(result["payload_bytes_scanned"], 0)
        self.assertEqual(result["hotset_records"], 2)
        self.assertGreater(result["hotset_payload_bytes"], 0)
        self.assertGreater(result["database_pages"], 0)

    @patch("tools.validation.linux_market_cgroup_gate._cgroup_values")
    @patch("tools.validation.linux_market_cgroup_gate._memory_evidence")
    @patch("tools.validation.linux_market_cgroup_gate._request")
    def test_combined_read_audit_runs_complete_and_overlapping_cycles(
        self, request, memory_evidence, cgroup_values,
    ) -> None:
        request.return_value = (200, '{"status":"ok"}', 2.0)
        memory_evidence.side_effect = lambda phase: {
            "lifecycle_phase": phase, "raw_cgroup_bytes": 1_000,
        }
        cgroup_values.return_value = {
            "oom": 0, "oom_kill": 0, "oom_group_kill": 0,
        }
        result = _combined_read_audit()
        self.assertEqual(len(result["cycles"]), 2)
        self.assertEqual(request.call_count, 20)
        self.assertEqual(
            {sample["path"] for sample in result["cycles"][0]["overlapping"]},
            {
                "/api/history/coverage", "/api/market/health",
                "/api/market/assets?limit=50",
                "/api/market/assets/player:10213",
                "/api/market/search?q=QB&limit=50",
            },
        )


def _published(generation: str = "market-2") -> dict[str, object]:
    return {
        "application_version": "1.8.9", "application_build": 1809,
        "market_schema_version": "1.0", "league_id": "league-1",
        "historical_dataset_version": "history-1",
        "market_generation": generation, "brain_generation": "brain-1",
        "valuation_generation": "valuation-1", "assets": [],
    }


def _response(
    status: int, payload: dict[str, object], profile: dict[str, object],
    *, client_ms: float = 2.0, server_ms: float = 1.0,
):
    headers = {"retry-after": "5"} if status == 503 else {}
    return status, json.dumps(payload, separators=(",", ":")).encode(), headers, client_ms, server_ms, profile


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class _ReadyResponse:
    status = 503
    headers = {
        "Content-Type": "application/json",
        "X-DTOS-Request-Duration": "2.5",
    }

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    @staticmethod
    def read() -> bytes:
        return b'{"detail":"Waiting for the initial Sleeper dataset."}'


class _FakeProcess:
    def __init__(self, returncodes) -> None:
        self.returncodes = deque(returncodes)
        self.returncode = None
        self.pid = 1234

    def poll(self):
        if self.returncodes:
            self.returncode = self.returncodes.popleft()
        return self.returncode


class RestartReuseValidationTests(unittest.TestCase):
    def test_canonical_fixture_contains_five_seasons_and_all_asset_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"DTOS_METADATA_DB_FILE": str(Path(directory) / "dtos_metadata.sqlite3")},
        ):
            root = Path(directory)
            _canonical_history_fixture(root)
            cache = SleeperSeasonCache(root / "sleeper-season-cache")
            self.assertEqual(cache.available_seasons(LEAGUE_ID), tuple(range(2021, 2026)))
            events = sum(
                len(row.get("players_points") or {})
                for season in range(2021, 2026)
                for rows in (cache.read(LEAGUE_ID, season).facts.get("matchups") or {}).values()
                for row in rows
            )
            self.assertEqual(events, HISTORICAL_COUNT)

    def setUp(self) -> None:
        self.payload = _published()
        self.body = json.dumps(self.payload, separators=(",", ":")).encode()
        self.identity = _identity(self.payload)
        self.warming_profile = {
            "market_construction_total": 0, "market_object_build_total": 0,
            "artifact_load_total": 0, "market_build_phase": "loading_artifact",
            "market_last_error": None,
        }
        self.ready_profile = {
            **self.warming_profile, "artifact_load_total": 1,
            "market_build_phase": "ready",
        }

    @staticmethod
    def _request(responses):
        queue = deque(responses)
        return lambda _path: queue.popleft()

    @staticmethod
    def _probe():
        return 200, b"{}", 1.0, 0.5

    @staticmethod
    def _load():
        return 0.25, 0.5, 0.75

    @staticmethod
    def _memory():
        return 1_073_741_824

    def test_successful_artifact_loading(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        result = _restart_reuse(
            self.identity, self.body, request=request, sleeper=lambda _seconds: None,
            event_probe=self._probe, load_observer=self._load,
            memory_observer=self._memory,
        )
        self.assertEqual(result["warming_attempts"], 1)
        self.assertEqual(result["artifact_loads"], 1)
        self.assertEqual(result["market_constructions"], 0)

    def test_immediate_compatible_artifact_restore_needs_no_warming(self) -> None:
        result = _restart_reuse(
            self.identity, self.body,
            request=lambda _path: (
                200, self.body, {}, 3.0, 2.0, self.ready_profile,
            ),
            event_probe=self._probe, load_observer=self._load,
            memory_observer=self._memory,
        )
        self.assertEqual(result["restore_mode"], "immediate_compatible_artifact")
        self.assertEqual(result["warming_attempts"], 0)
        self.assertEqual(result["artifact_loads"], 1)
        self.assertEqual(result["market_constructions"], 0)

    def test_immediate_ready_without_artifact_load_fails(self) -> None:
        profile = {**self.ready_profile, "artifact_load_total": 0}
        with self.assertRaisesRegex(AssertionError, "exactly one durable artifact"):
            _restart_reuse(
                self.identity, self.body,
                request=lambda _path: (200, self.body, {}, 3.0, 2.0, profile),
                event_probe=self._probe, load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_timeout(self) -> None:
        clock = _Clock()
        response = _response(503, {"detail": DETAIL}, self.warming_profile)
        with self.assertRaisesRegex(AssertionError, "exceeded 60 seconds"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                clock=clock, sleeper=clock.sleep, event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_incompatible_artifact_identity(self) -> None:
        incompatible = _published("other-generation")
        response = _response(200, incompatible, self.ready_profile)
        with self.assertRaisesRegex(AssertionError, "identity mismatch"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_accidental_rebuild(self) -> None:
        profile = {**self.warming_profile, "market_construction_total": 1}
        response = _response(503, {"detail": DETAIL}, profile)
        with self.assertRaisesRegex(AssertionError, "reconstruction"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_load_failure(self) -> None:
        profile = {**self.warming_profile, "market_last_error": "invalid artifact"}
        response = _response(503, {"detail": DETAIL}, profile)
        with self.assertRaisesRegex(AssertionError, "load failed"):
            _restart_reuse(
                self.identity, self.body, request=lambda _path: response,
                event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )

    def test_injected_load_observer_supports_platform_without_getloadavg(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        with patch.object(
            __import__("os"), "getloadavg", side_effect=AssertionError("unavailable"),
            create=True,
        ):
            result = _restart_reuse(
                self.identity, self.body, request=request,
                sleeper=lambda _seconds: None, event_probe=self._probe,
                load_observer=self._load,
                memory_observer=self._memory,
            )
        self.assertEqual(result["warming_samples"][0]["runner_load"], [0.25, 0.5, 0.75])
        self.assertEqual(
            result["warming_samples"][0]["cgroup_memory_current"],
            1_073_741_824,
        )

    def test_injected_memory_observer_avoids_host_cgroup_access(self) -> None:
        request = self._request([
            _response(503, {"detail": DETAIL}, self.warming_profile),
            (200, self.body, {}, 3.0, 2.0, self.ready_profile),
        ])
        with patch(
            "tools.validation.linux_market_cgroup_gate._cgroup",
            side_effect=AssertionError("host cgroup unavailable"),
        ):
            result = _restart_reuse(
                self.identity, self.body, request=request,
                sleeper=lambda _seconds: None, event_probe=self._probe,
                load_observer=self._load, memory_observer=self._memory,
            )
        self.assertEqual(
            result["warming_samples"][0]["cgroup_memory_current"],
            1_073_741_824,
        )

    def test_retry_header_normalization_is_case_insensitive(self) -> None:
        self.assertEqual(
            _normalized_headers([("rEtRy-AfTeR", "5")])["retry-after"], "5",
        )

    def test_duplicate_or_conflicting_retry_headers_fail(self) -> None:
        for values in (("5", "5"), ("5", "10")):
            with self.subTest(values=values):
                with self.assertRaisesRegex(AssertionError, "duplicate"):
                    _normalized_headers([
                        ("Retry-After", values[0]), ("retry-after", values[1]),
                    ])

    def test_readiness_503_does_not_require_market_retry_header(self) -> None:
        with patch(
            "tools.validation.linux_market_cgroup_gate.urlopen",
            return_value=_ReadyResponse(),
        ):
            status, body, _client_ms, server_ms = _diagnostic_request(
                "/health/ready", (200, 503),
            )
        self.assertEqual(status, 503)
        self.assertIn(b"initial Sleeper dataset", body)
        self.assertEqual(server_ms, 2.5)

    def test_artifact_discovery_uses_application_contract(self) -> None:
        payload = {
            "active": True,
            "artifact_name": ".history.asset-market-generation.sqlite3",
            "exists": True,
            "size_bytes": 4096,
            "final_artifacts": 1,
            "temporary_artifacts": 0,
            "complete": True,
            "generation": "generation-1",
        }
        response = (200, json.dumps(payload).encode(), 1.0)
        with patch(
            "tools.validation.linux_market_cgroup_gate._request",
            return_value=response,
        ):
            state = _artifact_state()
        self.assertEqual(state["generation"], "generation-1")
        self.assertNotIn("directory", state)

    def test_artifact_discovery_rejects_partial_or_missing_state(self) -> None:
        invalid = (
            {"active": False, "final_artifacts": 0, "temporary_artifacts": 0},
            {
                "active": True, "exists": True, "size_bytes": 4096,
                "final_artifacts": 1, "temporary_artifacts": 1,
                "complete": True, "generation": "generation-1",
            },
        )
        for payload in invalid:
            with self.subTest(payload=payload), patch(
                "tools.validation.linux_market_cgroup_gate._request",
                return_value=(200, json.dumps(payload).encode(), 1.0),
            ), self.assertRaises(AssertionError):
                _artifact_state()

    def test_explicit_fixture_configuration_is_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "dtos_cache.json"
            history = root / "dtos_history.sqlite3"
            metadata = root / "dtos_metadata.sqlite3"
            cache.write_text("{}", encoding="utf-8")
            HistoricalStore(history)
            MinimalMetadataStore(metadata)
            environment = {
                "DTOS_CACHE_FILE": str(cache),
                "DTOS_HISTORY_DB_FILE": str(history),
                "DTOS_METADATA_DB_FILE": str(metadata),
                "DTOS_HISTORY_STORAGE_ROOT": str(root),
                "SLEEPER_LEAGUE_ID": "1804000000000000000",
            }
            with patch.dict(os.environ, environment, clear=False), patch(
                "tools.validation.linux_market_cgroup_gate.FIXTURE", root,
            ):
                contract = _configured_fixture_contract()
        self.assertEqual(contract["cache_file"], "dtos_cache.json")
        self.assertEqual(contract["legacy_history_database"], "dtos_history.sqlite3")
        self.assertEqual(contract["metadata_database"], "dtos_metadata.sqlite3")
        self.assertTrue(contract["contained"])
        self.assertEqual(contract["league_id"], "1804000000000000000")

    def test_missing_explicit_fixture_setting_cannot_use_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            AssertionError, "required fixture setting is missing",
        ):
            _configured_fixture_contract()

    def test_application_and_validator_fixture_contracts_must_match(self) -> None:
        expected = {
            "storage_root": ".", "cache_file": "dtos_cache.json",
            "legacy_history_database": "dtos_history.sqlite3",
            "metadata_database": "dtos_metadata.sqlite3", "contained": True,
            "league_id": "1804000000000000000",
            "database_identity_digest": "sanitized-digest",
            "file_identity_digest": "sanitized-file-digest",
            "legacy_history_database_size": 1024,
            "metadata_database_size": 20480,
        }
        actual = {
            **expected, "active_store_database": "dtos_metadata.sqlite3",
            "cache_exists": True, "legacy_history_database_exists": True,
            "metadata_database_exists": True,
            "active_store_matches": True,
            "cache_league_id": "1804000000000000000",
        }
        with patch(
            "tools.validation.linux_market_cgroup_gate._request",
            return_value=(200, json.dumps(actual).encode(), 1.0),
        ):
            self.assertEqual(_application_fixture_contract(expected), actual)
        leaked = {**actual, "active_store_database": "default.sqlite3"}
        with patch(
            "tools.validation.linux_market_cgroup_gate._request",
            return_value=(200, json.dumps(leaked).encode(), 1.0),
        ), self.assertRaisesRegex(AssertionError, "canonical store"):
            _application_fixture_contract(expected)

    def test_startup_exit_preserves_sanitized_log_and_exit_code(self) -> None:
        process = _FakeProcess([1])
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as log:
            log.write('Traceback\n  File "/app/private/module.py", line 1\nboom\n')
            log.flush()
            evidence: dict[str, object] = {}
            with self.assertRaises(StartupFailure) as raised:
                _start_server(
                    log, evidence=evidence,
                    popen_factory=lambda *_args, **_kwargs: process,
                    request_observer=lambda _path: (200, b"", 1.0),
                    memory_observer=lambda: 128,
                )
        self.assertEqual(raised.exception.process, process)
        self.assertEqual(evidence["exit_code"], 1)
        self.assertEqual(evidence["termination"], "natural_exit")
        self.assertIn("Traceback", evidence["server_log_tail"])
        self.assertNotIn("/app/private", evidence["server_log_tail"])

    def test_startup_timeout_preserves_process_for_cleanup(self) -> None:
        clock = _Clock()
        process = _FakeProcess([None] * 300)
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as log:
            evidence: dict[str, object] = {}
            with self.assertRaisesRegex(StartupFailure, "60 seconds") as raised:
                _start_server(
                    log, evidence=evidence,
                    popen_factory=lambda *_args, **_kwargs: process,
                    request_observer=lambda _path: (_ for _ in ()).throw(
                        ConnectionRefusedError()
                    ),
                    clock=clock, sleeper=clock.sleep,
                    memory_observer=lambda: 256,
                )
        self.assertEqual(raised.exception.process, process)
        self.assertEqual(evidence["termination"], "startup_timeout")
        self.assertGreater(len(evidence["observations"]), 0)

    def test_missing_executable_is_reported_as_launch_failure(self) -> None:
        def missing(*_args, **_kwargs):
            raise FileNotFoundError("missing executable")

        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as log:
            evidence: dict[str, object] = {}
            with self.assertRaisesRegex(StartupFailure, "could not start"):
                _start_server(
                    log, evidence=evidence, popen_factory=missing,
                    memory_observer=lambda: 64,
                )
        self.assertEqual(evidence["termination"], "launch_failure")
        self.assertEqual(evidence["exception_type"], "FileNotFoundError")

    def test_successful_startup_records_bounded_observation(self) -> None:
        process = _FakeProcess([None])
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as log:
            evidence: dict[str, object] = {}
            result = _start_server(
                log, evidence=evidence,
                popen_factory=lambda *_args, **_kwargs: process,
                request_observer=lambda _path: (200, b"{}", 1.25),
                memory_observer=lambda: 512,
            )
        self.assertIs(result, process)
        self.assertEqual(evidence["termination"], "running")
        self.assertEqual(evidence["observations"][0]["status"], 200)
        self.assertNotIn(str(Path(sys.executable).parent), json.dumps(evidence))

    def test_material_fixture_mutation_updates_attached_canonical_input(self) -> None:
        source = {"valuation_intelligence": fixture_valuation_intelligence()}
        target = source["valuation_intelligence"]["assets"]["player:10213"]
        self.assertIs(brain_service(source).asset("player:10213"), target)
        changed, evidence = material_market_fixture_change(source)
        original = source["valuation_intelligence"]["assets"]["player:10213"]
        mutated = changed["valuation_intelligence"]["assets"]["player:10213"]
        self.assertEqual(
            original["valuation_layers"]["contender_value"]["value"], 450,
        )
        self.assertEqual(
            mutated["valuation_layers"]["contender_value"]["value"], 550,
        )
        self.assertTrue(evidence["attached"])
        self.assertEqual(evidence["changed_canonical_fields"], 1)
        self.assertNotEqual(
            evidence["brain_semantic_digest_before"],
            evidence["brain_semantic_digest_after"],
        )
        self.assertNotEqual(
            evidence["asset_market_semantic_revision_before"],
            evidence["asset_market_semantic_revision_after"],
        )
        self.assertEqual(
            changed["asset_market_semantic_revision"],
            evidence["asset_market_semantic_revision_after"],
        )

    def test_fixture_publication_is_stable_for_identical_semantics(self) -> None:
        source = {"valuation_intelligence": fixture_valuation_intelligence()}
        first = publish_fixture_market_revision(source)
        second = publish_fixture_market_revision(source)
        self.assertEqual(second, first)

    def test_material_fixture_mutation_changes_only_expected_market_row(self) -> None:
        source = {
            "normalized_players": {
                "10213": {
                    "name": "Bijan Robinson", "position": "RB", "dtos_value": 91,
                },
                "4046": {
                    "name": "Josh Allen", "position": "QB", "dtos_value": 95,
                },
            },
            "valuation_intelligence": fixture_valuation_intelligence(),
        }
        changed, _evidence = material_market_fixture_change(source)
        before = source["valuation_intelligence"]["assets"]
        after = changed["valuation_intelligence"]["assets"]
        self.assertEqual(set(before), set(after))
        self.assertNotEqual(before["player:10213"], after["player:10213"])

    def test_material_fixture_mutation_rejects_missing_or_detached_target(self) -> None:
        invalid = ({}, {"valuation_intelligence": {"assets": {}}}, {
            "valuation_intelligence": {"assets": {"player:10213": {
                "valuation_layers": {"contender_value": {"value": None}},
            }}},
        })
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(ValueError):
                material_market_fixture_change(source)

    def test_nonsemantic_payload_comparison_allows_only_named_volatile_fields(self) -> None:
        before = _published()
        before.update({
            "valuation_generation": None,
        })
        after = json.loads(json.dumps(before))
        after["valuation_generation"] = "generated-later"
        evidence = _nonsemantic_payload_comparison(
            json.dumps(before).encode(), json.dumps(after).encode(),
        )
        self.assertEqual(evidence["changed_path_count"], 1)
        self.assertEqual(evidence["row_digest_before"], evidence["row_digest_after"])
        self.assertEqual(evidence["stable_digest_before"], evidence["stable_digest_after"])
        self.assertNotEqual(evidence["raw_digest_before"], evidence["raw_digest_after"])

    def test_nonsemantic_payload_comparison_rejects_row_or_stable_changes(self) -> None:
        before = {"assets": [{"asset_id": "player:10213", "value": 90}], "total": 1}
        for after in (
            {"assets": [{"asset_id": "player:10213", "value": 91}], "total": 1},
            {"assets": [{"asset_id": "player:10213", "value": 90}], "total": 2},
            {"assets": [{"asset_id": "player:2", "value": 90}], "total": 1},
        ):
            with self.subTest(after=after), self.assertRaisesRegex(
                AssertionError, "unapproved response paths",
            ):
                _nonsemantic_payload_comparison(
                    json.dumps(before).encode(), json.dumps(after).encode(),
                )

    def test_material_target_comparison_requires_exact_controlled_row_change(self) -> None:
        before = {"results": [{
            "asset_id": "player:10213",
            "contender_value": 20,
            "values": {"contender_value": 20},
            "confidence": 0,
        }]}
        after = json.loads(json.dumps(before))
        after["results"][0]["contender_value"] = 30
        after["results"][0]["values"]["contender_value"] = 30
        differences = _material_target_comparison(
            json.dumps(before).encode(), json.dumps(after).encode(),
        )
        self.assertEqual(len(differences), 2)
        after["results"][0]["confidence"] = 1
        with self.assertRaisesRegex(AssertionError, "unexpected target fields"):
            _material_target_comparison(
                json.dumps(before).encode(), json.dumps(after).encode(),
            )

    def test_material_target_comparison_rejects_missing_target(self) -> None:
        body = json.dumps({"results": []}).encode()
        with self.assertRaisesRegex(AssertionError, "target is unavailable"):
            _material_target_comparison(body, body)

    def test_material_target_search_uses_canonical_public_asset_id(self) -> None:
        self.assertEqual(
            _material_target_search_path(),
            "/api/market/search?q=player%3A10213&limit=50",
        )

    def test_material_target_comparison_rejects_ambiguous_name_results(self) -> None:
        body = json.dumps({
            "results": [
                {"asset_id": "player:10213"},
                {"asset_id": "player:v10213"},
            ],
        }).encode()
        with self.assertRaisesRegex(AssertionError, "unavailable"):
            _material_target_comparison(body, body)

    def test_material_target_search_rejects_noncanonical_target(self) -> None:
        with self.assertRaisesRegex(AssertionError, "canonical player asset ID"):
            _material_target_search_path("Validation Player 10213")

    def test_material_first_page_separates_rows_from_publication_envelope(self) -> None:
        before = {
            "market_generation": "market-old", "generated_at": "market-old",
            "brain_generation": "brain-old", "valuation_generation": None,
            "historical_dataset_version": "history-old",
            "historical_dataset_version_scope": "artifact_build",
            "total": 2, "offset": 0, "limit": 50, "sort": "market",
            "assets": [{"asset_id": "player:1"}, {"asset_id": "player:2"}],
        }
        after = json.loads(json.dumps(before))
        after.update({
            "market_generation": "market-new", "generated_at": "market-new",
            "brain_generation": "brain-new", "valuation_generation": "value-new",
        })
        evidence = _material_first_page_comparison(
            json.dumps(before).encode(), json.dumps(after).encode(),
            old_market_generation="market-old", new_market_generation="market-new",
        )
        self.assertEqual(evidence["asset_digest_before"], evidence["asset_digest_after"])
        self.assertEqual(evidence["asset_order"], ["player:1", "player:2"])

    def test_material_first_page_rejects_row_change_or_reorder(self) -> None:
        before = {
            "market_generation": "old", "generated_at": "old",
            "historical_dataset_version_scope": "artifact_build",
            "assets": [{"asset_id": "player:1", "value": 1}, {"asset_id": "player:2", "value": 2}],
        }
        changed = json.loads(json.dumps(before))
        changed.update({"market_generation": "new", "generated_at": "new"})
        reordered = json.loads(json.dumps(changed))
        reordered["assets"].reverse()
        changed["assets"][0]["value"] = 2
        for after in (changed, reordered):
            with self.subTest(after=after), self.assertRaisesRegex(
                AssertionError, "first-page assets",
            ):
                _material_first_page_comparison(
                    json.dumps(before).encode(), json.dumps(after).encode(),
                    old_market_generation="old", new_market_generation="new",
                )

    def test_material_first_page_rejects_unknown_or_stale_envelope(self) -> None:
        before = {
            "market_generation": "old", "generated_at": "old",
            "historical_dataset_version_scope": "artifact_build", "assets": [],
        }
        unexpected = {
            "market_generation": "new", "generated_at": "new", "total": 2,
            "historical_dataset_version_scope": "artifact_build",
            "assets": [],
        }
        with self.assertRaisesRegex(AssertionError, "unexpected envelope"):
            _material_first_page_comparison(
                json.dumps(before).encode(), json.dumps(unexpected).encode(),
                old_market_generation="old", new_market_generation="new",
            )
        stale = {
            "market_generation": "old", "generated_at": "old",
            "historical_dataset_version_scope": "artifact_build", "assets": [],
        }
        with self.assertRaisesRegex(AssertionError, "stale generation"):
            _material_first_page_comparison(
                json.dumps(before).encode(), json.dumps(stale).encode(),
                old_market_generation="old", new_market_generation="new",
            )


if __name__ == "__main__":
    unittest.main()
