"""Apply every existing and integrated front-office native guard to final-source archives."""
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

from common import BASE, digest, load_source, write_json

sys.dont_write_bytecode = True
publisher_path = Path("/workspace/dtos-publisher-2249/tools/release/publish.py")
spec = importlib.util.spec_from_file_location("final_readonly_native_guard", publisher_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
source = load_source()
host = json.loads((BASE / "host-canonical-verified.json").read_text())
assert host["candidate"] == source["candidate"] and host["tree"] == source["tree"] and host["all_gates_passed"]
plan = dict(source, canonical_tests=source["expected_test_count"], canonical_entries=host["entries"], python_version="3.14.3", capital_tests=14, market_roster_tests=21, roster_source_scope_tests=20)
front_office_guard = getattr(guard, "verify_front_office_workflow", None)
assert callable(front_office_guard), "Agreed front-office publisher verifier is required; never skip new acceptance"
queue = json.loads((BASE / "artifact-download-queue.json").read_text())
assert len(queue) == 15
checks = {
    "actuals-restoration-original.zip": guard.verify_actuals_restoration,
    "restoration-unused-original.zip": guard.verify_restoration_unused,
    "resident-refresh-original.zip": guard.verify_resident_refresh,
    "trade-resource-original.zip": guard.verify_trade_resource,
    "league-entry-original.zip": guard.verify_league_entry,
    "preflight-original.zip": guard.verify_preflight,
    "current-history-original.zip": guard.verify_current_history,
    "current-production-coverage-original.zip": guard.verify_current_production,
    "market-history-coverage-original.zip": guard.verify_market_history,
    "history-followthrough-original.zip": guard.verify_history_followthrough,
}
rows = []
for item in queue:
    path = BASE / "hosted-originals" / item["file"]
    assert path.stat().st_size == item["bytes"] and digest(path) == item["sha256"]
    guard.verify_zip(path)
    if item["file"] in checks:
        checks[item["file"]](path, plan)
    if item["file"] == "canonical-original.zip":
        guard.verify_canonical(path, plan)
        guard.verify_capital_test_execution(path, plan)
        guard.verify_market_roster_tests(path, plan)
        guard.verify_roster_source_scope_tests(path, plan)
    if item["file"] == "trade-resource-original.zip":
        guard.verify_team_need_handoff(path, plan)
        guard.verify_offer_comparison(path, plan)
        guard.verify_recommended_protections(path, plan)
        guard.verify_activation_deferral(path, plan)
        front_office_guard(path, plan, prefix="browser/front-office-workflow/")
        guard.verify_draft_capital(path, plan)
        guard.verify_market_roster(path, plan)
        guard.verify_roster_source_scope(path, plan)
    if item["file"] == "history-followthrough-original.zip":
        guard.verify_completed_trade_browser(path, plan)
    if item["file"] == "public-welcome-security.zip":
        guard.verify_partner_history_links(path, plan)
    if item["file"].startswith("lifecycle-"):
        with zipfile.ZipFile(path) as archive:
            result = json.loads(archive.read("summary.json"))
        assert result["passed"] and result["completed"] and result["exit_code"] == 0 and result["memory_max"] == 2147483648
    rows.append(dict(item, original_bytes_verified=True, specialized_guards_verified=True))
write_json(BASE / "hosted-artifacts-verified.json", dict(candidate=source["candidate"], tree=source["tree"], passed=True, originals=rows,
    publisher_guard_file=str(publisher_path), publisher_guard_sha256=digest(publisher_path)))
print("All fifteen fresh source-bound original archives and native guards passed.")

