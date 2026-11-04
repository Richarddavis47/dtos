"""Metadata-only restoration observations; no private cache decoding or work."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from src.platform import restoration_preflight as probe

MIB = 1024**2
SAFE_HANDLES = probe._supports_pinning()


class PreflightMetadataTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.path = self.root / "cache.json"
        self.path.write_bytes(b"PRIVATE_ROSTER_CONTENT_NOT_DECODED")
        self.snapshot = {
            "available": True, "phase": "idle", "cache_lease_conflict": False,
            "heavy_work": dict(fois_generation=False, trade_search=False,
                               historical_response=False, market_critical=False,
                               market_build_active=False),
            "memory": {"cgroup_current_bytes": 512*MIB, "cgroup_limit_bytes": 2*1024**3,
                       "cgroup_inactive_file_bytes": 64*MIB, "cgroup_anonymous_bytes": 400*MIB,
                       "rss_bytes": 450*MIB, "vms_bytes": 900*MIB,
                       "memory_accounting_scope": "cgroup", "system_available_bytes": 999999,
                       "cgroup_memory_events": {"oom": 0, "oom_kill": 0}},
        }
        self.runtime = dict(resident=False, status="cold", cooldown_remaining_seconds=0,
                            cooldown_valid=True)
        self.identity = dict(application="DTOS", version="1.22.11", build=2226,
                             commit="a"*40, ready=True, token="PRIVATE_TOKEN")

    def run_probe(self, *, snapshot=None, path=None, runtime=None, check=None):
        return probe.restoration_preflight(
            "200", cache_path=lambda _league: path or self.path,
            lifecycle_snapshot=snapshot or (lambda: deepcopy(self.snapshot)),
            resident_metadata=lambda _league: deepcopy(self.runtime if runtime is None else runtime),
            deployment_identity=lambda: deepcopy(self.identity),
            fois_working_bytes=512*MIB, fois_safety_bytes=256*MIB,
            check_budget=check or (lambda: None),
        )

    def test_unsupported_platform_is_unknown_without_any_open(self):
        with patch.object(probe, "_supports_pinning", return_value=False), patch.object(probe.os, "open") as opened:
            result = self.run_probe()
        self.assertEqual((result["verdict"], result["reason"]),
                         ("unknown", "safe_metadata_handle_unsupported"))
        self.assertFalse(result["cache"]["generation_pinned"])
        opened.assert_not_called()

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_regular_cache_advisory_scopes_and_no_private_output(self):
        before = self.path.stat()
        with patch("builtins.open", side_effect=AssertionError("Payload open")), patch.object(probe.os, "read", side_effect=AssertionError("Payload read")):
            result = self.run_probe()
        after = self.path.stat()
        self.assertEqual(result["verdict"], "would_admit")
        self.assertTrue(result["advisory_only"])
        self.assertTrue(result["non_atomic"])
        self.assertTrue(result["recheck_required"])
        self.assertEqual(result["process"]["pid"], os.getpid())
        self.assertEqual(result["process"]["lifecycle_scope"], "serving_process_only")
        self.assertEqual(result["process"]["other_worker_idleness"], "not_established")
        self.assertEqual(result["memory"]["scope"], "shared_container")
        self.assertEqual(result["cache"]["size_bytes"], before.st_size)
        self.assertTrue(result["cache"]["path_matches_pinned_generation_at_end"])
        self.assertEqual(result["cache"]["payload_readability"], "not_checked")
        self.assertEqual(result["cache"]["content_compatibility"], "not_evaluated")
        self.assertEqual((before.st_size, before.st_mtime_ns, before.st_atime_ns),
                         (after.st_size, after.st_mtime_ns, after.st_atime_ns))
        text = json.dumps(result)
        for private in (str(self.root), self.path.name, "PRIVATE_ROSTER_CONTENT", "PRIVATE_TOKEN", "system_available_bytes"):
            self.assertNotIn(private, text)

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_every_open_is_metadata_only_and_descriptors_close(self):
        opened = []
        real_open = os.open
        def observed(*args, **kwargs):
            self.assertTrue(args[1] & os.O_PATH)
            self.assertTrue(args[1] & os.O_NOFOLLOW)
            descriptor = real_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor
        with patch.object(probe, "_supports_pinning", return_value=True), patch.object(probe.os, "open", side_effect=observed):
            self.assertEqual(self.run_probe()["verdict"], "would_admit")
        self.assertGreater(len(opened), 1)
        for descriptor in opened:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_missing_and_nonregular_files_are_not_applicable(self):
        missing = self.root / "missing.json"
        result = self.run_probe(path=missing)
        self.assertEqual((result["verdict"], result["reason"]), ("restoration_not_applicable", "cache_missing"))
        self.assertFalse(result["cache"]["exists"])
        paths = [self.root]
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        paths.append(fifo)
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(connection.close)
        endpoint = self.root / "socket"
        connection.bind(str(endpoint))
        paths.append(endpoint)
        if Path("/dev/null").exists():
            paths.append(Path("/dev/null"))
        for path in paths:
            with self.subTest(kind=path.name):
                result = self.run_probe(path=path)
                self.assertEqual((result["verdict"], result["reason"]),
                                 ("restoration_not_applicable", "cache_not_regular"))

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_leaf_and_parent_symlinks_never_follow(self):
        leaf = self.root / "link"
        leaf.symlink_to(self.path)
        result = self.run_probe(path=leaf)
        self.assertEqual(result["reason"], "cache_symlink")
        leaf.unlink()
        leaf.symlink_to(self.root / "absent")
        self.assertEqual(self.run_probe(path=leaf)["reason"], "cache_symlink")
        parent = self.root / "parent-link"
        parent.symlink_to(self.root, target_is_directory=True)
        result = self.run_probe(path=parent/self.path.name)
        self.assertEqual(result["verdict"], "unknown")
        self.assertEqual(result["reason"], "cache_metadata_unavailable")

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_permission_failure_is_unknown_not_absent_and_no_retry(self):
        original = probe.os.open
        calls = 0
        def deny_leaf(path, *args, **kwargs):
            nonlocal calls
            if path == self.path.name:
                calls += 1
                raise PermissionError("PRIVATE_PATH_ERROR")
            return original(path, *args, **kwargs)
        with patch.object(probe, "_supports_pinning", return_value=True), patch.object(probe.os, "open", side_effect=deny_leaf):
            result = self.run_probe()
        self.assertEqual((result["verdict"], result["reason"]), ("unknown", "cache_metadata_unavailable"))
        self.assertIsNone(result["cache"]["exists"])
        self.assertEqual(calls, 1)
        self.assertNotIn("PRIVATE_PATH_ERROR", json.dumps(result))

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_stale_future_and_oversize_are_retention_not_source_claims(self):
        for stamp in (time.time()-31*86400, time.time()+3600):
            with self.subTest(stamp=stamp):
                os.utime(self.path, (stamp, stamp))
                result = self.run_probe()
                self.assertEqual(result["reason"], "cache_retention_ineligible")
                self.assertEqual(result["cache"]["content_compatibility"], "not_evaluated")
        self.path.write_bytes(b"")
        with self.path.open("wb") as handle:
            handle.truncate(65*MIB)
        self.assertEqual(self.run_probe()["reason"], "cache_retention_ineligible")

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_empty_file_and_zero_usage_are_not_missing_values(self):
        self.path.write_bytes(b"")
        self.snapshot["memory"]["cgroup_current_bytes"] = 0
        result = self.run_probe()
        self.assertEqual(result["cache"]["size_bytes"], 0)
        self.assertEqual(result["memory"]["cgroup_current_bytes"], 0)
        self.assertEqual(result["capacity"]["required_bytes"], 256*MIB)
        self.assertEqual(result["verdict"], "would_admit")
        self.assertEqual(result["cache"]["content_compatibility"], "not_evaluated")

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_detected_replacement_and_in_place_mutation_are_unknown(self):
        def replace():
            alternate = self.root / "new"
            alternate.write_bytes(b"different")
            os.replace(alternate, self.path)
        def symlink():
            self.path.unlink()
            self.path.symlink_to(self.root / "absent")
        def fifo():
            self.path.unlink()
            os.mkfifo(self.path)
        def grow():
            self.path.write_bytes(b"growing-private-payload")
        for change in (replace, symlink, fifo, grow, self.path.unlink):
            with self.subTest(change=change.__name__):
                if self.path.exists() or self.path.is_symlink():
                    self.path.unlink()
                self.path.write_bytes(b"original")
                callback = Mock(side_effect=lambda: (change(), deepcopy(self.snapshot))[1])
                result = self.run_probe(snapshot=callback)
                self.assertEqual((result["verdict"], result["reason"]),
                                 ("unknown", "cache_changed_during_observation"))
                self.assertFalse(result["cache"]["path_matches_pinned_generation_at_end"])
                callback.assert_called_once_with()

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_replaced_parent_directory_is_not_claimed_as_matching_path(self):
        parent = self.root / "source"
        parent.mkdir()
        path = parent / "cache.json"
        path.write_bytes(b"pinned")
        def replace_parent():
            parent.rename(self.root / "previous-source")
            parent.mkdir()
            (parent / path.name).write_bytes(b"different-generation")
            return deepcopy(self.snapshot)
        result = self.run_probe(path=path, snapshot=replace_parent)
        self.assertEqual((result["verdict"], result["reason"]),
                         ("unknown", "cache_changed_during_observation"))
        self.assertFalse(result["cache"]["path_matches_pinned_generation_at_end"])

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_fo_is_reservation_not_an_automatic_lease_conflict(self):
        self.snapshot["heavy_work"]["fois_generation"] = True
        self.snapshot["memory"]["cgroup_current_bytes"] = 1024*MIB
        result = self.run_probe()
        self.assertEqual(result["capacity"]["required_bytes"], 896*MIB)
        self.assertEqual(result["verdict"], "would_admit")
        self.snapshot["memory"]["cgroup_current_bytes"] = 1500*MIB
        result = self.run_probe()
        self.assertEqual((result["verdict"], result["reason"]), ("would_defer", "insufficient_headroom"))

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_known_lease_conflict_and_cooldown_are_specific(self):
        self.snapshot["cache_lease_conflict"] = True
        result = self.run_probe()
        self.assertEqual(result["reason"], "heavyweight_lease_conflict")
        self.snapshot["cache_lease_conflict"] = False
        runtime = self.runtime | {"cooldown_remaining_seconds": 12.5}
        result = self.run_probe(runtime=runtime)
        self.assertEqual((result["verdict"], result["reason"]), ("would_defer", "retry_cooldown_active"))

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_market_flags_do_not_replace_the_cache_lease_predicate(self):
        self.snapshot["heavy_work"].update(market_critical=True, market_build_active=True)
        self.assertEqual(self.run_probe()["verdict"], "would_admit")

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_unavailable_required_inputs_are_unknown_not_negative_capacity(self):
        for value in (None, True, -1, "100"):
            with self.subTest(memory=value):
                self.snapshot["memory"]["cgroup_current_bytes"] = value
                result = self.run_probe()
                self.assertEqual((result["verdict"], result["reason"]), ("unknown", "unknown_memory"))
                self.assertIsNone(result["capacity"]["would_admit"])
        self.snapshot["memory"]["cgroup_current_bytes"] = 512*MIB
        self.snapshot["available"] = False
        self.assertEqual(self.run_probe()["reason"], "lifecycle_unavailable")
        self.snapshot["available"] = True
        self.snapshot["heavy_work"]["fois_generation"] = None
        result = self.run_probe()
        self.assertEqual(result["reason"], "unknown_reservation")
        self.assertIn("lifecycle.heavy_work.fois_generation", result["unknown_fields"])
        self.snapshot["heavy_work"]["fois_generation"] = False
        self.assertEqual(self.run_probe(runtime=self.runtime | {"cooldown_valid": False})["reason"], "runtime_metadata_unavailable")

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_missing_optional_accounting_does_not_invent_data_or_block_known_math(self):
        self.snapshot["memory"].pop("cgroup_anonymous_bytes")
        result = self.run_probe()
        self.assertEqual(result["verdict"], "would_admit")
        self.assertIsNone(result["memory"]["cgroup_anonymous_bytes"])
        self.assertIn("memory.cgroup_anonymous_bytes", result["unknown_fields"])

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_changed_conditions_after_positive_snapshot_require_new_admission(self):
        first = self.run_probe()
        self.snapshot["memory"]["cgroup_current_bytes"] = 2*1024**3-1
        second = self.run_probe()
        self.assertEqual(first["verdict"], "would_admit")
        self.assertEqual(second["verdict"], "would_defer")
        self.assertTrue(first["recheck_required"])

    @unittest.skipUnless(SAFE_HANDLES, "Linux metadata-only handles required")
    def test_budget_failure_propagates_and_releases_all_descriptors(self):
        class Expired(RuntimeError):
            pass
        real_open = os.open
        opened = []
        def track(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened.append(fd)
            return fd
        def budget():
            if opened and len(opened) >= len(self.path.parent.parts)+1:
                raise Expired()
        with patch.object(probe, "_supports_pinning", return_value=True), patch.object(probe.os, "open", side_effect=track):
            with self.assertRaises(Expired):
                self.run_probe(check=budget)
        for fd in opened:
            with self.assertRaises(OSError):
                os.fstat(fd)


if __name__ == "__main__":
    unittest.main()
