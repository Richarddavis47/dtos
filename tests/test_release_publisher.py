"""Fail-closed release admission and byte integrity, without remote mutations."""

import copy
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from tools.release import publish as p


class ArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.plan = {
            "candidate": "a" * 40,
            "tree": "b" * 40,
            "canonical_entries": 3,
            "local_canonical_entries": 3,
            "canonical_tests": 2,
            "python_version": "3.14.3",
        }
        result = {
            "head": self.plan["candidate"],
            "tree": self.plan["tree"],
            "passed": True,
            "exit_code": 0,
            "cgroup_limit": 2147483648,
            "cpus": 2,
            "network": "none",
            "python": "3.14.3 (fixture)",
            "final_memory": {"cgroup_memory_events": {"oom_kill": 0}},
        }
        events = [{"event": x} for x in ["start", "stop", "start", "stop"]]
        trace = [
            {"event": "validation_child_completed", "return_code": 0} for _ in range(10)
        ]
        trace.append({"event": "validator_final_summary", "gates": 10})
        self.files = {
            "result.json": json.dumps(result).encode(),
            "tests.jsonl": "\n".join(map(json.dumps, events)).encode(),
            "canonical-trace.jsonl": "\n".join(map(json.dumps, trace)).encode(),
        }

    def archive(self, alter=None):
        files = copy.deepcopy(self.files)
        if alter:
            alter(files)
        manifest = [
            {"name": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
            for n, b in files.items()
        ]
        files["manifest.json"] = json.dumps(manifest).encode()
        files["SHA256SUMS"] = "".join(
            row["sha256"] + "  " + row["name"] + "\n" for row in manifest
        ).encode()
        path = self.root / "evidence.zip"
        p.make_zip(path, files)
        return path

    def local_files(self):
        files = copy.deepcopy(self.files)
        files["manifest.json"] = json.dumps(
            [
                {"name": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                for n, b in files.items()
            ]
        ).encode()
        files["SHA256SUMS"] = "".join(
            row["sha256"] + "  " + row["name"] + "\n"
            for row in json.loads(files["manifest.json"])
        ).encode()
        return {"local-canonical/" + n: b for n, b in files.items()}

    def test_canonical_checksum_sidecar_cannot_disagree_with_manifest(self):
        path = self.archive()
        with zipfile.ZipFile(path) as archive:
            files = {n: archive.read(n) for n in archive.namelist()}
        files["SHA256SUMS"] = b"0" * 64 + b"  tests.jsonl\n"
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            p.verify_canonical(path, self.plan)

    def test_local_checksum_sidecar_is_required(self):
        files = self.local_files()
        del files["local-canonical/SHA256SUMS"]
        path = self.root / "recovery.zip"
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, "checksum list missing"):
            p.verify_local_recovery(path, self.plan)

    def test_complete_source_pinned_evidence(self):
        self.assertTrue(p.verify_canonical(self.archive(), self.plan)["passed"])

    def test_prior_attempts_require_their_own_source_association_and_payload_manifest(
        self,
    ):
        for mutation in ("none", "source", "scope", "payload", "extra", "duplicate"):
            with self.subTest(mutation=mutation):
                payload = b"Original failed attempt, not a passing gate."
                entry = {
                    "name": "prior-local/failed.log",
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                meta = {
                    "candidate": self.plan["candidate"],
                    "tree": self.plan["tree"],
                    "scope": "prior-attempts-only",
                    "files": [entry],
                }
                files = {entry["name"]: payload}
                if mutation == "source":
                    meta["candidate"] = "wrong"
                if mutation == "scope":
                    meta["scope"] = "final-validation"
                if mutation == "payload":
                    files[entry["name"]] += b"changed"
                if mutation == "extra":
                    files["unlisted.log"] = b"unlisted"
                if mutation == "duplicate":
                    meta["files"].append(entry.copy())
                files["prior-manifest.json"] = json.dumps(meta).encode()
                target = self.root / "prior.zip"
                p.make_zip(target, files)
                plan = self.plan | {"prior_evidence_sha256": p.digest(target)}
                if mutation == "none":
                    p.verify_prior_evidence(target, plan)
                else:
                    with self.assertRaises(RuntimeError):
                        p.verify_prior_evidence(target, plan)

    def test_prior_archive_hash_cannot_be_substituted(self):
        target = self.archive()
        with self.assertRaisesRegex(RuntimeError, "archive changed"):
            p.verify_prior_evidence(
                target, self.plan | {"prior_evidence_sha256": "0" * 64}
            )

    def test_wrong_source_and_resource_limit_fail(self):
        for field, value in [
            ("head", "c" * 40),
            ("tree", "d" * 40),
            ("cgroup_limit", 0),
            ("passed", False),
        ]:
            with self.subTest(field=field):

                def alter(files, field=field, value=value):
                    result = json.loads(files["result.json"])
                    result[field] = value
                    files["result.json"] = json.dumps(result).encode()

                with self.assertRaises(RuntimeError):
                    p.verify_canonical(self.archive(alter), self.plan)

    def test_failure_skip_and_incomplete_tests_fail(self):
        for events in [
            [{"event": "start"}],
            [{"event": "failure"}],
            [{"event": "skip"}],
        ]:
            with self.subTest(events=events), self.assertRaises(RuntimeError):
                p.verify_canonical(
                    self.archive(
                        lambda f, events=events: f.update(
                            {"tests.jsonl": "\n".join(map(json.dumps, events)).encode()}
                        )
                    ),
                    self.plan,
                )

    def test_missing_gate_completion_fails(self):
        with self.assertRaisesRegex(RuntimeError, "gate execution"):
            p.verify_canonical(
                self.archive(
                    lambda f: f.update(
                        {
                            "canonical-trace.jsonl": b'{"event":"validator_final_summary","gates":10}'
                        }
                    )
                ),
                self.plan,
            )

    def test_payload_changed_after_manifest_fails(self):
        path = self.archive()
        with zipfile.ZipFile(path) as z:
            files = {n: z.read(n) for n in z.namelist()}
        files["tests.jsonl"] += b"\n"
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            p.verify_canonical(path, self.plan)

    def test_path_escape_and_symlink_fail(self):
        for name in ["../escape", "/absolute", "dir\\escape"]:
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(RuntimeError, "Unsafe"),
            ):
                p.make_zip(self.root / "bad.zip", {name: b"bad"})
        path = self.root / "link.zip"
        with zipfile.ZipFile(path, "w") as z:
            info = zipfile.ZipInfo("link")
            info.external_attr = 0o120777 << 16
            z.writestr(info, "/outside")
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            p.verify_zip(path)

    def test_credential_shaped_payload_holds_publication(self):
        with self.assertRaisesRegex(RuntimeError, "Credential"):
            p.make_zip(self.root / "secret.zip", {"secret.log": b"ghp_" + b"X" * 36})

    def test_complete_local_validation_is_required_in_recovery(self):
        path = self.root / "recovery.zip"
        p.make_zip(path, self.local_files())
        self.assertTrue(p.verify_local_recovery(path, self.plan)["passed"])

    def test_incomplete_local_validation_holds_publication(self):
        path = self.root / "recovery.zip"
        files = self.local_files()
        files["local-canonical/tests.jsonl"] = b'{"event":"start"}'
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, "Local regression incomplete"):
            p.verify_local_recovery(path, self.plan)

    def test_local_manifest_and_every_payload_are_required(self):
        for mutation in ("missing", "population", "payload"):
            files = self.local_files()
            plan = self.plan.copy()
            if mutation == "missing":
                del files["local-canonical/manifest.json"]
            elif mutation == "population":
                plan["local_canonical_entries"] = 99
            else:
                files["local-canonical/tests.jsonl"] += b"\n"
            path = self.root / "recovery.zip"
            p.make_zip(path, files)
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                p.verify_local_recovery(path, plan)

    def test_older_python_cannot_replace_production_canonical(self):
        def alter(files):
            result = json.loads(files["result.json"])
            result["python"] = "3.12.3 (older local runtime)"
            files["result.json"] = json.dumps(result).encode()

        with self.assertRaisesRegex(RuntimeError, "Python runtime mismatch"):
            p.verify_canonical(self.archive(alter), self.plan)

    def test_older_python_cannot_replace_local_canonical(self):
        files = self.local_files()
        result = json.loads(files["local-canonical/result.json"])
        result["python"] = "3.12.3 (older local runtime)"
        files["local-canonical/result.json"] = json.dumps(result).encode()
        path = self.root / "recovery.zip"
        p.make_zip(path, files)
        with self.assertRaisesRegex(RuntimeError, "Python runtime mismatch"):
            p.verify_local_recovery(path, self.plan)


class RemoteAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.expected = {"proof.json": (12, "a" * 64)}
        self.release = {
            "assets": [
                {
                    "name": "proof.json",
                    "state": "uploaded",
                    "size": 12,
                    "digest": "sha256:" + "a" * 64,
                }
            ]
        }

    def test_exact_readback_metadata(self):
        self.assertEqual(
            set(p.verify_remote_assets(self.release, self.expected, True)),
            {"proof.json"},
        )

    def test_missing_partial_unexpected_duplicate_and_corrupt_assets(self):
        p.verify_remote_assets({"assets": []}, self.expected, False)
        for release in [
            {"assets": []},
            {"assets": self.release["assets"] * 2},
            {"assets": [dict(self.release["assets"][0], digest="sha256:" + "b" * 64)]},
            {"assets": [dict(self.release["assets"][0], name="other")]},
            {"assets": [dict(self.release["assets"][0], state="new")]},
        ]:
            with self.subTest(release=release), self.assertRaises(RuntimeError):
                p.verify_remote_assets(release, self.expected, True)

    def test_log_escape_bytes_are_retained_in_file_only(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(p.subprocess, "run") as run,
        ):
            p.download("repos/owner/repo/actions/jobs/1/logs", Path(folder) / "log")
            self.assertIn("--allow-escape-sequences", run.call_args.args[0])
            self.assertIsNotNone(run.call_args.kwargs["stdout"])
            p.download("repos/owner/repo/actions/artifacts/2/zip", Path(folder) / "zip")
            self.assertNotIn("--allow-escape-sequences", run.call_args.args[0])


class ContextAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(Path(".github/release-plans/2251.json").read_text())
        self.publisher = "c" * 40
        self.merge = "d" * 40
        self.env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": self.plan["repository"],
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_ACTOR": self.plan["actor"],
            "GITHUB_REF": self.plan["publisher_ref"],
            "GITHUB_SHA": self.publisher,
            "GITHUB_RUN_ID": "99",
        }
        self.pr = {
            "base": {"ref": "main", "repo": {"full_name": self.plan["repository"]}},
            "head": {
                "repo": {"full_name": self.plan["repository"]},
                "sha": self.plan["candidate"],
                "ref": self.plan["source_branch"],
            },
            "state": "open",
            "merged": False,
            "merged_at": None,
            "merge_commit_sha": None,
        }
        self.current_main = self.plan["baseline"]
        self.tree = self.plan["tree"]
        self.merge_tree = self.plan["tree"]
        self.changes = "tools/release/publish.py"

    def api(self, path):
        if "/git/ref/heads/release/" in path:
            return {"object": {"sha": self.publisher}}
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": self.current_main}}
        if "/actions/runs/" in path:
            return {
                "head_sha": self.publisher,
                "event": "workflow_dispatch",
                "path": ".github/workflows/canonical-release-recovery.yml",
            }
        if "/pulls/" in path:
            return self.pr
        if "/releases/tags/" in path:
            return {"immutable": True, "draft": False}
        self.fail("Unexpected API " + path)

    def command(self, *args):
        if args[1:3] == ("rev-parse", "HEAD"):
            return self.publisher
        if args[1] == "diff":
            return self.changes
        if args[1] == "rev-parse":
            return self.merge_tree if args[2].startswith(self.merge) else self.tree
        if args[1] == "show":
            return f'VERSION = "{self.plan["version"]}"\nBUILD_NUMBER = {self.plan["build"]}\n'
        self.fail("Unexpected command")

    def check(self, operation):
        with (
            patch.dict(os.environ, self.env),
            patch.object(p, "api", side_effect=self.api),
            patch.object(p, "command", side_effect=self.command),
            patch.object(p.subprocess, "run"),
        ):
            return p.verify_context(self.plan, operation)

    def test_prepare_accepts_only_unchanged_open_candidate(self):
        self.check("prepare")

    def test_publish_refuses_unmerged_candidate(self):
        with self.assertRaisesRegex(RuntimeError, "merged at current main"):
            self.check("publish")

    def test_merged_identical_tree_is_required(self):
        self.pr.update(merged=True, merged_at="2026-11-01", merge_commit_sha=self.merge)
        self.current_main = self.merge
        self.check("publish")
        self.merge_tree = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "Merged application differs"):
            self.check("publish")

    def test_advanced_main_does_not_publish_old_merge(self):
        self.pr.update(merged=True, merged_at="2026-11-01", merge_commit_sha=self.merge)
        self.current_main = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "merged at current main"):
            self.check("publish")

    def test_candidate_revision_change_is_rejected(self):
        self.pr["head"]["sha"] = "e" * 40
        with self.assertRaisesRegex(RuntimeError, "Candidate PR changed"):
            self.check("prepare")

    def test_wrong_actor_event_ref_and_repository_fail(self):
        for key in [
            "GITHUB_ACTOR",
            "GITHUB_EVENT_NAME",
            "GITHUB_REF",
            "GITHUB_REPOSITORY",
        ]:
            original = self.env[key]
            self.env[key] = "untrusted"
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.check("prepare")
            self.env[key] = original

    def test_tooling_branch_cannot_smuggle_application_changes(self):
        self.changes = "src/platform/fois_admission.py"
        with self.assertRaisesRegex(RuntimeError, "application changes"):
            self.check("prepare")

    def test_rejected_context_has_no_upload_or_tag_side_effect(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(p, "verify_context", side_effect=RuntimeError("unmerged")),
            patch.object(p, "collect") as collect,
            patch.object(p, "api") as api,
        ):
            with self.assertRaisesRegex(RuntimeError, "unmerged"):
                p.prepare_or_publish(self.plan, Path(folder), "publish")
            collect.assert_not_called()
            api.assert_not_called()


class RunAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(Path(".github/release-plans/2251.json").read_text())
        self.plan["runs"] = [
            run | {"id": 100000 + index * 1000}
            for index, run in enumerate(self.plan["runs"])
        ]
        self.checks = [
            {
                "name": name,
                "head_sha": self.plan["candidate"],
                "status": "completed",
                "conclusion": "success",
                "app": {"slug": "github-actions"},
            }
            for run in self.plan["runs"]
            for name in run["jobs"]
        ]
        self.bad_source = False

    def api(self, path):
        if "/check-runs?" in path:
            return {"check_runs": self.checks}
        run = next(x for x in self.plan["runs"] if str(x["id"]) in path)
        if "/jobs?" in path:
            return {
                "jobs": [
                    {
                        "name": n,
                        "status": "completed",
                        "conclusion": "success",
                        "id": i + run["id"],
                    }
                    for i, n in enumerate(run["jobs"])
                ]
            }
        return {
            "head_sha": "wrong" if self.bad_source else self.plan["candidate"],
            "head_repository": {"full_name": self.plan["repository"]},
            "event": "pull_request",
            "path": run["path"],
            "name": run["name"],
            "status": "completed",
            "conclusion": "success",
        }

    def test_exact_thirteen_jobs_are_required(self):
        with patch.object(p, "api", side_effect=self.api):
            records, product = p.verify_runs(self.plan)
        self.assertEqual(len(records), 13)
        self.assertIsNotNone(product)

    def test_later_failed_missing_and_wrong_source_checks_reject(self):
        for change in ["failed", "missing", "source"]:
            with self.subTest(change=change):
                original = copy.deepcopy(self.checks)
                if change == "failed":
                    self.checks[0]["conclusion"] = "failure"
                elif change == "missing":
                    self.checks.pop()
                else:
                    self.checks[0]["head_sha"] = "wrong"
                with (
                    patch.object(p, "api", side_effect=self.api),
                    self.assertRaisesRegex(RuntimeError, "Latest required check"),
                ):
                    p.verify_runs(self.plan)
                self.checks = original

    def test_successful_run_from_another_commit_is_rejected(self):
        self.bad_source = True
        with (
            patch.object(p, "api", side_effect=self.api),
            self.assertRaisesRegex(RuntimeError, "run source mismatch"),
        ):
            p.verify_runs(self.plan)

    def test_publish_cannot_omit_preparation_certificate(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(p, "api") as api:
            with self.assertRaisesRegex(
                RuntimeError, "explicit successful preparation"
            ):
                p.verify_preparation(self.plan, Path(folder), {}, None)
            api.assert_not_called()


class TradeResourceIntegrityTests(unittest.TestCase):
    def test_exact_source_and_complete_real_work_are_required(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        valid = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "passed": True,
            "complete": True,
            "kernel_peak": 2_000_000_000,
            "working_tree_clean": True,
            "cleanup": {
                "harness_scratch_exists_after": False,
                "trade_lease_available": True,
            },
            "one_qb_http_evaluation": {"passed": True},
            "operations": [{"full_evaluations": 180, "business_digest": "same"}] * 2,
            "actual_cancel": {"evaluations_started": 1},
            "file_cache_recovery": {
                "completed_evaluations": 180,
                "content_still_valid": True,
            },
            "states": [
                {
                    "cgroup_limit_bytes": 2147483648,
                    "cgroup_memory_events": {"oom": 0, "oom_kill": 0},
                }
            ],
            "liveness": [
                {"milliseconds": 20, "server_duration_ms": 20, "client_elapsed_ms": 30}
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trade.zip"
            for update in (
                {},
                {"head": "wrong"},
                {"complete": False},
                {"kernel_peak": 2147483649},
                {"operations": []},
                {"working_tree_clean": False},
                {"cleanup": {}},
                {"liveness": [{"milliseconds": 501}]},
            ):
                files = {
                    "result.json": json.dumps(valid | update).encode(),
                    "raw.log": b"controlled",
                    "preparation.log": b"fixture",
                }
                files["SHA256SUMS"] = "".join(
                    hashlib.sha256(b).hexdigest() + "  " + n + "\n"
                    for n, b in files.items()
                ).encode()
                p.make_zip(path, files)
                if update:
                    with self.assertRaises(RuntimeError):
                        p.verify_trade_resource(path, plan)
                else:
                    self.assertTrue(p.verify_trade_resource(path, plan)["passed"])


class LeagueEntryIntegrityTests(unittest.TestCase):
    def test_handoff_requires_exact_source_and_no_credentials(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        body = (plan["candidate"] + " " + plan["tree"]).encode()
        self.assertEqual(p.verify_handoff(body, plan), body)
        for bad in (b"old source", body + b"ghp_" + b"X" * 40, b"X" * (128 * 1024 + 1)):
            with self.assertRaises(RuntimeError):
                p.verify_handoff(bad, plan)

    def test_real_execution_deferral_recovery_ownership_and_liveness_are_required(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        labels = [
            "active_fois_worker",
            "before_large_restore_with_fois",
            "after_large_restore_with_fois",
            "unsafe_pressure",
            "active_fois_outstanding_reserve",
            "same_pressure_after_fois_release",
            "pressure_relieved",
            "recovered_restore",
            "cleanup",
        ]
        valid = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "passed": True,
            "complete": True,
            "working_tree_clean": True,
            "warm_cold_saved_http": "passed",
            "one_qb_k_def_http_evaluation": "passed",
            "pressure_deferred": True,
            "recovery_completed": True,
            "worker_reaped": True,
            "cgroup_lifetime_peak": 2_000_000_000,
            "active_fois_commitment_deferred": True,
            "after_fois_release_same_pressure_completed": True,
            "samples": [
                {
                    "label": n,
                    "cgroup_limit_bytes": 2147483648,
                    "cgroup_current_bytes": 1_000_000_000,
                    "cgroup_memory_events": {"oom": 0, "oom_kill": 0},
                }
                for n in labels
            ],
            "liveness": [{"server_ms": 20, "client_ms": 30}] * 5,
        }
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "entry.zip"
            for update in (
                {},
                {"head": "wrong"},
                {"complete": False},
                {"working_tree_clean": False},
                {"pressure_deferred": False},
                {"recovery_completed": False},
                {"worker_reaped": False},
                {"active_fois_commitment_deferred": False},
                {"after_fois_release_same_pressure_completed": False},
                {"one_qb_k_def_http_evaluation": "deferred"},
                {"samples": []},
                {"liveness": []},
                {"cgroup_lifetime_peak": 2147483649},
            ):
                files = {
                    "result.json": json.dumps(valid | update).encode(),
                    "raw.log": b"controlled",
                    "preparation.log": b"fixture",
                }
                files["SHA256SUMS"] = "".join(
                    hashlib.sha256(b).hexdigest() + "  " + n + "\n"
                    for n, b in files.items()
                ).encode()
                p.make_zip(target, files)
                if update:
                    with self.assertRaises(RuntimeError):
                        p.verify_league_entry(target, plan)
                else:
                    self.assertTrue(p.verify_league_entry(target, plan)["passed"])


class PreflightIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name) / "preflight.zip"
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40}
        self.result = {
            "head": self.plan["candidate"],
            "tree": self.plan["tree"],
            "passed": True,
            "complete": True,
            "enforced_limit": 2147483648,
            "swap_limit": 0,
            "kernel_peak_bytes": 2000000000,
            "scratch_removed": True,
            "children_after": [],
            "runtime_population_unchanged": True,
            "no_private_payload_decoded": True,
            "guarded_operation_calls": [0] * 5,
            "final_memory": {
                "cgroup_limit_bytes": 2147483648,
                "cgroup_memory_events": {"oom": 0, "oom_kill": 0},
            },
            "cases": [],
            "liveness": [],
        }
        for name, verdict, reserved, raw_mib, padding in (
            ("healthy", "would_admit", False, 900, 0),
            ("capacity_deferred", "would_defer", False, 1800, 1000000000),
            ("pressure_relieved", "would_admit", False, 900, 0),
            ("fois_reserve_protected", "would_defer", True, 1150, 500000000),
            ("fois_released_same_pressure", "would_admit", False, 1150, 500000000),
        ):
            working = 16 * 23048708
            safety, fois = (
                (256 * 1024**2, 512 * 1024**2) if reserved else (128 * 1024**2, 0)
            )
            response = {
                "verdict": verdict,
                "reason": "sufficient_headroom"
                if verdict == "would_admit"
                else "insufficient_headroom",
                "advisory_only": True,
                "non_atomic": True,
                "recheck_required": True,
                "assessment_scope": "saved_cache_resource_and_coordination_admission_only",
                "process": {
                    "pid": 123,
                    "lifecycle_scope": "serving_process_only",
                    "other_worker_idleness": "not_established",
                },
                "cache": {
                    "size_bytes": 23048708,
                    "generation_pinned": True,
                    "path_matches_pinned_generation_at_end": True,
                    "payload_readability": "not_checked",
                    "content_compatibility": "not_evaluated",
                },
                "lifecycle": {
                    "available": True,
                    "cache_lease_conflict": False,
                    "heavy_work": {"fois_generation": reserved},
                },
                "memory": {
                    "scope": "shared_container",
                    "cgroup_limit_bytes": 2147483648,
                    "cgroup_current_bytes": raw_mib * 1024**2,
                    "memory_events": {"oom": 0, "oom_kill": 0},
                },
                "capacity": {
                    "telemetry_valid": True,
                    "working_bytes": working,
                    "safety_bytes": safety,
                    "fois_working_bytes": fois,
                    "required_bytes": working + safety + fois,
                    "effective_limit_bytes": 2147483648,
                    "headroom_bytes": 2147483648 - raw_mib * 1024**2,
                    "would_admit": verdict == "would_admit",
                },
            }
            self.result["cases"].append(
                {"name": name, "response": response, "harness_padding_bytes": padding}
            )
            self.result["liveness"].append(
                {"case": name, "server_ms": 10, "client_ms": 15}
            )

    def write(self, result=None, *, corrupt_checksum=False):
        files = {
            "result.json": json.dumps(result or self.result).encode(),
            "raw.log": b"Fixture-only original observer log.",
        }
        files["SHA256SUMS"] = "".join(
            hashlib.sha256(b).hexdigest() + "  " + n + "\n" for n, b in files.items()
        ).encode()
        if corrupt_checksum:
            files["raw.log"] += b"changed"
        p.make_zip(self.target, files)
        return self.target

    def test_exact_five_case_metadata_acceptance(self):
        self.assertTrue(p.verify_preflight(self.write(), self.plan)["passed"])

    def test_source_resource_cleanup_and_completion_are_required(self):
        for update in (
            {"head": "old"},
            {"tree": "other"},
            {"passed": False},
            {"complete": False},
            {"enforced_limit": 0},
            {"swap_limit": 1},
            {"kernel_peak_bytes": 2147483649},
            {"scratch_removed": False},
            {"children_after": [99]},
            {"runtime_population_unchanged": False},
            {"no_private_payload_decoded": False},
            {"guarded_operation_calls": [0, 0, 1, 0, 0]},
            {
                "final_memory": {
                    "cgroup_limit_bytes": 2147483648,
                    "cgroup_memory_events": {"oom_kill": 1},
                }
            },
            {"cases": []},
            {"liveness": []},
        ):
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(self.result | update), self.plan)

    def test_advisory_scope_compatibility_and_reservations_are_required(self):
        for field, key, value in (
            ("process", "lifecycle_scope", "whole_service"),
            ("process", "other_worker_idleness", "idle"),
            ("cache", "size_bytes", 1),
            ("cache", "generation_pinned", False),
            ("cache", "path_matches_pinned_generation_at_end", False),
            ("cache", "content_compatibility", "verified"),
            ("cache", "payload_readability", "read"),
            ("lifecycle", "cache_lease_conflict", True),
            ("lifecycle", "available", False),
            ("memory", "scope", "process_only"),
            ("capacity", "required_bytes", 1),
            ("capacity", "effective_limit_bytes", 4294967296),
            ("capacity", "working_bytes", 1),
        ):
            data = copy.deepcopy(self.result)
            data["cases"][0]["response"][field][key] = value
            with self.subTest(field=field, key=key), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(data), self.plan)
        for key in ("advisory_only", "non_atomic", "recheck_required"):
            data = copy.deepcopy(self.result)
            data["cases"][0]["response"][key] = False
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(data), self.plan)

    def test_fois_recovery_requires_same_pressure_and_live_reservation(self):
        for change in (
            "pressure",
            "reservation",
            "verdict",
            "duplicate",
            "liveness",
            "oom",
        ):
            data = copy.deepcopy(self.result)
            if change == "pressure":
                data["cases"][4]["harness_padding_bytes"] = 0
            if change == "reservation":
                data["cases"][3]["response"]["lifecycle"]["heavy_work"][
                    "fois_generation"
                ] = False
            if change == "verdict":
                data["cases"][1]["response"]["verdict"] = "would_admit"
            if change == "duplicate":
                data["cases"][4]["name"] = "healthy"
            if change == "liveness":
                data["liveness"][0]["server_ms"] = 500
            if change == "oom":
                data["cases"][0]["response"]["memory"]["memory_events"]["oom"] = 1
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                p.verify_preflight(self.write(data), self.plan)

    def test_changed_original_payload_holds_preflight(self):
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            p.verify_preflight(self.write(corrupt_checksum=True), self.plan)


class CurrentHistoryArtifactTests(unittest.TestCase):
    def test_only_complete_exact_source_browser_evidence_is_accepted(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        rows = [
            {
                "league_control": league,
                "width": w,
                "height": h,
                "retrieved": [1, 2, 3, 5, 6, 7, 8],
                "failed": [4],
                "keyboard": True,
                "touch_emulated": w < 1000,
                "overflow": False,
                "extra_disclosure_requests": 0,
            }
            for league in ("Granite-shaped", "Day-shaped", "Arkham-shaped")
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        ]
        report = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "working_tree_clean": True,
            "records": rows,
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "current-history.zip"
            for change in (
                "control",
                "source",
                "dirty",
                "missing",
                "duplicate",
                "coverage",
                "failure",
                "keyboard",
                "touch",
                "overflow",
                "requests",
                "screenshots",
            ):
                with self.subTest(change=change):
                    data = copy.deepcopy(report)
                    if change == "source":
                        data["tree"] = "c" * 40
                    if change == "dirty":
                        data["working_tree_clean"] = False
                    if change == "missing":
                        data["records"].pop()
                    if change == "duplicate":
                        data["records"][-1] = data["records"][0]
                    for key, field, value in (
                        ("coverage", "retrieved", [1]),
                        ("failure", "failed", []),
                        ("keyboard", "keyboard", False),
                        ("touch", "touch_emulated", False),
                        ("overflow", "overflow", True),
                        ("requests", "extra_disclosure_requests", 1),
                    ):
                        if change == key:
                            data["records"][0][field] = value
                    files = {"browser.json": json.dumps(data).encode()}
                    files.update(
                        {str(i) + ".png": b"\x89PNG\r\n\x1a\n" for i in range(12)}
                    )
                    if change == "screenshots":
                        del files["0.png"]
                    p.make_zip(path, files)
                    if change == "control":
                        self.assertEqual(p.verify_current_history(path, plan), report)
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_current_history(path, plan)


class HistoryFollowThroughArtifactTests(unittest.TestCase):
    def test_exact_source_complete_chain_context_and_cleanup_are_required(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        h = "/history/team/100:franchise:4"
        root = "/trades/history/1234"
        pick = "/picks/PICK-2026-R2-ORIG7?from_trade=1234"
        player = "/players/13346?from_trade=1234"
        later = "/trades/history/5678?from_trade=1234"
        chain = [
            h,
            h + "?events_page=2",
            root,
            pick,
            player,
            later,
            root,
            later,
            player,
            pick,
            root,
            h + "?events_page=2",
            h,
            h + "?events_page=2",
            h + "?events_page=2",
            "/history/team/200:franchise:1",
        ]
        rows = []
        for w, hgt in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            rows.extend(
                [
                    {
                        "control": "Day retained chain plus disposable pagination",
                        "width": w,
                        "height": hgt,
                        "chain": chain,
                        "original": "1234",
                        "pick": "PICK-2026-R2-ORIG7",
                        "later": "5678",
                        "keyboard": True,
                        "touch_emulated": w < 500,
                        "overflow": False,
                        "extra_disclosure_requests": 0,
                        "pagination_return": True,
                        "forward_reload": True,
                    },
                    {
                        "control": "Arkham retained history and scope reset",
                        "width": w,
                        "height": hgt,
                        "overflow": False,
                        "source_qualified": True,
                        "old_league_replay": False,
                    },
                ]
            )
        report = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "working_tree_clean": True,
            "records": rows,
            "errors": [],
            "server_thread_reaped": True,
            "requests": [{"path": "/api/account/navigation-context", "status": 200}],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.zip"
            for change in (
                "control",
                "source",
                "dirty",
                "missing",
                "duplicate",
                "chain",
                "origin",
                "pagination",
                "reload",
                "scope",
                "browser-error",
                "cleanup",
                "heavy-request",
                "context",
                "screenshots",
            ):
                with self.subTest(change=change):
                    data = copy.deepcopy(report)
                    if change == "source":
                        data["tree"] = "c" * 40
                    if change == "dirty":
                        data["working_tree_clean"] = False
                    if change == "missing":
                        data["records"].pop()
                    if change == "duplicate":
                        data["records"][-1] = data["records"][0]
                    if change == "chain":
                        data["records"][0]["chain"][11] = "/league"
                    if change == "origin":
                        data["records"][0]["original"] = "9999"
                    if change == "pagination":
                        data["records"][0]["pagination_return"] = False
                    if change == "reload":
                        data["records"][0]["forward_reload"] = False
                    if change == "scope":
                        data["records"][1]["old_league_replay"] = True
                    if change == "browser-error":
                        data["errors"] = ["failed"]
                    if change == "cleanup":
                        data["server_thread_reaped"] = False
                    if change == "heavy-request":
                        data["requests"].append({"path": "/sync", "status": 200})
                    if change == "context":
                        data["requests"] = []
                    files = {"browser.json": json.dumps(data).encode()}
                    files.update(
                        {str(i) + ".png": b"\x89PNG\r\n\x1a\n" for i in range(8)}
                    )
                    if change == "screenshots":
                        del files["0.png"]
                    p.make_zip(path, files)
                    if change == "control":
                        self.assertEqual(
                            p.verify_history_followthrough(path, plan), report
                        )
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_history_followthrough(path, plan)


class MarketHistoryArtifactTests(unittest.TestCase):
    def test_complete_cache_transition_compatibility_and_cleanup_required(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        memory = {
            "cgroup_limit_bytes": 2147483648,
            "cgroup_memory_events": {"oom": 0, "oom_kill": 0},
        }
        rows = [
            {
                "league": league,
                "viewport": [w, h],
                "before": {"magnitude": 100, "checkpoint_count": 2},
                "updated": {
                    "magnitude": 120,
                    "checkpoint_count": 3,
                    "comparison_start_at": "2026-06-01T12:00:00Z",
                    "comparison_end_at": "2026-08-31T12:00:00+00:00",
                    "comparison_scope": "historical_to_current",
                    "comparison_units": "0-1000",
                    "confidence": "low",
                },
                "boundary": {
                    "magnitude": None,
                    "checkpoint_count": 4,
                    "direction": "not_comparable",
                    "comparison_reasons": ["INCOMPATIBLE_OBSERVATION_BOUNDARY"],
                },
                "price_publication_unchanged": True,
                "overflow": False,
                "keyboard": True,
                "disclosure_extra_requests": 0,
                "source_catalogue_not_participation": True,
            }
            for league in ("1314695233040052224", "1319750579458686976")
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        ]
        report = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "working_tree_clean": True,
            "records": rows,
            "errors": [],
            "browser_closed": True,
            "before_memory": memory,
            "after_memory": memory,
            "requests": [{"path": "/market?selected=player%3A1", "status": 200}],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "market.zip"
            for change in (
                "control",
                "source",
                "dirty",
                "missing",
                "duplicate",
                "before",
                "magnitude",
                "dates",
                "scope",
                "units",
                "confidence",
                "boundary",
                "publication",
                "overflow",
                "keyboard",
                "requests",
                "provider",
                "error",
                "cleanup",
                "memory",
                "oom",
                "heavy",
                "screenshots",
            ):
                with self.subTest(change=change):
                    data = copy.deepcopy(report)
                    row = data["records"][0]
                    if change == "source":
                        data["tree"] = "c" * 40
                    if change == "dirty":
                        data["working_tree_clean"] = False
                    if change == "missing":
                        data["records"].pop()
                    if change == "duplicate":
                        data["records"][-1] = copy.deepcopy(row)
                    if change == "before":
                        row["before"]["magnitude"] = 120
                    for key, field, value in (
                        ("magnitude", "magnitude", 100),
                        ("dates", "comparison_start_at", None),
                        ("scope", "comparison_scope", None),
                        ("units", "comparison_units", None),
                        ("confidence", "confidence", "high"),
                    ):
                        if change == key:
                            row["updated"][field] = value
                    if change == "boundary":
                        row["boundary"]["magnitude"] = 120
                    for key, field, value in (
                        ("publication", "price_publication_unchanged", False),
                        ("overflow", "overflow", True),
                        ("keyboard", "keyboard", False),
                        ("requests", "disclosure_extra_requests", 1),
                        ("provider", "source_catalogue_not_participation", False),
                    ):
                        if change == key:
                            row[field] = value
                    if change == "error":
                        data["errors"] = ["failed"]
                    if change == "cleanup":
                        data["browser_closed"] = False
                    if change == "memory":
                        data["before_memory"]["cgroup_limit_bytes"] = None
                    if change == "oom":
                        data["after_memory"]["cgroup_memory_events"]["oom_kill"] = 1
                    if change == "heavy":
                        data["requests"].append({"path": "/sync", "status": 200})
                    files = {"browser.json": json.dumps(data).encode()}
                    files.update(
                        {str(i) + ".png": b"\x89PNG\r\n\x1a\n" for i in range(24)}
                    )
                    if change == "screenshots":
                        del files["0.png"]
                    p.make_zip(path, files)
                    if change == "control":
                        self.assertEqual(p.verify_market_history(path, plan), report)
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_market_history(path, plan)


class RestorationAdmissionEvidenceTests(unittest.TestCase):
    def test_incomplete_or_weakened_restoration_records_cannot_publish(self):
        result = {
            "head": "a" * 40,
            "tree": "b" * 40,
            "working_tree_clean": True,
            "passed": True,
            "scratch_removed": True,
            "explicit_retry_completed": True,
            "expired_released_active_and_fresh_preserved": True,
            "fois_reserve_preserved": True,
            "before_plan": {"would_admit": False, "required_bytes": 500},
            "recovery": {
                "would_admit": True,
                "required_bytes": 500,
                "expired_entries": 3,
            },
            "raw_bytes_released": 200,
            "unsafe_pressure_deferred": {"would_admit": False},
            "fois_reserved_plan": {"would_admit": False, "required_bytes": 1000},
            "kernel_lifetime_peak_bytes": 1800000000,
            "samples": [
                {
                    "cgroup_limit_bytes": 2147483648,
                    "cgroup_memory_events": {"oom": 0, "oom_kill": 0},
                }
            ],
            "cleanup_processes": [],
            "liveness": [{"server_ms": 2, "client_ms": 3}] * 4,
        }
        mutations = {
            "source": lambda r: r.update(head="wrong"),
            "incomplete": lambda r: r.update(passed=False),
            "dirty": lambda r: r.update(working_tree_clean=False),
            "scratch": lambda r: r.update(scratch_removed=False),
            "retry": lambda r: r.update(explicit_retry_completed=False),
            "active": lambda r: r.update(
                expired_released_active_and_fresh_preserved=False
            ),
            "reserve": lambda r: r["recovery"].update(required_bytes=400),
            "defer": lambda r: r["unsafe_pressure_deferred"].update(would_admit=True),
            "fois": lambda r: r["fois_reserved_plan"].update(required_bytes=500),
            "memory": lambda r: r.update(kernel_lifetime_peak_bytes=2147483649),
            "oom": lambda r: r["samples"][0]["cgroup_memory_events"].update(oom_kill=1),
            "worker": lambda r: r.update(
                cleanup_processes=[{"resource_tracker": False}]
            ),
            "liveness": lambda r: r.update(liveness=[]),
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "control.zip"
            for name, change in mutations.items():
                with self.subTest(name=name):
                    row = copy.deepcopy(result)
                    change(row)
                    p.make_zip(path, {"evidence/result.json": json.dumps(row).encode()})
                    with self.assertRaises(RuntimeError):
                        p.verify_restoration_unused(
                            path, {"candidate": "a" * 40, "tree": "b" * 40}
                        )


class NativeRestorationAdmissionTests(unittest.TestCase):
    def test_completed_generic_recovery_does_not_replace_native_actuals_parity(self):
        good = {
            "passed": True,
            "method": "sleeper-matchup-actuals-v1",
            "source_generation": "native",
            "admitted_generation": "native",
            "expected_first_scores": [0, -2.125],
            "admitted_first_scores": [0, -2.125],
            "league_id": "fixture",
            "season": "2026",
            "scoring_fingerprint": "scoring",
            "observations": 2,
        }
        with patch.object(
            p, "verify_restoration_unused", return_value={"native_actuals": good}
        ):
            self.assertEqual(
                p.verify_actuals_restoration(None, None)["native_actuals"], good
            )
        for key, value in [
            ("passed", False),
            ("method", "nflverse"),
            ("source_generation", None),
            ("admitted_generation", "other"),
            ("admitted_first_scores", [0, 0]),
            ("observations", 0),
            ("league_id", None),
        ]:
            with (
                self.subTest(key=key),
                patch.object(
                    p,
                    "verify_restoration_unused",
                    return_value={"native_actuals": good | {key: value}},
                ),
                self.assertRaises(RuntimeError),
            ):
                p.verify_actuals_restoration(None, None)


class PlanFinalizationTests(unittest.TestCase):
    def test_placeholder_or_incomplete_evidence_cannot_publish(self):
        plan = json.loads(Path(".github/release-plans/2251.json").read_text())
        with self.assertRaisesRegex(RuntimeError, "not finalized"):
            p.verify_plan(plan | {"finalized": False})
        ready = plan | {
            "recovery_file": ".github/release-plans/2251-recovery.zip",
            "recovery_parts": [
                {
                    "path": ".github/release-plans/2251-recovery-001.part",
                    "bytes": 1,
                    "sha256": "c" * 64,
                }
            ],
            "capital_tests": 14,
            "finalized": True,
            "draft_id": 1,
            "canonical_tests": 2,
            "canonical_entries": 3,
            "local_canonical_entries": 3,
            "product_tests": 4,
            "recovery_sha256": "a" * 64,
            "prior_evidence_sha256": "b" * 64,
            "runs": [run | {"id": index + 1} for index, run in enumerate(plan["runs"])],
            "artifacts": [
                {"file": n}
                for n in (
                    "current-production-coverage-original.zip",
                    "market-history-coverage-original.zip",
                    "canonical-original.zip",
                    "preflight-original.zip",
                    "trade-resource-original.zip",
                    "actuals-restoration-original.zip",
                    "restoration-unused-original.zip",
                    "resident-refresh-original.zip",
                    "league-entry-original.zip",
                    "current-history-original.zip",
                    "history-followthrough-original.zip",
                    "lifecycle-ordinary.zip",
                    "lifecycle-archive-warmed.zip",
                    "lifecycle-combined-read.zip",
                    "public-welcome-security.zip",
                )
            ],
        }
        p.verify_plan(ready)
        for field in (
            "draft_id",
            "canonical_tests",
            "canonical_entries",
            "local_canonical_entries",
            "product_tests",
        ):
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(RuntimeError, "Missing final release evidence"),
            ):
                p.verify_plan(ready | {field: None})
        with self.assertRaisesRegex(
            RuntimeError, "Missing mandatory release artifacts"
        ):
            p.verify_plan(ready | {"artifacts": []})
        for omitted in ("resident-refresh-original.zip", "public-welcome-security.zip"):
            with (
                self.subTest(omitted=omitted),
                self.assertRaisesRegex(RuntimeError, "Missing mandatory"),
            ):
                p.verify_plan(
                    ready
                    | {
                        "artifacts": [
                            a for a in ready["artifacts"] if a["file"] != omitted
                        ]
                    }
                )
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            p.verify_plan(
                ready | {"artifacts": ready["artifacts"] + [ready["artifacts"][0]]}
            )


class CurrentProductionIntegrityTests(unittest.TestCase):
    def test_exact_coverage_missing_safety_and_rendered_controls_are_required(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        complete = {
            "fantasy_points": 18,
            "observation_count": 8,
            "scored_count": 8,
            "season": 2026,
            "weeks": list(range(1, 9)),
        }
        partial = {
            "fantasy_points": None,
            "observation_count": 8,
            "scored_count": 7,
            "missing_components": ["conflicting_sleeper_scores"],
        }
        records = [
            {
                "league": league,
                "viewport": [w, h],
                "complete": complete,
                "partial": partial,
                "retained_failure": True,
                "keyboard": True,
                "overflow": False,
                "extra_disclosure_requests": 0,
                "touch_emulated": w < 1000,
            }
            for league in ("1314695233040052224", "1319750579458686976")
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
        ]
        memory = {
            "cgroup_limit_bytes": 2147483648,
            "cgroup_memory_events": {"oom": 0, "oom_kill": 0},
        }
        good = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "working_tree_clean": True,
            "records": records,
            "before_memory": memory,
            "after_memory": memory,
            "errors": [],
            "browser_closed": True,
            "requests": [{"path": "/market"}],
        }
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "production.zip"
            for mutation in (
                "valid",
                "source",
                "dirty",
                "population",
                "partial_value",
                "coverage",
                "retained",
                "overflow",
                "heavy",
                "oom",
                "png",
                "old_non_sleeper_gap",
            ):
                report = copy.deepcopy(good)
                if mutation == "old_non_sleeper_gap":
                    report["records"][0]["partial"].update(
                        scored_count=0, missing_components=["st_ff"]
                    )
                if mutation == "source":
                    report["head"] = "wrong"
                if mutation == "dirty":
                    report["working_tree_clean"] = False
                if mutation == "population":
                    report["records"].pop()
                if mutation == "partial_value":
                    report["records"][0]["partial"]["fantasy_points"] = 0
                if mutation == "coverage":
                    report["records"][0]["complete"]["scored_count"] = 7
                if mutation == "retained":
                    report["records"][0]["retained_failure"] = False
                if mutation == "overflow":
                    report["records"][0]["overflow"] = True
                if mutation == "heavy":
                    report["requests"].append({"path": "/sync"})
                if mutation == "oom":
                    report["after_memory"]["cgroup_memory_events"]["oom_kill"] = 1
                files = {"browser.json": json.dumps(report).encode()}
                files.update(
                    {
                        str(i) + ".png": b"\x89PNG\r\n\x1a\nfixture"
                        for i in range(23 if mutation == "png" else 24)
                    }
                )
                p.make_zip(target, files)
                with self.subTest(mutation=mutation):
                    if mutation == "valid":
                        self.assertEqual(
                            len(p.verify_current_production(target, plan)["records"]), 8
                        )
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_current_production(target, plan)


class PriorAttemptIdentityTests(unittest.TestCase):
    def test_history_uses_attempt_specific_endpoint_and_preserves_failure(self):
        record = {
            "id": 123,
            "run_attempt": 1,
            "name": "canonical",
            "head_sha": "a" * 40,
            "status": "completed",
            "conclusion": "failure",
            "html_url": "https://github.com/owner/repo/actions/runs/123/attempts/1",
        }
        with patch.object(p, "api", return_value=record) as reader:
            self.assertEqual(
                p.prior_attempt_record("repos/owner/repo", {"id": 123, "attempt": 1}),
                record,
            )
        reader.assert_called_once_with("repos/owner/repo/actions/runs/123/attempts/1")

    def test_history_cannot_substitute_latest_success_for_failed_attempt(self):
        with (
            patch.object(
                p,
                "api",
                return_value={"id": 123, "run_attempt": 2, "conclusion": "success"},
            ),
            self.assertRaisesRegex(RuntimeError, "identity mismatch"),
        ):
            p.prior_attempt_record("repos/owner/repo", {"id": 123, "attempt": 1})

    def test_invalid_history_reference_does_not_issue_a_request(self):
        for value in (
            {"id": True, "attempt": 1},
            {"id": 1, "attempt": 0},
            {"id": "1", "attempt": 1},
            {"id": 1, "attempt": 1, "path": "untrusted"},
            123,
        ):
            with self.subTest(value=value), patch.object(p, "api") as reader:
                with self.assertRaises(RuntimeError):
                    p.prior_attempt_record("repos/owner/repo", value)
                reader.assert_not_called()


class ResidentRefreshIntegrityTests(unittest.TestCase):
    def test_resource_source_cleanup_execution_and_checksums_are_required(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        cases = [
            {
                "name": name,
                "failed_refresh": failed,
                "reader": reader,
                "completed": True,
                "invalid_restore_preserved_current": True,
                "repeated_switches": 3,
                "cancellation_writer_drained": True,
                "old_released_without_reader": not reader,
                "source_digest": "c" * 64,
            }
            for name, failed, reader in [
                ("oneqb", False, False),
                ("oneqb", True, False),
                ("superflex", False, True),
            ]
        ]
        cases[-1].update(
            pressure_deferred=True,
            fois_protected=True,
            recovery_completed=True,
            relieved_fixture_bytes=64 * 1024**2,
            owner_release_plan={"telemetry_valid": True},
            recovery_plan={"would_admit": True},
        )
        cases.append(
            {
                "name": "global-evidence",
                "completed": True,
                "old_released_without_reader": True,
                "source_acquisition_mocked": True,
                "source_restoration_completed": True,
                "scheduler_cancelled": True,
                "source_digest": "c" * 64,
            }
        )
        good = {
            "schema": "resident-refresh-ownership-v2",
            "head": plan["candidate"],
            "tree": plan["tree"],
            "passed": True,
            "working_tree_clean": True,
            "cgroup_limit": 2147483648,
            "swap_limit": 0,
            "cpus": 2,
            "network": "none",
            "children_after": [],
            "scratch_removed": True,
            "source_values_preserved": True,
            "cases": cases,
            "samples": [
                {
                    "cgroup_limit_bytes": 2147483648,
                    "cgroup_memory_events": {"oom_kill": 0},
                }
            ],
            "liveness": [{"server_ms": 4.0, "client_ms": 8.0}],
        }
        mutations = {
            "none": lambda r: None,
            "source": lambda r: r.update(head="wrong"),
            "tree": lambda r: r.update(tree="wrong"),
            "limit": lambda r: r.update(cgroup_limit=1),
            "child": lambda r: r.update(children_after=[123]),
            "scratch": lambda r: r.update(scratch_removed=False),
            "values": lambda r: r.update(source_values_preserved=False),
            "case": lambda r: r["cases"].pop(),
            "deferred-as-complete": lambda r: r["cases"][0].update(completed=False),
            "writer": lambda r: r["cases"][1].update(cancellation_writer_drained=False),
            "reader": lambda r: r["cases"][2].update(old_released_without_reader=True),
            "recovery": lambda r: r["cases"][2].update(recovery_completed=False),
            "fois": lambda r: r["cases"][2].update(fois_protected=False),
            "oom": lambda r: r["samples"][0]["cgroup_memory_events"].update(oom_kill=1),
            "live": lambda r: r["liveness"][0].update(server_ms=501),
            "global": lambda r: r["cases"][3].update(old_released_without_reader=False),
            "global-restoration": lambda r: r["cases"][3].update(
                source_restoration_completed=False
            ),
            "sums": lambda r: None,
            "incomplete-sums": lambda r: None,
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, change in mutations.items():
                with self.subTest(name=name):
                    result = copy.deepcopy(good)
                    change(result)
                    data = json.dumps(result).encode()
                    files = {"evidence/result.json": data, "raw.log": b"original log"}
                    files["SHA256SUMS"] = "".join(
                        hashlib.sha256(b).hexdigest() + "  " + n + "\n"
                        for n, b in files.items()
                    ).encode()
                    if name == "sums":
                        files["raw.log"] += b"changed"
                    if name == "incomplete-sums":
                        files["SHA256SUMS"] = b""
                    target = Path(folder) / "resident.zip"
                    p.make_zip(target, files)
                    if name == "none":
                        self.assertTrue(
                            p.verify_resident_refresh(target, plan)["passed"]
                        )
                    else:
                        with self.assertRaises(RuntimeError):
                            p.verify_resident_refresh(target, plan)


class TradeTimeMarketPublisherTests(unittest.TestCase):
    def test_feature_source_phone_and_package_boundaries(self):
        import copy
        import tempfile
        import zipfile
        from pathlib import Path

        plan = {"candidate": "candidate", "tree": "tree"}
        phone = {
            "head": "candidate",
            "tree": "tree",
            "working_tree_clean": True,
            "records": [
                {
                    "width": w,
                    "height": h,
                    "keyboard": True,
                    "overflow": False,
                    "touch_emulated": w < 500,
                    "source_value": 321,
                    "age_seconds": 3600,
                    "extra_disclosure_requests": 0,
                    "errors": [],
                }
                for w, h in [(320, 432), (375, 667), (390, 844), (1280, 900)]
            ],
        }
        feature = {
            "head": "candidate",
            "tree": "tree",
            "working_tree_clean": True,
            "cases": [
                {
                    "case": k,
                    "selected_value": v,
                    "package_totals_displayed": False,
                    "retained_fixture_values": [{"value": v}],
                }
                for k, v in {
                    "newer_incompatible": 400,
                    "newer_foreign": 400,
                    "partial_old": 275,
                    "zero": 0,
                    "conflicting": None,
                }.items()
            ],
        }
        supplied = {
            "provenance": "Supplied Main Chat observation",
            "exhaustive": False,
            "complete_package_coverage": "Not established",
            "historical_league_format_parity": "Not established",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feature.zip"

            def write(ph, fe, sp):
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("feature/browser.json", json.dumps(ph))
                    z.writestr("feature/feature.json", json.dumps(fe))
                    z.writestr("supplied-screen.json", json.dumps(sp))

            write(phone, feature, supplied)
            self.assertTrue(p.verify_trade_time_market(path, plan)["passed"])
            for field, value in [
                ("head", "other"),
                ("tree", "other"),
                ("working_tree_clean", False),
            ]:
                bad = copy.deepcopy(feature)
                bad[field] = value
                write(phone, bad, supplied)
                with self.assertRaises(RuntimeError):
                    p.verify_trade_time_market(path, plan)
            bad = copy.deepcopy(phone)
            bad["records"][0]["extra_disclosure_requests"] = 1
            write(bad, feature, supplied)
            with self.assertRaises(RuntimeError):
                p.verify_trade_time_market(path, plan)
            bad = copy.deepcopy(feature)
            bad["cases"][0]["package_totals_displayed"] = True
            write(phone, bad, supplied)
            with self.assertRaises(RuntimeError):
                p.verify_trade_time_market(path, plan)
            bad = copy.deepcopy(supplied)
            bad["exhaustive"] = True
            write(phone, feature, bad)
            with self.assertRaises(RuntimeError):
                p.verify_trade_time_market(path, plan)


class CompletedTradePublisherTests(unittest.TestCase):
    def fixture(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        controls = (
            "Day retained trades; disposable waiver pagination",
            "Arkham sparse retained source",
        )
        report = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "working_tree_clean": True,
            "errors": [],
            "server_thread_reaped": True,
            "scope": "Retained source replay; no fresh production observation",
            "records": [],
        }
        for control in controls:
            for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                known = control == controls[0]
                report["records"].append(
                    {
                        "control": control,
                        "width": w,
                        "height": h,
                        "supported_trades": 2 if known else None,
                        "firsts_received": 3 if known else None,
                        "firsts_sent": 1 if known else None,
                        "keyboard": known,
                        "contextual_back": known,
                        "touch_emulated": known and w < 1000,
                        "overflow": False,
                    }
                )
        fields = (
            "completed_trades",
            "firsts_received",
            "firsts_sent",
            "receiving_trades",
            "sending_trades",
        )
        expected = {
            "retained_day": (2, 3, 1, 1, 1),
            "multi_team": (1, 2, 1, 1, 1),
            "partial_pick": (1, 1, None, 1, None),
            "supported_zero": (1, 0, 0, 0, 0),
            "unknown": (None, None, None, None, None),
        }
        feature = {
            "head": plan["candidate"],
            "tree": plan["tree"],
            "working_tree_clean": True,
            "live_observation": False,
            "source_fixture_sha256": "012de53aeefa4cfb4cb7de717910fa829f399b23d6f6ad7962598afe8c76833f",
            "raw_retained_expectations": dict(zip(fields, expected["retained_day"])),
            "cases": [],
        }
        for name, values in expected.items():
            row = {
                **dict(zip(fields, values)),
                "state": "unknown" if name == "unknown" else "partial",
                "references": [],
                "pick_counts_complete_in_sample": name != "partial_pick",
            }
            if name == "retained_day":
                row.update(
                    dated_trades=2,
                    first_completion_at="2026-03-01T14:01:05Z",
                    last_completion_at="2026-10-11T15:05:21Z",
                    references=[
                        {
                            "firsts_received": [
                                "PICK-2026-R1-ORIG8",
                                "PICK-2027-R1-ORIG7",
                                "PICK-2028-R1-ORIG7",
                            ],
                            "firsts_sent": ["PICK-2026-R1-ORIG5"],
                        }
                    ],
                )
            feature["cases"].append({"case": name, "summary": row})
        return plan, report, feature

    def test_completed_feature_fail_closed_source_counts_unknown_and_interaction(self):
        for change in (
            "control",
            "source",
            "dirty",
            "live",
            "unknown_zero",
            "unknown_omitted",
            "overcount",
            "back",
            "touch",
            "errors",
            "cleanup",
            "coverage",
            "pick_direction",
            "raw",
            "partial_zero",
            "screenshots",
        ):
            with (
                self.subTest(change=change),
                tempfile.TemporaryDirectory() as directory,
            ):
                plan, phone, feature = self.fixture()
                if change == "source":
                    phone["head"] = "c" * 40
                if change == "dirty":
                    feature["working_tree_clean"] = False
                if change == "live":
                    feature["live_observation"] = True
                if change == "unknown_zero":
                    phone["records"][-1]["supported_trades"] = 0
                if change == "unknown_omitted":
                    del feature["cases"][-1]["summary"]["firsts_sent"]
                if change == "overcount":
                    feature["cases"][1]["summary"]["completed_trades"] = 2
                if change == "back":
                    phone["records"][0]["contextual_back"] = False
                if change == "touch":
                    phone["records"][0]["touch_emulated"] = False
                if change == "errors":
                    phone["errors"] = ["failed"]
                if change == "cleanup":
                    phone["server_thread_reaped"] = False
                if change == "coverage":
                    feature["cases"][0]["summary"]["state"] = "complete"
                if change == "pick_direction":
                    feature["cases"][0]["summary"]["references"][0]["firsts_sent"] = [
                        "PICK-2026-R1-ORIG4"
                    ]
                if change == "raw":
                    feature["raw_retained_expectations"]["firsts_received"] = 9
                if change == "partial_zero":
                    feature["cases"][2]["summary"]["firsts_sent"] = 0
                files = {
                    "feature/browser.json": json.dumps(phone).encode(),
                    "feature/feature.json": json.dumps(feature).encode(),
                }
                files.update(
                    {
                        "feature/" + str(i) + ".png": b"\x89PNG\r\n\x1a\n"
                        for i in range(7 if change == "screenshots" else 8)
                    }
                )
                path = Path(directory) / "feature.zip"
                p.make_zip(path, files)

                def verify(path=path, plan=plan):
                    p.verify_completed_trade_browser(path, plan, prefix="feature/")
                    return p.verify_completed_trade_cases(path, plan)

                if change == "control":
                    self.assertTrue(verify()["passed"])
                else:
                    with self.assertRaises(RuntimeError):
                        verify()

    def test_new_browser_namespace_does_not_replace_original_history_screenshots(self):
        with tempfile.TemporaryDirectory() as directory:
            plan, phone, _ = self.fixture()
            prefix = "completed-trade-observations/"
            files = {prefix + "browser.json": json.dumps(phone).encode()}
            files.update(
                {prefix + str(i) + ".png": b"\x89PNG\r\n\x1a\n" for i in range(8)}
            )
            files.update({str(i) + ".png": b"\x89PNG\r\n\x1a\n" for i in range(8)})
            path = Path(directory) / "browser.zip"
            p.make_zip(path, files)
            self.assertTrue(p.verify_completed_trade_browser(path, plan)["passed"])
            del files["0.png"]
            p.make_zip(path, files)
            with self.assertRaises(RuntimeError):
                p.verify_completed_trade_browser(path, plan)
            files["0.png"] = b"\x89PNG\r\n\x1a\n"
            files["unapproved/extra.png"] = b"\x89PNG\r\n\x1a\n"
            p.make_zip(path, files)
            with self.assertRaises(RuntimeError):
                p.verify_completed_trade_browser(path, plan)


class PartnerHistoryLinkIntegrityTests(unittest.TestCase):
    def reports(self):
        identity = {
            "commit": "a" * 40,
            "tree": "b" * 40,
            "source": "disposable prepared league; real authenticated HTTP and evaluator",
            "physical_safari_tested": False,
        }
        evaluation = dict(
            identity,
            checks=[
                {
                    "viewport": [w, h],
                    "mode": "custom",
                    "draft": {"sent": ["a"], "received": ["2028-R1-4"], "partner": 2},
                    "filters": {
                        "sent": {"q": "a", "pos": "ALL"},
                        "received": {"q": "", "pos": "ALL"},
                    },
                    "post_requests": [["POST", "/api/trades/evaluate", 200]],
                }
                for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
            ],
        )
        recommendation = dict(
            identity,
            checks=[
                {
                    "viewport": [w, h],
                    "draft": {"sent": [], "received": [], "partner": 0},
                    "preview": {
                        "partner_roster_id": 2,
                        "assets_sent": ["a"],
                        "assets_received": ["2028-R1-4"],
                    },
                    "post_requests": [["POST", "/api/trades/generate", 200]],
                }
                for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
            ],
        )
        return evaluation, recommendation

    def verify(self, alter=None):
        evaluation, recommendation = self.reports()
        if alter:
            alter(evaluation, recommendation)
        files = {
            "trade-partner-history/" + name + "-round-trip.json": json.dumps(
                report
            ).encode()
            for name, report in [
                ("evaluation", evaluation),
                ("recommendation", recommendation),
            ]
        }
        files.update(
            {
                "trade-partner-history/"
                + flow
                + "-"
                + str(width)
                + "-"
                + stage
                + ".png": b"\x89PNG\r\n\x1a\n"
                for flow in ("create", "recommended")
                for width in (320, 375, 390, 1280)
                for stage in ("history", "returned")
            }
        )
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "fixture.zip"
            p.make_zip(target, files)
            return p.verify_partner_history_links(
                target, {"candidate": "a" * 40, "tree": "b" * 40}
            )

    def test_two_source_bound_four_viewport_round_trips_are_required(self):
        self.assertTrue(self.verify()["passed"])
        for key, value in [
            ("commit", "x" * 40),
            ("tree", "x" * 40),
            ("physical_safari_tested", True),
            ("source", "live"),
        ]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verify(lambda e, r, key=key, value=value: e.update({key: value}))
        with self.assertRaises(RuntimeError):
            self.verify(lambda e, r: r["checks"].pop())

    def test_extra_work_lost_draft_filters_preview_or_exact_picks_block_publication(
        self,
    ):
        changes = [
            lambda e, r: e["checks"][0]["post_requests"].append(
                ["POST", "/api/trades/evaluate", 200]
            ),
            lambda e, r: e["checks"][0].update(mode="neutral"),
            lambda e, r: e["checks"][0]["filters"]["sent"].update(q="lost"),
            lambda e, r: e["checks"][0]["draft"].update(received=["2028-R1-2"]),
            lambda e, r: r["checks"][0]["draft"].update(sent=["a"]),
            lambda e, r: r["checks"][0]["preview"].update(partner_roster_id=3),
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.verify(change)


if __name__ == "__main__":
    unittest.main()


class TeamNeedHandoffGuardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "team-need.zip"
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40}
        self.reports = {
            "phone-round-trips": [
                {
                    "width": w,
                    "height": h,
                    "handoff": "RB starter",
                    "draft_and_custom_preserved": True,
                    "changed_and_cleared_after_reload": True,
                    "no_automatic_search": True,
                    "position_visible_on_entry": True,
                    "position_clear_of_back_bar": True,
                    "type_filter_preserves_need_reason": True,
                    "back": "My Team",
                    "overflow": 0,
                }
                for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
            ],
            "superflex-depth-and-stale": {
                "depth_distinct": True,
                "stale_hint_rejected": True,
                "general_shortcut": True,
                "no_automatic_search": True,
                "stale_manual_filter_preserved": True,
            },
            "real-search-and-prior-context": {
                "real_evaluations": True,
                "prior_contexts": 2,
                "position_applied_only_on_generate": True,
                "old_results_separate": True,
                "explicit_reset_clears_prior_context": True,
            },
            "league-switch": {
                "hint_discarded": True,
                "old_draft_not_loaded": True,
                "no_automatic_search": True,
            },
        }

    def verify(self, *, source=None, omit=None):
        files = {
            "browser/team-need/" + name + ".json": json.dumps(
                {
                    "commit": source or self.plan["candidate"],
                    "tree": self.plan["tree"],
                    "source": "disposable authenticated prepared Sleeper fixture",
                    "physical_safari_tested": False,
                    "observations": rows,
                }
            ).encode()
            for name, rows in self.reports.items()
            if name != omit
        }
        p.make_zip(self.path, files)
        return p.verify_team_need_handoff(self.path, self.plan)

    def test_complete_source_bound_fixture_passes(self):
        self.assertTrue(self.verify()["passed"])

    def test_wrong_candidate_is_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "source mismatch"):
            self.verify(source="c" * 40)

    def test_missing_report_is_blocked(self):
        with self.assertRaises(KeyError):
            self.verify(omit="league-switch")

    def test_missing_phone_is_blocked(self):
        self.reports["phone-round-trips"].pop()
        with self.assertRaisesRegex(RuntimeError, "phone controls"):
            self.verify()

    def test_lost_draft_or_custom_blocks_publication(self):
        self.reports["phone-round-trips"][0]["draft_and_custom_preserved"] = False
        with self.assertRaisesRegex(RuntimeError, "draft or explicit"):
            self.verify()

    def test_deferred_does_not_count_as_real_execution(self):
        self.reports["real-search-and-prior-context"]["real_evaluations"] = False
        with self.assertRaisesRegex(RuntimeError, "completed evaluation absent"):
            self.verify()

    def test_auto_search_blocks_publication(self):
        self.reports["superflex-depth-and-stale"]["no_automatic_search"] = False
        with self.assertRaisesRegex(RuntimeError, "depth or stale"):
            self.verify()

    def test_stale_league_hint_blocks_publication(self):
        self.reports["league-switch"]["hint_discarded"] = False
        with self.assertRaisesRegex(RuntimeError, "league isolation"):
            self.verify()

    def test_hidden_position_blocks_publication(self):
        self.reports["phone-round-trips"][0]["position_visible_on_entry"] = False
        with self.assertRaisesRegex(RuntimeError, "draft or explicit"):
            self.verify()

    def test_obscured_label_blocks_publication(self):
        self.reports["phone-round-trips"][0]["position_clear_of_back_bar"] = False
        with self.assertRaisesRegex(RuntimeError, "draft or explicit"):
            self.verify()

    def test_type_change_losing_reason_blocks_publication(self):
        self.reports["phone-round-trips"][0]["type_filter_preserves_need_reason"] = (
            False
        )
        with self.assertRaisesRegex(RuntimeError, "draft or explicit"):
            self.verify()

    def test_stale_manual_override_lost_blocks_publication(self):
        self.reports["superflex-depth-and-stale"]["stale_manual_filter_preserved"] = (
            False
        )
        with self.assertRaisesRegex(RuntimeError, "depth or stale"):
            self.verify()

    def test_explicit_reset_retaining_context_blocks_publication(self):
        self.reports["real-search-and-prior-context"][
            "explicit_reset_clears_prior_context"
        ] = False
        with self.assertRaisesRegex(RuntimeError, "completed evaluation absent"):
            self.verify()


class OfferComparisonEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "comparison.zip"
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40}
        self.observations = {
            "phone-round-trips": [
                {"width": w, "height": h, "preserved_draft": True, "no_http": True}
                for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))
            ],
            "superflex-depth-replace-remove": {
                "missing_depth_qualified": True,
                "counterparty_attached": True,
                "explicit_replacement": True,
                "no_http": True,
            },
            "neutral-custom": {
                "actual_evaluations": 2,
                "neutral_values_match_originals": True,
                "custom_values_match_original": True,
                "modes_separate": True,
                "no_http": True,
            },
            "partial-pair": {
                "actual_evaluations": 2,
                "supported_individual_delta_preserved": True,
                "incomplete_other_lineup_unknown": True,
                "no_http": True,
            },
            "two-generations": {
                "actual_evaluations": 2,
                "incompatible_generations_withheld": True,
                "original_packages_retained": True,
                "no_http": True,
            },
            "aged-incompatible": {
                "shared_numbers_withheld": True,
                "retained_offer_visible": True,
                "no_http": True,
            },
            "retained-reload": {
                "same_prepared_generation": True,
                "retained_qualification_visible": True,
                "exact_draft": True,
                "no_http": True,
            },
            "custom-incomplete-reload": {
                "same_prepared_generation": True,
                "original_incomplete_lineup_preserved": True,
                "draft_mode_does_not_mutate_selected_assessment": True,
                "retained_qualification_visible": True,
                "exact_draft": True,
                "no_http": True,
            },
            "recommendation-league-scope": {
                "real_searches": 1,
                "qualified_source_offers": 1,
                "no_comparison_search": True,
                "no_adoption": True,
                "league_switch_discards_comparison": True,
            },
        }
        for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            self.observations["phone-" + str(w)] = {
                "width": w,
                "height": h,
                "independent_evaluations": 2,
                "no_http": True,
                "higher_gain_higher_cost": True,
                "asset_order_preserved": True,
                "native_deltas": [4.0, 8.0],
                "native_sent_market": [250.0, 500.0],
            }
        self.metadata = {
            "commit": self.plan["candidate"],
            "tree": self.plan["tree"],
            "working_tree_clean": True,
            "source": "Disposable authenticated prepared Sleeper fixture; actual canonical evaluator",
            "physical_safari_tested": False,
        }

    def verify(self, drop_image=False):
        files = {
            "browser/offer-comparison/" + name + ".json": json.dumps(
                dict(self.metadata, observations=row)
            ).encode()
            for name, row in self.observations.items()
        }
        for width in (320, 375, 390, 1280):
            if not drop_image or width != 320:
                files["browser/offer-comparison/phone-" + str(width) + ".png"] = (
                    b"\x89PNG\r\n\x1a\nfixture"
                )
        p.make_zip(self.path, files)
        return p.verify_offer_comparison(self.path, self.plan)

    def test_complete_source_bound_native_controls(self):
        self.assertTrue(self.verify()["passed"])
        for mode in ("complete", "absent", "foreign-source"):
            with self.subTest(native_comparison=mode):
                self.assert_native_collection_boundary(mode)

    def assert_native_collection_boundary(self, mode):
        """Recovery never substitutes for a missing or incompatible native proof."""

        class ReachedRecovery(Exception):
            pass

        root = Path(self.folder.name) / ("collect-" + mode)
        root.mkdir()
        canonical = root / "canonical.zip"
        p.make_zip(
            canonical, {"fixture.txt": b"Canonical guard is covered independently."}
        )
        native = root / "native.zip"
        with zipfile.ZipFile(self.path) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        if mode == "foreign-source":
            for name, raw in list(files.items()):
                if name.endswith(".json"):
                    row = json.loads(raw)
                    row["commit"] = "c" * 40
                    files[name] = json.dumps(row).encode()
        p.make_zip(native, files)
        recovery = root / "recovery.zip"
        p.make_zip(recovery, {"fixture.txt": b"No duplicate offer-comparison family."})
        originals = {"canonical-original.zip": canonical}
        if mode != "absent":
            originals["trade-resource-original.zip"] = native
        artifacts = [
            {
                "id": index,
                "run": 100,
                "file": name,
                "name": name,
                "sha256": p.digest(path),
            }
            for index, (name, path) in enumerate(originals.items(), 1)
        ]
        by_id = {row["id"]: row for row in artifacts}
        plan = self.plan | {
            "repository": "fixture/repository",
            "artifacts": artifacts,
            "recovery_file": str(recovery),
            "recovery_sha256": p.digest(recovery),
        }

        def metadata(endpoint):
            row = by_id[int(endpoint.rsplit("/", 1)[1])]
            return {
                "expired": False,
                "name": row["name"],
                "digest": "sha256:" + row["sha256"],
                "size_in_bytes": originals[row["file"]].stat().st_size,
                "workflow_run": {"id": row["run"], "head_sha": plan["candidate"]},
            }

        def download(endpoint, target):
            row = by_id[int(endpoint.split("/")[-2])]
            target.write_bytes(originals[row["file"]].read_bytes())

        with ExitStack() as stack:
            stack.enter_context(patch.object(p, "verify_runs", return_value=([], 1)))
            stack.enter_context(patch.object(p, "api", side_effect=metadata))
            stack.enter_context(patch.object(p, "download", side_effect=download))
            stack.enter_context(
                patch.object(p, "verify_canonical", return_value={"passed": True})
            )
            for name in (
                "verify_trade_resource",
                "verify_team_need_handoff",
                "verify_recommended_protections",
                "verify_activation_deferral",
                "verify_front_office_workflow",
                "verify_capital_test_execution",
                "verify_market_roster_tests",
                "verify_roster_source_scope_tests",
                "verify_franchise_progress_tests",
                "verify_acquisition_tests",
                "verify_normal_execution_tests",
                "verify_roster_source_scope",
                "verify_market_roster",
                "verify_draft_capital",
            ):
                stack.enter_context(
                    patch.object(p, name, return_value={"passed": True})
                )
            comparison = stack.enter_context(
                patch.object(
                    p, "verify_offer_comparison", wraps=p.verify_offer_comparison
                )
            )
            stack.enter_context(
                patch.object(p, "materialize_recovery", return_value=recovery)
            )
            local = stack.enter_context(
                patch.object(p, "verify_local_recovery", side_effect=ReachedRecovery)
            )
            if mode == "complete":
                with self.assertRaises(ReachedRecovery):
                    p.collect(plan, root / "output")
                comparison.assert_called_once_with(
                    root / "output/assets/trade-resource-original.zip", plan
                )
                local.assert_called_once_with(recovery, plan)
            elif mode == "absent":
                with self.assertRaisesRegex(
                    RuntimeError, "Hosted offer comparison proof absent"
                ):
                    p.collect(plan, root / "output")
                comparison.assert_not_called()
                local.assert_not_called()
            else:
                with self.assertRaisesRegex(RuntimeError, "source mismatch"):
                    p.collect(plan, root / "output")
                comparison.assert_called_once()
                local.assert_not_called()

    def test_source_revision_or_dirty_tree_cannot_pass(self):
        for key, bad in [
            ("commit", "c" * 40),
            ("tree", "d" * 40),
            ("working_tree_clean", False),
        ]:
            with self.subTest(key=key):
                saved = self.metadata[key]
                self.metadata[key] = bad
                with self.assertRaisesRegex(RuntimeError, "source mismatch"):
                    self.verify()
                self.metadata[key] = saved

    def test_fixture_cannot_claim_physical_or_live_scope(self):
        self.metadata["physical_safari_tested"] = True
        with self.assertRaisesRegex(RuntimeError, "scope"):
            self.verify()

    def test_missing_viewport_or_screenshot_blocks(self):
        with self.assertRaises(KeyError):
            self.verify(drop_image=True)
        self.observations["phone-round-trips"].pop()
        with self.assertRaisesRegex(RuntimeError, "phone round trip"):
            self.verify()

    def test_extra_http_or_mutated_draft_blocks(self):
        for key in ["preserved_draft", "no_http"]:
            self.observations["phone-round-trips"][0][key] = False
            with self.assertRaisesRegex(RuntimeError, "phone round trip"):
                self.verify()
            self.observations["phone-round-trips"][0][key] = True

    def test_fabricated_gain_or_cost_controls_block(self):
        for values in ([4, 4], [4, float("nan")], [4, None]):
            self.observations["phone-320"]["native_deltas"] = values
            with self.assertRaisesRegex(RuntimeError, "gain/cost"):
                self.verify()

    def test_missing_depth_stale_scope_and_custom_controls_block(self):
        for name, key in [
            ("superflex-depth-replace-remove", "counterparty_attached"),
            ("partial-pair", "incomplete_other_lineup_unknown"),
            ("two-generations", "incompatible_generations_withheld"),
            ("aged-incompatible", "shared_numbers_withheld"),
            ("neutral-custom", "modes_separate"),
            ("retained-reload", "retained_qualification_visible"),
            (
                "custom-incomplete-reload",
                "draft_mode_does_not_mutate_selected_assessment",
            ),
            ("recommendation-league-scope", "league_switch_discards_comparison"),
        ]:
            with self.subTest(name=name):
                self.observations[name][key] = False
                with self.assertRaisesRegex(RuntimeError, "control missing"):
                    self.verify()
                self.observations[name][key] = True

    def test_missing_real_evaluation_or_qualified_control_blocks(self):
        self.observations["neutral-custom"]["actual_evaluations"] = 0
        with self.assertRaisesRegex(RuntimeError, "actual evaluation count"):
            self.verify()
        self.observations["neutral-custom"]["actual_evaluations"] = 2
        self.observations["recommendation-league-scope"]["qualified_source_offers"] = 0
        with self.assertRaisesRegex(RuntimeError, "qualified native control"):
            self.verify()


class RecommendedProtectionIntegrityTests(unittest.TestCase):
    def fixture(self):
        plan = {"candidate": "a" * 40, "tree": "b" * 40}
        # Verifier-only synthetic records. Real canonical captures are verified
        # independently against the actual candidate before preparation.
        observations = {
            "exact-native-search": {
                "payload": {"protected_assets": ["2029-R1-1", "a"]},
                "constraints": {"protected_assets": ["2029-R1-1", "a"]},
                "candidate_pools": [["b", "2029-R1-3"]],
                "offers": [{"proposal": {"assets_sent": ["b"]}}],
                "saved_preferences_unchanged": True,
            },
            "clear-and-prior-results": {
                "old_results_not_relabeled": True,
                "clearing_did_not_search": True,
                "first_constraints": {"protected_assets": ["2029-R1-1"]},
                "second_constraints": {"protected_assets": []},
            },
            "draft-and-scope": {
                "real_evaluations": 2,
                "recommended_controls_not_applied_to_evaluate": True,
                "original_draft_retained": True,
                "comparison_proposals_retained": True,
                "reload_retained": True,
                "league_switch_cleared": True,
            },
            "completed-zero-result": {
                "completed": True,
                "no_protection_causality_claim": True,
                "payload": {"protected_assets": ["a"]},
                "body": {"results": [], "exploratory_results": []},
            },
        }
        for width, height in [(320, 432), (375, 667), (390, 844), (1280, 900)]:
            observations["phone-" + str(width)] = {
                "width": width,
                "height": height,
                "exact_ids": ["2029-R1-1", "a"],
                "no_search_from_controls": True,
            }
        files = {}
        for name, facts in observations.items():
            row = {
                "commit": plan["candidate"],
                "tree": plan["tree"],
                "working_tree_clean": True,
                "source": "Disposable prepared Sleeper fixture; actual authenticated routes, canonical search and admission",
                "physical_safari_tested": False,
                "observations": facts,
            }
            files["browser/protections/" + name + ".json"] = json.dumps(row).encode()
            if name.startswith("phone-"):
                files["browser/protections/" + name + ".png"] = b"\x89PNG\r\n\x1a\n"
        return plan, files

    def check(self, change=None):
        plan, files = self.fixture()
        if change:
            change(plan, files)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "proof.zip"
            p.make_zip(path, files)
            return p.verify_recommended_protections(path, plan)

    def test_complete_native_contract(self):
        self.assertTrue(self.check()["passed"])

    def test_protected_asset_in_result_is_rejected(self):
        def change(plan, files):
            key = "browser/protections/exact-native-search.json"
            row = json.loads(files[key])
            row["observations"]["offers"][0]["proposal"]["assets_sent"].append(
                "2029-R1-1"
            )
            files[key] = json.dumps(row).encode()

        with self.assertRaisesRegex(RuntimeError, "escaped"):
            self.check(change)

    def test_foreign_source_and_missing_phone_are_rejected(self):
        for change in [
            lambda plan, files: plan.update(tree="c" * 40),
            lambda plan, files: files.pop("browser/protections/phone-320.png"),
        ]:
            with self.assertRaises((RuntimeError, KeyError)):
                self.check(change)


class ActivationEvidenceIntegrityTests(unittest.TestCase):
    PREFIXES = ("browser/activation/", "local-canonical/activation/")

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "activation.zip"
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40}

        def record(observations):
            return json.dumps(
                {
                    "commit": self.plan["candidate"],
                    "tree": self.plan["tree"],
                    "working_tree_clean": True,
                    "physical_safari_tested": False,
                    "scope": "Disposable authenticated native route/manager/guard controls; modeled telemetry identified, not live Granite",
                    "observations": observations,
                }
            ).encode()

        self.files = {
            "browser/activation/typed-capacity.json": record(
                {
                    "html": 503,
                    "api": {"status": "deferred", "code": "league_preparation_waiting"},
                    "retry_after": "60",
                    "account_unchanged": True,
                    "source_requests": 0,
                    "actual_hydrations": 1,
                }
            ),
            "browser/activation/real-recovery.json": record(
                {
                    "initial": 503,
                    "explicit_retry": 303,
                    "warm": True,
                    "source_values_preserved": True,
                    "source_requests": 0,
                    "limitation": "Small compatible fixture, actual enforced memory telemetry; not private Granite payload or live acceptance",
                }
            ),
        }
        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
            self.files["browser/activation/phone-" + str(width) + ".json"] = record(
                {
                    "viewport": [width, height],
                    "status": 503,
                    "retry_after": "60",
                    "no_overflow": True,
                    "no_new_source_requests": True,
                    "account_unchanged": True,
                }
            )
            self.files["browser/activation/phone-" + str(width) + ".png"] = (
                b"\x89PNG\r\n\x1a\n"
            )

    def verify(self, prefix="browser/activation/"):
        files = {
            prefix + name.removeprefix("browser/activation/"): raw
            for name, raw in self.files.items()
        }
        p.make_zip(self.path, files)
        return p.verify_activation_deferral(self.path, self.plan, prefix=prefix)

    def alter(self, name, key, value, observations=True):
        path = "browser/activation/" + name + ".json"
        row = json.loads(self.files[path])
        (row["observations"] if observations else row)[key] = value
        self.files[path] = json.dumps(row).encode()

    def test_complete_typed_and_actual_retry_controls(self):
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])
                wrong = next(value for value in self.PREFIXES if value != prefix)
                with self.assertRaises(KeyError):
                    p.verify_activation_deferral(self.path, self.plan, prefix=wrong)

    def test_deferred_retry_is_not_completion(self):
        self.alter("real-recovery", "explicit_retry", 503)
        for prefix in self.PREFIXES:
            with (
                self.subTest(prefix=prefix),
                self.assertRaisesRegex(RuntimeError, "retry completion"),
            ):
                self.verify(prefix=prefix)

    def test_generic_error_is_not_typed_deferral(self):
        self.alter("typed-capacity", "api", {"status": "failed"})
        for prefix in self.PREFIXES:
            with (
                self.subTest(prefix=prefix),
                self.assertRaisesRegex(RuntimeError, "Typed activation"),
            ):
                self.verify(prefix=prefix)

    def test_wrong_source_cannot_pass(self):
        original = copy.deepcopy(self.files)
        for key, value in [
            ("commit", "c" * 40),
            ("tree", "d" * 40),
            ("working_tree_clean", False),
        ]:
            self.files = copy.deepcopy(original)
            self.alter("phone-320", key, value, False)
            for prefix in self.PREFIXES:
                with (
                    self.subTest(key=key, prefix=prefix),
                    self.assertRaisesRegex(RuntimeError, "source mismatch"),
                ):
                    self.verify(prefix=prefix)

    def test_missing_phone_or_changed_account_cannot_pass(self):
        original = copy.deepcopy(self.files)
        del self.files["browser/activation/phone-390.png"]
        for prefix in self.PREFIXES:
            with (
                self.subTest(prefix=prefix, invalid="missing image"),
                self.assertRaises(KeyError),
            ):
                self.verify(prefix=prefix)
        self.files = copy.deepcopy(original)
        self.files["browser/activation/phone-390.png"] = b"not a PNG"
        for prefix in self.PREFIXES:
            with (
                self.subTest(prefix=prefix, invalid="image signature"),
                self.assertRaisesRegex(RuntimeError, "image missing"),
            ):
                self.verify(prefix=prefix)
        self.files = original
        self.alter("phone-375", "account_unchanged", False)
        for prefix in self.PREFIXES:
            with (
                self.subTest(prefix=prefix, invalid="account changed"),
                self.assertRaisesRegex(RuntimeError, "phone coverage"),
            ):
                self.verify(prefix=prefix)

    def test_fixture_cannot_claim_live_access(self):
        original = copy.deepcopy(self.files)
        for key, value in [
            ("scope", "Live Granite recovery"),
            ("physical_safari_tested", True),
        ]:
            self.files = copy.deepcopy(original)
            self.alter("real-recovery", key, value, False)
            for prefix in self.PREFIXES:
                with (
                    self.subTest(key=key, prefix=prefix),
                    self.assertRaisesRegex(RuntimeError, "scope mismatch"),
                ):
                    self.verify(prefix=prefix)


class FrontOfficeWorkflowIntegrityTests(unittest.TestCase):
    """Verifier-only records; native candidate captures supply execution proof."""

    PREFIXES = (
        "browser/front-office-workflow/",
        "local-canonical/front-office-workflow/",
    )

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "front-office.zip"
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40}
        self.metadata = {
            "commit": self.plan["candidate"],
            "tree": self.plan["tree"],
            "working_tree_clean": True,
            "source": "Disposable authenticated prepared Sleeper fixture; native search and canonical evaluator",
            "physical_safari_tested": False,
        }
        fingerprint = "f" * 64
        href = "/trades/recommended?front_office=1&team_need=" + fingerprint
        views = ((320, 432), (375, 667), (390, 844), (1280, 900))
        context = {
            "binding": "account-session-league-1",
            "league_id": "league-1",
            "roster_id": 1,
            "ownership_generation": "ownership-a",
        }
        payload = {
            "workflow": "recommended",
            "active_roster_id": 1,
            "partner_roster_id": 0,
            "recommendation_position": "RB",
            "recommendation_filter": "all",
            "protected_assets": ["2029-R1-1", "a"],
            "workspace_context": context,
        }
        evaluations = [
            {
                "active_roster_id": 1,
                "partner_roster_id": 2,
                "assets_sent": sent,
                "assets_received": [target],
                "protected_assets": [],
                "workspace_context": copy.deepcopy(context),
            }
            for sent, target in ((["a"], "d"), (["2028-R1-3", "a"], "c"), (["a"], "f"))
        ]
        proposals = [
            {
                key: value[key]
                for key in (
                    "active_roster_id",
                    "partner_roster_id",
                    "assets_sent",
                    "assets_received",
                )
            }
            for value in evaluations
        ]
        base = {
            "league": "league-1",
            "roster": 1,
            "ownership": "ownership-a",
            "lineup": "lineup-a",
            "season": 2026,
            "week": 2,
            "scoring": "scoring-a",
            "projection": "projection-a",
            "provider": "Sleeper",
        }
        selected, actual = [], []
        for index, proposal in enumerate(proposals[:2]):
            market = {
                "availability": "full",
                "sent": {"total": 100 + index},
                "received": {"total": 104 + index},
            }
            selected.append(
                {
                    "scope": {
                        "binding": context["binding"],
                        "league": "league-1",
                        "roster": 1,
                    },
                    "baseline": copy.deepcopy(base),
                    "proposal": copy.deepcopy(proposal),
                    "identity": {
                        "binding": context["binding"],
                        "ownership": "ownership-a",
                        "market": "market-a",
                        "package": json.dumps(
                            [
                                2,
                                sorted(proposal["assets_sent"]),
                                proposal["assets_received"],
                            ]
                        ),
                    },
                    "summary": {
                        "verdict": "NOT WORTH IT",
                        "mode": "neutral",
                        "neutral": {
                            "availability": "full",
                            "sent": 100 + index,
                            "received": 104 + index,
                        },
                        "lineup": {
                            "state": "supported",
                            "pre_total": 100,
                            "post_total": 104 + index,
                            "delta": 4 + index,
                            "weeks": [2],
                            "season": 2026,
                            "league_id": "league-1",
                            "scoring_profile_id": "scoring-a",
                            "projection_generation": "projection-a",
                        },
                    },
                }
            )
            actual.append(
                {
                    "recommendation": "NOT WORTH IT",
                    "market": market,
                    "lineup": dict(
                        selected[-1]["summary"]["lineup"],
                        season=2026,
                        league_id="league-1",
                        scoring_profile_id="scoring-a",
                        projection_generation="projection-a",
                    ),
                }
            )
        row = {
            "league_slots": ["QB", "RB", "WR", "FLEX", "K", "DEF", "BN"],
            "home": [
                {
                    "width": w,
                    "height": h,
                    "title": "RB starter need",
                    "action": "Explore RB trades →",
                    "href": href,
                }
                for w, h in views
            ],
            "handoff": {
                "position": "RB",
                "href": href,
                "explanation": "Week 2: a supported RB addition. Change or clear, then Generate.",
                "existing_my_team_reused": True,
                "initial_choice": {
                    "fingerprint": fingerprint,
                    "position": "RB",
                    "manual": False,
                },
                "edited_choice": {
                    "fingerprint": fingerprint,
                    "position": "",
                    "manual": True,
                },
            },
            "protection_views": [
                {"width": w, "height": h, "exact_ids": ["2029-R1-1", "a"]}
                for w, h in views
            ],
            "generation_payload": payload,
            "applied_constraints": {"protected_assets": ["2029-R1-1", "a"]},
            "outgoing_pools": [["b", "2029-R1-3"]],
            "exact_protected_ids": ["2029-R1-1", "a"],
            "distinct_same_round_pick": "2029-R1-3",
            "distinct_pick_remained_eligible": True,
            "native_offers": [
                {
                    "family": "exploratory_results",
                    "proposal": {
                        "active_roster_id": 1,
                        "partner_roster_id": 2,
                        "assets_sent": ["b"],
                        "assets_received": ["c"],
                    },
                    "recommendation": "NOT WORTH IT",
                    "generated_trade_eligible": False,
                    "exploration": True,
                }
            ],
            "prior_search": {
                "position": "RB",
                "type": "all",
                "count": 1,
                "protections": [
                    {"id": "2029-R1-1", "label": "Own first"},
                    {"id": "a", "label": "Player a"},
                ],
            },
            "actual_evaluations": actual,
            "comparison_offers": selected,
            "comparison_and_history": [
                {
                    "width": w,
                    "height": h,
                    "exact_draft": {
                        "partner": 2,
                        "sent": ["2028-R1-3", "a"],
                        "received": ["c"],
                    },
                    "panel_state": "retained",
                    "keep_option": "Keep the roster · no trade",
                    "comparison_retained": True,
                    "history_qualification": "retained",
                    "history_return_without_post": True,
                }
                for w, h in views
            ],
            "post_requests": [["POST", "/api/trades/generate", 200]]
            + [["POST", "/api/trades/evaluate", 200]] * 3,
            "post_ledger": [
                {
                    "path": "/api/trades/generate",
                    "status": 200,
                    "payload": copy.deepcopy(payload),
                }
            ]
            + [
                {"path": "/api/trades/evaluate", "status": 200, "payload": value}
                for value in evaluations
            ],
            "reload_retained": True,
            "replacement": {
                "selected_proposals": [proposals[2], proposals[1]],
                "remaining_proposals": [proposals[1]],
                "draft": {"partner": 2, "sent": ["a"], "received": ["f"]},
            },
            "scope_change": {
                "old": context["binding"],
                "current": "account-session-league-2",
                "temporary_state_cleared": True,
                "before_protections": ["2029-R1-1", "a"],
                "before_position": "QB",
                "before_draft": {"partner": 2, "sent": ["a"], "received": ["f"]},
            },
            "saved_goal_and_rankings_unchanged": True,
        }
        self.rows = {"1qb-k-def-journey": row, "superflex-journey": copy.deepcopy(row)}
        self.rows["superflex-journey"]["league_slots"] = [
            "QB",
            "SUPER_FLEX",
            "RB",
            "WR",
            "FLEX",
            "BN",
        ]

    def verify(self, prefix="browser/front-office-workflow/", omit=None):
        files = {}
        for name, row in self.rows.items():
            files[prefix + name + ".json"] = json.dumps(
                dict(self.metadata, observations=row)
            ).encode()
            files[prefix + name + ".png"] = b"\x89PNG\r\n\x1a\nfixture"
        if omit:
            del files[prefix + omit]
        p.make_zip(self.path, files)
        return p.verify_front_office_workflow(self.path, self.plan, prefix=prefix)

    def reject(self, change, message):
        original = copy.deepcopy(self.rows)
        try:
            change(self.rows["1qb-k-def-journey"])
            for prefix in self.PREFIXES:
                with (
                    self.subTest(prefix=prefix),
                    self.assertRaisesRegex(RuntimeError, message),
                ):
                    self.verify(prefix=prefix)
        finally:
            self.rows = original

    def test_native_qualification_is_preserved_without_requiring_endorsement(self):
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])
                wrong = next(value for value in self.PREFIXES if value != prefix)
                with self.assertRaises(KeyError):
                    p.verify_front_office_workflow(self.path, self.plan, prefix=wrong)

    def test_zero_offers_are_valid_with_actual_nonempty_exclusion_pools(self):
        for row in self.rows.values():
            row["native_offers"] = []
            row["prior_search"]["count"] = 0
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])

    def test_missing_near_miss_verdict_is_retained_without_becoming_an_offer(self):
        for row in self.rows.values():
            row["native_offers"][0].update(
                family="near_misses", recommendation=None, exploration=False
            )
            row["prior_search"]["count"] = 0
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])

    def test_explicit_zero_lineup_change_remains_supported_recorded_evidence(self):
        for row in self.rows.values():
            row["comparison_offers"][0]["summary"]["lineup"].update(
                post_total=100, delta=0
            )
            row["actual_evaluations"][0]["lineup"].update(post_total=100, delta=0)
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])

    def test_missing_overall_verdict_and_partial_market_do_not_erase_supported_lineup(
        self,
    ):
        for row in self.rows.values():
            row["actual_evaluations"][0].update(
                recommendation=None,
                market={
                    "availability": "partial",
                    "sent": {"total": None},
                    "received": {"total": 104},
                },
            )
            row["comparison_offers"][0]["summary"]["neutral"].update(
                availability="partial", sent=None
            )
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])

    def test_recovery_uses_the_same_guard(self):
        for prefix in (
            "front-office-workflow/",
            "local-canonical/front-office-workflow/",
        ):
            with self.subTest(prefix=prefix):
                self.assertTrue(self.verify(prefix=prefix)["passed"])

    def test_foreign_or_dirty_source_and_claimed_live_scope_block(self):
        for key, value in [
            ("commit", "c" * 40),
            ("tree", "d" * 40),
            ("working_tree_clean", False),
            ("physical_safari_tested", True),
            ("source", "Live owner acceptance"),
        ]:
            with self.subTest(key=key):
                original = self.metadata[key]
                self.metadata[key] = value
                for prefix in self.PREFIXES:
                    with (
                        self.subTest(prefix=prefix),
                        self.assertRaisesRegex(
                            RuntimeError, "source mismatch|scope mismatch"
                        ),
                    ):
                        self.verify(prefix=prefix)
                self.metadata[key] = original

    def test_all_four_distinct_viewports_and_images_are_required(self):
        for name in ("home", "protection_views", "comparison_and_history"):
            with self.subTest(name=name):
                self.reject(lambda row, name=name: row[name].pop(), "viewport coverage")
                self.reject(
                    lambda row, name=name: row[name].__setitem__(
                        3, copy.deepcopy(row[name][0])
                    ),
                    "viewport coverage",
                )
        for prefix in self.PREFIXES:
            with self.subTest(prefix=prefix), self.assertRaises(KeyError):
                self.verify(prefix=prefix, omit="superflex-journey.png")

    def test_distinct_actual_league_configurations_are_required(self):
        self.reject(
            lambda row: row.update(league_slots=["QB", "SUPER_FLEX"]),
            "league configuration",
        )
        self.rows["superflex-journey"]["league_slots"] = ["QB", "RB", "K", "DEF"]
        for prefix in self.PREFIXES:
            with (
                self.subTest(prefix=prefix),
                self.assertRaisesRegex(RuntimeError, "league configuration"),
            ):
                self.verify(prefix=prefix)

    def test_missing_null_empty_or_malformed_pools_never_prove_exclusion(self):
        for pools in (
            None,
            [],
            {},
            "2029-R1-3",
            [None],
            [["b", "2029-R1-3"], []],
            [["2029-R1-3", None]],
            [["b", "2029-R1-3", "a"]],
            [["b", "2029-R1-3", "2029-R1-1"]],
            [["b"]],
        ):
            with self.subTest(pools=pools):
                self.reject(
                    lambda row, pools=pools: row.update(outgoing_pools=pools),
                    "construction isolation",
                )
        self.reject(lambda row: row.pop("outgoing_pools"), "construction isolation")

    def test_missing_native_population_and_leaked_or_promoted_offers_block(self):
        self.reject(
            lambda row: row.update(native_offers=None), "native offer population"
        )
        self.reject(lambda row: row.pop("native_offers"), "native offer population")
        self.reject(
            lambda row: row["native_offers"][0]["proposal"]["assets_sent"].append(
                "2029-R1-1"
            ),
            "escaped",
        )
        self.reject(
            lambda row: row["native_offers"][0].update(generated_trade_eligible=True),
            "qualification",
        )
        self.reject(
            lambda row: row["native_offers"][0].update(
                exploration=False, generated_trade_eligible=True
            ),
            "qualification",
        )

    def test_fingerprint_reason_and_editable_choice_are_bound(self):
        self.reject(
            lambda row: row["home"][0].update(action="Explore WR trades →"),
            "Home handoff",
        )
        self.reject(
            lambda row: row["handoff"].update(
                href="/trades/recommended?front_office=2&team_need=" + "f" * 64
            ),
            "fingerprint",
        )
        self.reject(
            lambda row: row["handoff"]["initial_choice"].update(fingerprint="e" * 64),
            "editable need",
        )
        self.reject(
            lambda row: row["handoff"]["edited_choice"].update(manual=False),
            "editable need",
        )
        self.reject(
            lambda row: row["handoff"].update(
                explanation="Unqualified roster weakness"
            ),
            "editable need",
        )

    def test_effective_and_prior_protections_cannot_be_relabelled(self):
        self.reject(
            lambda row: row["applied_constraints"].update(protected_assets=[]),
            "applied protection",
        )
        self.reject(
            lambda row: row["prior_search"].update(protections=[]), "prior applied"
        )
        self.reject(
            lambda row: row["prior_search"].update(position="WR"), "prior applied"
        )

    def test_extra_search_or_comparison_and_missing_replacement_requests_block(self):
        for path in ("/api/trades/generate", "/api/trades/compare"):
            with self.subTest(path=path):

                def change(row, path=path):
                    row["post_requests"].append(["POST", path, 200])
                    row["post_ledger"].append(
                        {"path": path, "status": 200, "payload": {}}
                    )

                self.reject(change, "POST ledger")
        self.reject(lambda row: row["post_ledger"].pop(), "POST ledger")

    def test_independent_evaluate_locks_and_authorized_scope_are_required(self):
        self.reject(
            lambda row: row["post_ledger"][1]["payload"].update(protected_assets=["a"]),
            "independent Evaluate",
        )
        self.reject(
            lambda row: row["post_ledger"][1]["payload"]["workspace_context"].update(
                binding="other-tab"
            ),
            "independent Evaluate",
        )
        self.reject(
            lambda row: row["generation_payload"]["workspace_context"].update(
                league_id="foreign-league"
            ),
            "generation scope",
        )

    def test_comparison_source_package_order_and_supported_numbers_are_required(self):
        self.reject(
            lambda row: row["comparison_offers"][0]["baseline"].update(projection=None),
            "source-qualified",
        )
        self.reject(
            lambda row: row["comparison_offers"][1]["baseline"].update(
                projection="other-source"
            ),
            "original lineup",
        )
        self.reject(
            lambda row: row["comparison_offers"][1]["proposal"][
                "assets_sent"
            ].reverse(),
            "package/order",
        )
        self.reject(
            lambda row: row["comparison_offers"][0]["identity"].update(package="null"),
            "package identity",
        )
        for delta in (None, float("nan"), 0):
            self.reject(
                lambda row, delta=delta: row["comparison_offers"][0]["summary"][
                    "lineup"
                ].update(delta=delta),
                "supported comparison",
            )
        self.reject(
            lambda row: row["comparison_offers"][0]["summary"]["neutral"].update(
                sent=999
            ),
            "Market values",
        )
        self.reject(
            lambda row: row["comparison_offers"][0]["summary"]["lineup"].update(
                post_total=105, delta=5
            ),
            "original lineup",
        )
        self.reject(
            lambda row: row["actual_evaluations"][0]["lineup"].update(
                projection_generation="foreign-source"
            ),
            "original lineup",
        )
        self.reject(
            lambda row: row["comparison_offers"][0]["summary"]["lineup"].update(
                projection_generation="foreign-source"
            ),
            "original lineup",
        )

    def test_history_reload_replacement_and_league_clearing_are_required(self):
        self.reject(
            lambda row: row["comparison_and_history"][0].update(
                history_return_without_post=False
            ),
            "comparison/history",
        )
        self.reject(
            lambda row: row["comparison_and_history"][0].update(
                history_qualification="current"
            ),
            "comparison/history",
        )
        self.reject(
            lambda row: row.update(reload_retained=False), "reload or replacement"
        )
        self.reject(
            lambda row: row["replacement"].update(remaining_proposals=[]),
            "reload or replacement",
        )
        self.reject(
            lambda row: row["scope_change"].update(old="foreign-binding"),
            "league clearing",
        )
        self.reject(
            lambda row: row["scope_change"].update(before_protections=[]),
            "league clearing",
        )
        self.reject(
            lambda row: row["scope_change"].update(before_position=""),
            "league clearing",
        )
        self.reject(
            lambda row: row.update(saved_goal_and_rankings_unchanged=False),
            "saved preferences",
        )


class DraftCapitalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40, "capital_tests": 14}
        self.files = {}
        for sf in ("False", "True"):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                name = "browser/offer-comparison/draft-capital-" + sf + "-" + str(width)
                captures = []
                for index in (0, 1):
                    body = {
                        "schema": 1,
                        "league": "league-1",
                        "roster": 1,
                        "complete": True,
                        "rounds": 4,
                        "seasons": [2028],
                        "before": [[2028, 1, 1], [2028, 1, 3]],
                        "generation": "c" * 64,
                        "sent": [[2028, 1, 3]] if index == 0 else [],
                        "received": [],
                    }
                    text = json.dumps(body)
                    captures.append({"characters": len(text), "parts": [text]})
                self.files[name + ".json"] = json.dumps(
                    {
                        "commit": self.plan["candidate"],
                        "tree": self.plan["tree"],
                        "working_tree_clean": True,
                        "physical_safari_tested": False,
                        "observations": {
                            "complete_recorded_inventories": 3,
                            "four_viewports": True,
                            "exact_originals": [1, 3],
                            "no_comparison_http": True,
                            "capital_records": captures,
                        },
                    }
                ).encode()
                self.files[name + ".png"] = (
                    b"\x89PNG\r\n\x1a\n"
                    + b"\0" * 8
                    + width.to_bytes(4, "big")
                    + height.to_bytes(4, "big")
                )

    def archive(self):
        path = self.root / "capital.zip"
        p.make_zip(path, self.files)
        return path

    def mutate(self, fn):
        key = "browser/offer-comparison/draft-capital-False-320.json"
        row = json.loads(self.files[key])
        fn(row)
        self.files[key] = json.dumps(row).encode()

    def test_complete_two_alternatives_at_both_league_shapes_and_four_sizes(self):
        self.assertEqual(
            len(p.verify_draft_capital(self.archive(), self.plan)["cases"]), 8
        )

    def test_foreign_source_is_rejected(self):
        self.mutate(lambda r: r.update(commit="f" * 40))
        with self.assertRaisesRegex(RuntimeError, "source mismatch"):
            p.verify_draft_capital(self.archive(), self.plan)

    def test_disclosure_requests_are_rejected(self):
        self.mutate(lambda r: r["observations"].update(no_comparison_http=False))
        with self.assertRaisesRegex(RuntimeError, "control failed"):
            p.verify_draft_capital(self.archive(), self.plan)

    def test_truncated_record_is_rejected(self):
        self.mutate(
            lambda r: r["observations"]["capital_records"][0].update(characters=1)
        )
        with self.assertRaisesRegex(RuntimeError, "Truncated"):
            p.verify_draft_capital(self.archive(), self.plan)

    def test_distinct_original_firsts_cannot_be_replaced_by_another_scope(self):
        def change(r):
            envelope = r["observations"]["capital_records"][0]
            row = json.loads("".join(envelope["parts"]))
            row["league"] = "another"
            text = json.dumps(row)
            envelope.update(characters=len(text), parts=[text])

        self.mutate(change)
        with self.assertRaisesRegex(RuntimeError, "scope"):
            p.verify_draft_capital(self.archive(), self.plan)

    def test_mismatched_phone_capture_is_rejected(self):
        name = "browser/offer-comparison/draft-capital-False-320.png"
        self.files[name] = (
            self.files[name][:16] + (390).to_bytes(4, "big") + self.files[name][20:]
        )
        with self.assertRaisesRegex(RuntimeError, "width"):
            p.verify_draft_capital(self.archive(), self.plan)

    def test_missing_alternative_is_rejected(self):
        self.mutate(lambda r: r["observations"]["capital_records"].pop())
        with self.assertRaisesRegex(RuntimeError, "Both"):
            p.verify_draft_capital(self.archive(), self.plan)

    def test_actual_regression_population_and_required_bound_case(self):
        names = [
            "test_trade_capital_inventory.CapitalInventoryTests.test_case_" + str(i)
            for i in range(13)
        ]
        names.append(
            "test_trade_capital_inventory.CapitalInventoryTests.test_bounded_record_keeps_supported_exchange_when_inventory_is_too_large"
        )
        rows = [
            {"event": event, "test": name}
            for name in names
            for event in ("start", "stop")
        ]
        path = self.root / "events.zip"
        p.make_zip(path, {"tests.jsonl": "\n".join(map(json.dumps, rows)).encode()})
        self.assertEqual(p.verify_capital_test_execution(path, self.plan), names)
        rows.pop()
        p.make_zip(path, {"tests.jsonl": "\n".join(map(json.dumps, rows)).encode()})
        with self.assertRaisesRegex(RuntimeError, "population"):
            p.verify_capital_test_execution(path, self.plan)


class RecoveryTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        folder = self.repo / ".github/release-plans"
        folder.mkdir(parents=True)
        archive = self.repo / "original.zip"
        p.make_zip(archive, {"fixture.txt": b"All original bytes retained."})
        raw = archive.read_bytes()
        pivot = len(raw) // 2
        self.plan = {
            "recovery_file": ".github/release-plans/2251-recovery.zip",
            "recovery_sha256": p.digest(archive),
            "recovery_parts": [],
        }
        for index, part in enumerate((raw[:pivot], raw[pivot:]), 1):
            path = (
                ".github/release-plans/2251-recovery-" + str(index).zfill(3) + ".part"
            )
            (self.repo / path).write_bytes(part)
            self.plan["recovery_parts"].append(
                {
                    "path": path,
                    "bytes": len(part),
                    "sha256": hashlib.sha256(part).hexdigest(),
                }
            )

    def materialize(self):
        return p.materialize_recovery(
            self.plan, self.repo / "output", repository=self.repo
        )

    def test_original_archive_bytes_are_reassembled_before_existing_guards(self):
        result = self.materialize()
        self.assertEqual(result.read_bytes(), (self.repo / "original.zip").read_bytes())

    def test_reversed_or_duplicate_parts_are_rejected(self):
        for rows in (
            list(reversed(self.plan["recovery_parts"])),
            [self.plan["recovery_parts"][0]] * 2,
        ):
            with self.assertRaisesRegex(RuntimeError, "unordered"):
                p.validate_recovery_parts(self.plan | {"recovery_parts": rows})

    def test_missing_part_is_rejected(self):
        (self.repo / self.plan["recovery_parts"][1]["path"]).unlink()
        with self.assertRaisesRegex(RuntimeError, "Missing"):
            self.materialize()

    def test_bad_part_bytes_are_rejected(self):
        (self.repo / self.plan["recovery_parts"][1]["path"]).write_bytes(b"wrong")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            self.materialize()

    def test_bad_full_archive_checksum_is_rejected(self):
        self.plan["recovery_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "Assembled"):
            self.materialize()

    def test_symlink_part_is_rejected(self):
        path = self.repo / self.plan["recovery_parts"][0]["path"]
        original = path.read_bytes()
        path.unlink()
        real = self.repo / "outside"
        real.write_bytes(original)
        path.symlink_to(real)
        with self.assertRaisesRegex(RuntimeError, "nonregular"):
            self.materialize()

    def test_path_traversal_is_rejected(self):
        self.plan["recovery_parts"][0]["path"] = "../elsewhere"
        with self.assertRaisesRegex(RuntimeError, "unordered"):
            self.materialize()

    def test_part_size_bound_and_existing_output_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "size"):
            p.validate_recovery_parts(
                self.plan
                | {
                    "recovery_parts": [
                        {
                            "path": ".github/release-plans/2251-recovery-001.part",
                            "bytes": 64 * 1024**2 + 1,
                            "sha256": "a" * 64,
                        }
                    ]
                }
            )
        self.materialize()
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            self.materialize()


class MarketRosterEvidenceGuards(unittest.TestCase):
    def setUp(self):
        import copy

        self.copy = copy.deepcopy
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "market.zip"
        self.plan = {"candidate": "a" * 40, "tree": "b" * 40, "market_roster_tests": 21}
        self.prefix = "browser/market-needs/"
        self.files = {}
        rows = []

        def put(name, observations):
            self.files[self.prefix + name + ".json"] = json.dumps(
                {
                    "commit": self.plan["candidate"],
                    "tree": self.plan["tree"],
                    "scope": "Disposable fixture; not owner live or physical Safari",
                    "observations": observations,
                }
            ).encode()

        for shape in ("oneqb-kdef", "superflex"):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                rows.append(
                    dict(
                        shape=shape,
                        viewport=[width, height],
                        **{
                            k: True
                            for k in (
                                "roundtrip",
                                "exact_asset",
                                "draft_preserved",
                                "protections_preserved",
                                "comparison_preserved",
                                "retained_result",
                                "no_extra_posts",
                                "no_solver_on_navigation",
                            )
                        },
                        errors=[],
                    )
                )
                stem = shape + "-" + str(width)
                put(
                    stem,
                    [
                        {
                            "viewport": [width, height],
                            "exact_target": "player:2-RB-0",
                            "neutral_movement": 150,
                            "keyboard_disclosure": True,
                            "touch_emulation": width < 1000,
                            "overflow": False,
                        }
                    ],
                )
                put("market-" + stem, [{"no_search": True}])
                for capture in (stem, "market-" + stem):
                    self.files[self.prefix + capture + ".png"] = (
                        b"\x89PNG\r\n\x1a\n"
                        + b"\0" * 8
                        + width.to_bytes(4, "big")
                        + height.to_bytes(4, "big")
                    )
        put("roundtrip", rows)
        put(
            "stale-and-league",
            [
                {
                    **{
                        k: True
                        for k in (
                            "stale_link_withheld",
                            "new_target_not_applied",
                            "existing_draft_preserved",
                            "league_switch_cleared_scope",
                            "no_posts",
                        )
                    },
                    "errors": [],
                }
            ],
        )

    def mutate(self, name, fn):
        key = self.prefix + name + ".json"
        row = json.loads(self.files[key])
        fn(row)
        self.files[key] = json.dumps(row).encode()

    def verify(self):
        p.make_zip(self.path, self.files)
        return p.verify_market_roster(self.path, self.plan)

    def test_complete_source_bound_roundtrip_required(self):
        self.assertEqual(self.verify()["cases"], 8)

    def test_wrong_source_rejected(self):
        self.mutate("roundtrip", lambda r: r.update(commit="c" * 40))
        with self.assertRaisesRegex(RuntimeError, "source"):
            self.verify()

    def test_partial_viewport_population_rejected(self):
        self.mutate("roundtrip", lambda r: r["observations"].pop())
        with self.assertRaisesRegex(RuntimeError, "coverage"):
            self.verify()

    def test_implicit_search_or_lost_state_rejected(self):
        self.mutate(
            "roundtrip", lambda r: r["observations"][0].update(no_extra_posts=False)
        )
        with self.assertRaisesRegex(RuntimeError, "no-work"):
            self.verify()

    def test_touch_and_keyboard_proof_required(self):
        self.mutate(
            "oneqb-kdef-320",
            lambda r: r["observations"][0].update(touch_emulation=False),
        )
        with self.assertRaisesRegex(RuntimeError, "accessibility"):
            self.verify()

    def test_missing_stale_protection_rejected(self):
        self.mutate(
            "stale-and-league", lambda r: r["observations"][0].update(no_posts=False)
        )
        with self.assertRaisesRegex(RuntimeError, "Stale"):
            self.verify()

    def test_mismatched_phone_capture_rejected(self):
        self.files[self.prefix + "market-oneqb-kdef-320.png"] = b"bad"
        with self.assertRaisesRegex(RuntimeError, "phone"):
            self.verify()


class MarketRosterTestPopulationGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tests.zip"
        self.names = [
            "tests.test_market_roster_relevance.Control.test_" + str(i)
            for i in range(21)
        ]
        self.rows = [
            {"event": event, "test": name}
            for name in self.names
            for event in ("start", "stop")
        ]

    def verify(self):
        p.make_zip(
            self.path,
            {"tests.jsonl": "\n".join(json.dumps(r) for r in self.rows).encode()},
        )
        return p.verify_market_roster_tests(self.path, {"market_roster_tests": 21})

    def test_complete_execution_population(self):
        self.assertEqual(self.verify(), self.names)

    def test_missing_completion_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(RuntimeError, "population"):
            self.verify()

    def test_duplicate_execution_rejected(self):
        self.rows.extend(self.rows[:2])
        with self.assertRaisesRegex(RuntimeError, "population"):
            self.verify()

    def test_unrelated_tests_do_not_fill_population(self):
        self.rows[-2:] = [
            {"event": e, "test": "unrelated.Control.test"} for e in ("start", "stop")
        ]
        with self.assertRaisesRegex(RuntimeError, "population"):
            self.verify()


class WorkflowPublisherWiringTests(unittest.TestCase):
    def test_manual_scoped_publisher_is_present_with_the_verified_plan(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/canonical-release-recovery.yml"
        ).read_text()
        self.assertEqual(workflow.count("\n  guarded-release-publisher:\n"), 1)
        block = workflow.split("\n  guarded-release-publisher:\n", 1)[1].split(
            "\n  publish-2191:\n", 1
        )[0]
        for required in [
            "if: github.event_name == 'workflow_dispatch'",
            'contains(fromJSON(\'["audit","prepare","publish"]\')',
            "timeout-minutes: 25",
            "contents: write",
            "checks: read",
            "pull-requests: read",
            "actions: read",
            "group: dtos-guarded-release-2251",
            "cancel-in-progress: false",
            "ref: ${{ github.sha }}",
            "persist-credentials: false",
            "python -m unittest -v tests.test_release_publisher",
            "GH_TOKEN: ${{ github.token }}",
            "PREPARATION_RUN_ID: ${{ inputs.preparation_run_id }}",
            "--plan .github/release-plans/2251.json",
            'arguments+=(--prepared-run "$PREPARATION_RUN_ID")',
            "name: guarded-release-2251-${{ inputs.release_operation }}-${{ github.run_id }}",
            "if-no-files-found: error",
        ]:
            with self.subTest(required=required):
                self.assertIn(required, block)
        self.assertNotIn("2247", block)


class RosterSourceScopePublicationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "source-scope.zip"
        self.plan = {
            "candidate": "a" * 40,
            "tree": "b" * 40,
            "roster_source_scope_tests": 20,
        }
        self.files = {}
        prefix = "browser/roster-source-scope/"
        for shape in ("oneqb-kdef", "sf"):
            for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                stem = prefix + shape + "-" + str(width)
                row = {
                    "commit": self.plan["candidate"],
                    "tree": self.plan["tree"],
                    "viewport": [width, height],
                    "exact_target": "player:2-RB-0",
                    "unrostered_missing_projection": True,
                    "my_team_supported": True,
                    "explicit_generate_required": True,
                    "keyboard": True,
                    "no_navigation_solver": True,
                    "touch_emulation": width < 1000,
                    "scope": "Disposable fixture, not owner live",
                    "working_tree_clean": True,
                }
                self.files[stem + ".json"] = json.dumps(row).encode()
                self.files[stem + ".png"] = b"\x89PNG\r\n\x1a\nfixture"
        for reason in (
            "unknown-k",
            "unknown-def",
            "eligible-missing",
            "aging",
            "failed-refresh",
        ):
            stem = prefix + reason
            self.files[stem + ".json"] = json.dumps(
                {
                    "commit": self.plan["candidate"],
                    "tree": self.plan["tree"],
                    "reason": reason,
                    "neutral_preserved": True,
                    "personalized_action_withheld": True,
                    "no_posts": True,
                    "working_tree_clean": True,
                }
            ).encode()
            self.files[stem + ".png"] = b"\x89PNG\r\n\x1a\nfixture"

    def verify(self):
        p.make_zip(self.path, self.files)
        return p.verify_roster_source_scope(self.path, self.plan)

    def change(self, suffix, **fields):
        name = "browser/roster-source-scope/" + suffix + ".json"
        row = json.loads(self.files[name])
        row.update(fields)
        self.files[name] = json.dumps(row).encode()

    def test_native_supported_and_withheld_controls_are_both_required(self):
        result = self.verify()
        self.assertEqual(result["supported_roundtrips"], 8)
        self.assertEqual(result["withheld_cases"], 5)
        self.assertTrue(result["passed"])

    def test_missing_image_cannot_be_replaced_by_a_summary(self):
        self.files.pop("browser/roster-source-scope/oneqb-kdef-320.png")
        with self.assertRaises((RuntimeError, KeyError)):
            self.verify()

    def test_foreign_source_is_rejected(self):
        self.change("sf-390", tree="c" * 40)
        with self.assertRaisesRegex(RuntimeError, "source mismatch"):
            self.verify()

    def test_automatic_generation_or_wrong_target_is_rejected(self):
        self.change("oneqb-kdef-320", explicit_generate_required=False)
        with self.assertRaisesRegex(RuntimeError, "journey incomplete"):
            self.verify()

    def test_genuine_uncertainty_cannot_be_promoted(self):
        self.change("unknown-def", personalized_action_withheld=False)
        with self.assertRaisesRegex(RuntimeError, "limitations were not preserved"):
            self.verify()

    def population(self, ids):
        rows = [
            {"event": event, "test": test}
            for test in ids
            for event in ("start", "stop")
        ]
        p.make_zip(
            self.path, {"tests.jsonl": "\n".join(map(json.dumps, rows)).encode()}
        )
        return p.verify_roster_source_scope_tests(self.path, self.plan)

    def test_exact_new_population_is_required(self):
        ids = [
            "tests.test_roster_source_scope.Control.test_" + str(i) for i in range(18)
        ]
        ids += [
            "tests.test_roster_source_scope_browser.Control.test_" + str(i)
            for i in range(2)
        ]
        self.assertEqual(self.population(ids), ids)
        with self.assertRaisesRegex(RuntimeError, "population incomplete"):
            self.population(ids[:-1])

    def test_duplicate_execution_does_not_replace_a_missing_case(self):
        ids = [
            "tests.test_roster_source_scope.Control.test_" + str(i) for i in range(19)
        ]
        with self.assertRaisesRegex(RuntimeError, "population incomplete"):
            self.population(ids + [ids[-1]])

    def test_plan_cannot_omit_the_new_population(self):
        with self.assertRaisesRegex(RuntimeError, "population missing"):
            p.verify_plan({"finalized": True})


class FranchiseProgressPublicationTests(unittest.TestCase):
    def test_actual_test_population_needs_completion_without_failure(self):
        for change in (None, "missing_stop", "duplicate", "failure", "plan"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                plan = {"franchise_progress_tests": 16}
                rows = [
                    {
                        "event": event,
                        "test": "tests.test_franchise_trade_progress.Control.test_"
                        + str(i),
                    }
                    for i in range(16)
                    for event in ("start", "stop")
                ]
                if change == "missing_stop":
                    rows.pop()
                if change == "duplicate":
                    rows += rows[:2]
                if change == "failure":
                    rows.append({"event": "failure", "test": rows[0]["test"]})
                if change == "plan":
                    plan["franchise_progress_tests"] = 15
                path = Path(folder) / "tests.zip"
                p.make_zip(
                    path,
                    {"tests.jsonl": b"\n".join(json.dumps(r).encode() for r in rows)},
                )
                if change:
                    with self.assertRaises(RuntimeError):
                        p.verify_franchise_progress_tests(path, plan)
                else:
                    self.assertEqual(
                        len(p.verify_franchise_progress_tests(path, plan)), 16
                    )

    def test_phone_journey_requires_period_and_conversion_return(self):
        for change in (None, "period", "conversion", "gross", "unknown"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                plan, phone, _ = CompletedTradePublisherTests().fixture()
                for row in phone["records"]:
                    known = row["control"].startswith("Day retained")
                    row.update(
                        season_filter=2026 if known else None,
                        filtered_pagination_conversion_return=known,
                        gross_player_transfers=[1, 3] if known else None,
                        gross_pick_transfers=[5, 2] if known else None,
                    )
                if change == "period":
                    phone["records"][0]["season_filter"] = 2025
                if change == "conversion":
                    phone["records"][0]["filtered_pagination_conversion_return"] = False
                if change == "gross":
                    phone["records"][0]["gross_player_transfers"] = [1, 1]
                if change == "unknown":
                    phone["records"][-1]["gross_player_transfers"] = [0, 0]
                files = {"feature/browser.json": json.dumps(phone).encode()}
                files.update(
                    {
                        "feature/control-" + str(i) + ".png": b"\x89PNG\r\n\x1a\n"
                        for i in range(8)
                    }
                )
                path = Path(folder) / "phone.zip"
                p.make_zip(path, files)
                if change:
                    with self.assertRaises(RuntimeError):
                        p.verify_franchise_progress_browser(
                            path, plan, prefix="feature/"
                        )
                else:
                    self.assertTrue(
                        p.verify_franchise_progress_browser(
                            path, plan, prefix="feature/"
                        )["passed"]
                    )

    def test_partial_unknown_and_conversion_boundaries_cannot_be_promoted(self):
        for change in (
            None,
            "gross",
            "net",
            "unknown",
            "partial",
            "player",
            "conversion",
            "bound",
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                plan, _, feature = CompletedTradePublisherTests().fixture()
                rows = {c["case"]: c["summary"] for c in feature["cases"]}
                rows["retained_day"].update(
                    movements={
                        "player": {
                            "acquired": 1,
                            "sent": 3,
                            "net": -2,
                            "complete_in_sample": True,
                        },
                        "pick": {
                            "acquired": 5,
                            "sent": 2,
                            "net": 3,
                            "complete_in_sample": True,
                        },
                    },
                    assets=[
                        {
                            "kind": "player",
                            "id": "13346",
                            "acquired": 0,
                            "sent": 1,
                            "references": [],
                        }
                    ],
                )
                rows["unknown"].update(
                    assets=[],
                    movements={
                        k: {"acquired": None, "sent": None, "net": None}
                        for k in ("player", "pick")
                    },
                )
                rows["partial_pick"]["movements"] = {
                    "pick": {"net": None, "complete_in_sample": False},
                    "player": {"complete_in_sample": True},
                }
                if change == "gross":
                    rows["retained_day"]["movements"]["player"]["sent"] = 2
                if change == "net":
                    rows["retained_day"]["movements"]["pick"]["net"] = 5
                if change == "unknown":
                    rows["unknown"]["movements"]["pick"]["net"] = 0
                if change == "partial":
                    rows["partial_pick"]["movements"]["pick"]["net"] = 0
                if change == "player":
                    rows["partial_pick"]["movements"]["player"][
                        "complete_in_sample"
                    ] = False
                if change == "conversion":
                    rows["retained_day"]["assets"][0]["acquired"] = 1
                if change == "bound":
                    rows["retained_day"]["assets"][0]["references"] = [{}] * 5
                path = Path(folder) / "cases.zip"
                p.make_zip(path, {"feature/feature.json": json.dumps(feature).encode()})
                if change:
                    with self.assertRaises(RuntimeError):
                        p.verify_franchise_progress_cases(path, plan)
                else:
                    self.assertTrue(
                        p.verify_franchise_progress_cases(path, plan)["passed"]
                    )


class AcquisitionPublicationTests(unittest.TestCase):
    def test_twenty_exact_completed_controls_required(self):
        ids = [
            "test_trade_for_acquisition.AcquisitionSelectionTests.case" + str(i)
            for i in range(18)
        ]
        ids += [
            "test_trade_for_acquisition_integration.AcquisitionIntegrationTests.test_actual_bounded_search_control",
            "test_trade_for_acquisition_browser.AcquisitionBrowserTests.test_cost_fit_preview_control",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "canonical.zip"
            rows = [{"event": e, "test": i} for i in ids for e in ("start", "stop")]
            for fault in (
                "none",
                "unfinished",
                "duplicate",
                "failure",
                "skip",
                "wrong_prefix",
            ):
                selected = copy.deepcopy(rows)
                if fault == "unfinished":
                    selected.pop()
                elif fault == "duplicate":
                    selected[-2]["test"] = ids[0]
                elif fault in ("failure", "skip"):
                    selected.append({"event": fault, "test": ids[0]})
                elif fault == "wrong_prefix":
                    selected = [
                        {
                            **r,
                            "test": r["test"].replace(
                                "test_trade_for_acquisition", "unrelated"
                            ),
                        }
                        for r in selected
                    ]
                p.make_zip(
                    path,
                    {
                        "tests.jsonl": "\n".join(
                            json.dumps(r) for r in selected
                        ).encode()
                    },
                )
                if fault == "none":
                    self.assertEqual(
                        len(
                            p.verify_acquisition_tests(path, {"acquisition_tests": 20})
                        ),
                        20,
                    )
                else:
                    with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                        p.verify_acquisition_tests(path, {"acquisition_tests": 20})

    def test_acquisition_controls_cannot_be_omitted_from_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "canonical.zip"
            p.make_zip(path, {"tests.jsonl": b""})
            with self.assertRaises(RuntimeError):
                p.verify_acquisition_tests(path, {})

    def test_recovery_requires_exact_source_completed_resources_and_phone_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recovery.zip"
            for report in (
                {},
                {"commit": "a" * 40, "tree": "b" * 40, "dirty": [], "passed": False},
            ):
                p.make_zip(
                    path, {"focused-exact/result.json": json.dumps(report).encode()}
                )
                with self.assertRaises((RuntimeError, KeyError)):
                    p.verify_acquisition_recovery(
                        path, {"candidate": "a" * 40, "tree": "b" * 40}
                    )


class NormalExecutionRecoveryTests(unittest.TestCase):
    def test_all_ten_real_normal_execution_controls_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "canonical.zip"
            rows = [
                {"event": event, "test": name}
                for name in p.NORMAL_EXECUTION_TESTS
                for event in ("start", "stop")
            ]
            p.make_zip(path, {"tests.jsonl": "\n".join(map(json.dumps, rows)).encode()})
            self.assertEqual(
                p.verify_normal_execution_tests(path, {"fixture_isolation_tests": 10}),
                sorted(p.NORMAL_EXECUTION_TESTS),
            )

    def test_missing_duplicate_or_failed_execution_cannot_be_promoted(self):
        for fault in ("missing", "duplicate", "error", "skip"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                rows = [
                    {"event": event, "test": name}
                    for name in p.NORMAL_EXECUTION_TESTS
                    for event in ("start", "stop")
                ]
                if fault == "missing":
                    rows.pop()
                elif fault == "duplicate":
                    rows.append(dict(rows[-1]))
                else:
                    rows.append({"event": fault, "test": p.NORMAL_EXECUTION_TESTS[-1]})
                path = Path(folder) / "canonical.zip"
                p.make_zip(
                    path, {"tests.jsonl": "\n".join(map(json.dumps, rows)).encode()}
                )
                with self.assertRaises(RuntimeError):
                    p.verify_normal_execution_tests(
                        path, {"fixture_isolation_tests": 10}
                    )

    def test_normal_execution_population_cannot_be_omitted_from_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "canonical.zip"
            p.make_zip(path, {"tests.jsonl": b""})
            with self.assertRaisesRegex(RuntimeError, "population"):
                p.verify_normal_execution_tests(path, {})


class PriorPartIntegrityTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        payload = root / "original.zip"
        p.make_zip(
            payload,
            {"original.log": b"Original prior attempt, never a passing current gate."},
        )
        raw = payload.read_bytes()
        plan = {
            "prior_evidence_file": ".github/release-plans/2251-prior.zip",
            "prior_evidence_sha256": hashlib.sha256(raw).hexdigest(),
            "prior_evidence_parts": [],
        }
        for i, data in enumerate((raw[: len(raw) // 2], raw[len(raw) // 2 :]), 1):
            name = ".github/release-plans/2251-prior-" + str(i).zfill(3) + ".part"
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            plan["prior_evidence_parts"].append(
                {
                    "path": name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        return root, payload, plan

    def test_prior_parts_reassemble_original_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, original, plan = self.fixture(folder)
            actual = p.materialize_prior_evidence(plan, root / "output", root)
            self.assertEqual(actual.read_bytes(), original.read_bytes())
            self.assertNotEqual(actual, original)

    def test_missing_tampered_reordered_and_wrong_full_checksum_fail_closed(self):
        for fault in ("missing", "tampered", "reordered", "whole-checksum"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                root, _, plan = self.fixture(folder)
                target = root / plan["prior_evidence_parts"][0]["path"]
                if fault == "missing":
                    target.unlink()
                elif fault == "tampered":
                    target.write_bytes(b"changed")
                elif fault == "reordered":
                    plan["prior_evidence_parts"].reverse()
                else:
                    plan["prior_evidence_sha256"] = "0" * 64
                with self.assertRaises(RuntimeError):
                    p.materialize_prior_evidence(plan, root / "output", root)

    def test_prior_family_preserves_path_size_checksum_and_population_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, plan = self.fixture(folder)
            for fault in ("path", "size", "checksum", "population", "family"):
                changed = copy.deepcopy(plan)
                if fault == "path":
                    changed["prior_evidence_parts"][0]["path"] = "../secret"
                elif fault == "size":
                    changed["prior_evidence_parts"][0]["bytes"] = 64 * 1024**2 + 1
                elif fault == "checksum":
                    changed["prior_evidence_parts"][0]["sha256"] = "bad"
                elif fault == "population":
                    changed["prior_evidence_parts"] *= 3
                with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                    p.validate_recovery_parts(
                        changed, family="unknown" if fault == "family" else "prior"
                    )

    def test_declared_missing_parts_cannot_fall_back_to_a_legacy_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root, original, plan = self.fixture(folder)
            target = root / plan["prior_evidence_file"]
            target.write_bytes(original.read_bytes())
            plan["prior_evidence_parts"] = []
            with self.assertRaises(RuntimeError):
                p.materialize_prior_evidence(plan, root / "output", root)
