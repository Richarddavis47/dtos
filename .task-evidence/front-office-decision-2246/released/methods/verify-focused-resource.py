"""Verify extracted final-source captures and fresh local native controls before packaging."""
import json
import tempfile
from pathlib import Path

from common import BASE, digest, load_source, write_json
from release_common import native_plan, publisher

source = load_source()
guard = publisher()
plan = native_plan()
resources = json.loads((BASE / "resource-preservation-verified.json").read_text())
assert resources["source"] == source and resources["all_native_guards_passed"]
extraction = json.loads((BASE / "capture-extraction.json").read_text())
assert extraction["candidate"] == source["candidate"] and extraction["tree"] == source["tree"] and extraction["source_bound_native_originals"]
for capture in extraction["captures"]:
    root = BASE / capture["destination"]
    expected = {row["name"] for row in capture["members"]}
    assert {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()} == expected
    for row in capture["members"]:
        path = root / row["name"]
        assert path.stat().st_size == row["bytes"] and digest(path) == row["sha256"], "Extracted original capture changed"
files = {}
for folder in ("partner-history", "team-need", "offer-comparison", "protections", "activation", "front-office-workflow"):
    for path in (BASE / folder).rglob("*"):
        if path.is_file():
            files[folder + "/" + str(path.relative_to(BASE / folder))] = path.read_bytes()
# The retained-case probe must be freshly run on final source separately, never relabeled from old source.
files["feature/feature.json"] = (BASE / "retained-history-feature.json").read_bytes()
files["feature/browser.json"] = (BASE / "history-browser/browser.json").read_bytes()
for path in (BASE / "history-browser").glob("*.png"):
    files["feature/" + path.name] = path.read_bytes()
checks = [
    ("partner_history", guard.verify_partner_history_links, "partner-history/"),
    ("team_need", guard.verify_team_need_handoff, "team-need/"),
    ("offer_comparison", guard.verify_offer_comparison, "offer-comparison/"),
    ("protections", guard.verify_recommended_protections, "protections/"),
    ("activation", guard.verify_activation_deferral, "activation/"),
    ("front_office_workflow", guard.verify_front_office_workflow, "front-office-workflow/"),
    ("history", guard.verify_completed_trade_browser, "feature/"),
]
results = {}
with tempfile.TemporaryDirectory() as temporary:
    archive = Path(temporary) / "captures.zip"
    guard.make_zip(archive, files)
    for name, verify, prefix in checks:
        results[name] = verify(archive, plan, prefix=prefix)
        assert results[name]["passed"]
    results["history_cases"] = guard.verify_completed_trade_cases(archive, plan)
    assert results["history_cases"]["passed"]
write_json(BASE / "focused-resource-verified.json", dict(candidate=source["candidate"], tree=source["tree"],
    all_native_guards_passed=True, resources=resources["native_results"], captures=results,
    scope="Fresh final-source native captures and local resource controls; full local/hosted canonical remain separately mandatory. Retained inputs are fixture replay; owner live/Safari acceptance remains separate."))
print("Final-source native focused/resource guards passed.")

