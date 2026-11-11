"""Seal complete final-source native proof locally; never write publisher files."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import zipfile

from common import BASE, digest, load_source, verify_worker_setup_controls, write_json
from release_common import passing_inputs, publisher, verify_release_inputs
from worker_evidence import collect_worker_setup_evidence

source, local, host, native, focused = passing_inputs()
verify_release_inputs()
worker_setup_controls = verify_worker_setup_controls(source)
assert json.loads((BASE / 'worker-setup-verified.json').read_bytes()) == worker_setup_controls
assert json.loads((BASE / 'focused-ready.json').read_bytes())['worker_setup_controls'] == worker_setup_controls
guard = publisher()
target = BASE / "recovery-package.zip"
assert not target.exists(), "Preserve the existing package; do not overwrite"
files = {}
worker_payloads = collect_worker_setup_evidence(worker_setup_controls)
for name, raw in worker_payloads.items():
    files['worker-setup-controls/' + name] = raw
for folder in ("local-canonical", "local-preflight", "local-restoration-unused", "local-resident-refresh",
               "partner-history", "team-need", "protections", "offer-comparison"):
    root = BASE / folder
    assert root.is_dir(), folder
    for path in root.rglob("*"):
        if path.is_file():
            # Canonical manifest payloads are never filtered, including any recorded bytecode.
            if folder != "local-canonical" and "__pycache__" in path.parts:
                continue
            files[folder + "/" + str(path.relative_to(root))] = path
files["feature/browser.json"] = BASE / "history-browser/browser.json"
files["feature/feature.json"] = BASE / "retained-history-feature.json"
for path in (BASE / "history-browser").glob("*.png"):
    files["feature/" + path.name] = path
required = [
    "REPORT.md", "SCOUT_HANDOFF.md", "PRIOR_ATTEMPTS.md", "CAPACITY_OPTIONS.md", "source.json", "candidate.patch", "release-inputs.json",
    "local-verified.json", "host-canonical-verified.json", "hosted-artifacts-verified.json", "hosted-final-records.json",
    "artifact-download-queue.json", "validation-runs.json", "capture-extraction.json", "focused-resource-verified.json",
    "resource-preservation-verified.json", "resource-inputs.json", "resource-invocation.json", "resource-native-guards.json",
    "product-test-counts.json", "public-welcome-test-counts.json", "canonical-invocation.json", "local-container-cleanup.json",
    "local-container-state-original.json", "local-container-stdout-original.log", "local-canonical-integrity-original.log",
    "retained-history-probe-original.log", "retained-history-probe-invocation.json", "prior-package.json",
    "resource-methods.md", "README.md", "harness-origins.json", "worker-setup-verified.json",
    "prior-url-scan-false-positive.json", "fixture-url-controls-v5-final.json", "fixture-url-logged-matches-v5.json",
    "fixture-url-classifier-revision-v5.json", "fixture-url-classifier-changes-v5.patch", "prior-package-original.log",
]
for name in required:
    path = BASE / name
    assert path.is_file(), "Missing required final packaging input: " + name
    files[name] = path
for path in BASE.glob("*.py"):
    files["methods/" + path.name] = path
for name in ('prior-b602-additions.py', 'build-released-evidence.py'):
    files['methods/history/prior-fixture-url-scan-before/' + name] = BASE / 'method-revisions/pre-fixture-url-classifier' / name
for name in ("methods-manifest.json", "SHA256SUMS"):
    if (BASE / name).exists():
        files["methods/" + name] = BASE / name
# Validate every original canonical manifest member is present verbatim in the package map.
manifest = json.loads((BASE / "local-canonical/manifest.json").read_text())
for row in manifest:
    path = files["local-canonical/" + row["name"]]
    assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"]
guard.verify_handoff((BASE / "SCOUT_HANDOFF.md").read_bytes(), source)
secret = re.compile(rb"(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
rows = []
with zipfile.ZipFile(target, "x", zipfile.ZIP_LZMA) as archive:
    for name, value in sorted(files.items()):
        member = PurePosixPath(name)
        if isinstance(value, bytes):
            assert name.startswith('worker-setup-controls/')
            assert name.removeprefix('worker-setup-controls/') in worker_payloads
            raw = value
        else:
            path = value
            assert path.is_file() and not path.is_symlink() and path.is_relative_to(BASE)
            assert 'private' not in path.relative_to(BASE).parts
            raw = path.read_bytes()
        assert not member.is_absolute() and ".." not in member.parts
        assert not secret.search(raw), name
        archive.writestr(name, raw)
        rows.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    archive.writestr("recovery-manifest.json", json.dumps(dict(candidate=source["candidate"], tree=source["tree"],
        scope="Final-source proof; activation and front-office workflow captures use complete local-canonical native families. Independently produced hosted originals remain separate required release assets; no local/host byte-identity claim. Historical failures remain separate linked original evidence in Prior-attempts.", files=rows), indent=2) + "\n")
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
assert target.stat().st_size < 100 * 1024**2, "Preserve all mandatory proof; resolve packaging without dropping originals"
write_json(BASE / "recovery-package.json", dict(candidate=source["candidate"], tree=source["tree"],
    file=target.name, files=len(rows) + 1, bytes=target.stat().st_size, sha256=digest(target),
    canonical_manifest_entries_preserved=len(manifest), private_production_reports_excluded=True,
    scope="All complete final local canonical manifest payloads, including activation and front-office workflow families, plus selected final-source native captures/resources and original consoles. Redundant standalone hosted copies of these two families are omitted only from Recovery. Fifteen independently produced hosted native archives remain required separate unchanged attachments; no local/host byte-identity or final-size claim."))
print("Sealed final-source Recovery locally; no controller files changed.")

