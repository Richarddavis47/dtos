"""Run the unchanged canonical validator in an enforced disposable cgroup."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

import psutil

ROOT = Path("/app")
OUTPUT = Path("/output")
FIXTURE = Path("/fixture")
OUTPUT.mkdir(exist_ok=True)
FIXTURE.mkdir(exist_ok=True)
os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=256")
for key, name in {"CACHE":"cache.json", "PROJECTION_DB":"projections.sqlite3",
                  "METADATA_DB":"metadata.sqlite3", "INTELLIGENCE_CHECKPOINT":"intelligence.sqlite3",
                  "FOIS_DB":"fois.sqlite3", "HISTORY_DB":"retired.sqlite3",
                  "ACCOUNT_DB":"accounts.sqlite3"}.items():
    os.environ["DTOS_" + key + "_FILE"] = str(FIXTURE / name)
os.environ.update(
    DTOS_DURABLE_HISTORY_REQUIRED="0", SLEEPER_BASE_URL="http://127.0.0.1:9/v1",
    SLEEPER_LEAGUE_ID="1804000000000000000", DTOS_FIXTURE_ROOT="/fixture",
    DTOS_SLEEPER_SEASON_CACHE_ROOT="/fixture/sleeper-season-cache",
    DTOS_HISTORY_STORAGE_ROOT="/fixture", DTOS_ATTRIBUTION_TEST_LOG="/output/tests.jsonl",
    DTOS_PLAIN_ENGLISH_EVIDENCE="/output/plain-browser",
    DTOS_PREMIUM_EVIDENCE="/output/premium-browser",
    DTOS_OUTLOOK_EVIDENCE="/output/outlook-browser",
    DTOS_BRIEF_EVIDENCE="/output/home-browser",
    DTOS_TREND_BROWSER_EVIDENCE="/output/market-browser.json",
    DTOS_MANAGER_EVIDENCE="/output/manager-browser",
    DTOS_PERSONAL_AVAILABILITY_EVIDENCE="/output/personal-browser",
    DTOS_PERSONAL_RECOVERY_EVIDENCE="/output/personal-recovery",
    DTOS_PHASE2_EVIDENCE="/output/source-screen",
    DTOS_PERSONAL_PARTIAL_EVIDENCE="/output/custom-partial",
    DTOS_RELATIVE_EVIDENCE="/output/relative-custom",
    DTOS_DECISION_HISTORY_EVIDENCE="/output/decision-history",
    DTOS_PROJECTION_COVERAGE_EVIDENCE="/output/projection-coverage",
    DTOS_LINEUP_REVIEW_EVIDENCE="/output/lineup-review",
    DTOS_TRADE_WORKFLOW_EVIDENCE="/output/trade-workflow",
    DTOS_TRADE_PICKER_EVIDENCE="/output/trade-picker",
    DTOS_MARKET_PREPARATION_EVIDENCE="/output/market-preparation",
    DTOS_CUSTOMER_CLARITY_EVIDENCE="/output/customer-clarity",
    DTOS_CUSTOM_READINESS_EVIDENCE="/output/custom-readiness",
    DTOS_REBUILD_DISCOVERY_EVIDENCE="/output/rebuild-discovery",
    DTOS_REBUILD_SPACE_EVIDENCE="/output/rebuild-space",
    DTOS_TRADE_RESPONSE_EVIDENCE="/output/trade-response",
    DTOS_CONDITIONAL_EVIDENCE="/output/conditional-trades",
    DTOS_STRATEGY_STATE_EVIDENCE="/output/strategy-state",
    DTOS_CONTEXTUAL_BACK_EVIDENCE="/output/contextual-back",
    DTOS_FOIS_BROWSER_EVIDENCE="/output/fois-browser.json",
    DTOS_PREPARATION_BROWSER_EVIDENCE="/output/preparation-browser.json",
    DTOS_ACTIVATION_EVIDENCE="/output/activation",
    DTOS_FRONT_OFFICE_WORKFLOW_EVIDENCE="/output/front-office-workflow",
    PYTHONPATH="/output/observer:/app")

sys.path.insert(0,str(ROOT))
os.environ.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0='/app')
import unittest
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
assert head=='4cf524c488efb36c77defd78bfd7acf84a3f6ddd' and tree=='79fe9268fb3394604559bbcbe1119616a080b71b'
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
suite=unittest.defaultTestLoader.discover('tests');expected=suite.countTestCases()
(OUTPUT/'expected-tests.json').write_text(json.dumps(dict(candidate=head,tree=tree,expected_test_count=expected,method='Pinned Python3.14.3 official unittest discovery on exact clean final source; counts only, not execution acceptance.'))+'\n')
names=['tests.test_account_activation_deferral','tests.test_recommended_protections_browser.RecommendedProtectionBrowserTests.test_exact_pick_player_and_phone_search_preserve_other_same_round_pick','tests.test_projection_audit','tests.test_front_office_brief','tests.test_front_office_brief_http','tests.test_front_office_brief_browser','tests.test_front_office_workflow_browser','tests.test_offer_comparison','tests.test_recommended_protections_browser.RecommendedProtectionBrowserTests.test_evaluate_draft_comparison_return_and_league_isolation','tests.test_offer_comparison_browser.OfferComparisonBrowserTests.test_phone_two_real_evaluations_keep_packages_costs_and_exact_draft']
from src.platform.lifecycle import memory_snapshot
started=time.time();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
proof=dict(candidate=head,tree=tree,expected_test_count=expected,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),passed=result.wasSuccessful(),started_at=started,elapsed_seconds=time.time()-started,memory=memory_snapshot(),scope='Exact clean combined candidate focused controls; all test modules loaded first. No full-local gate substitution. Native captures retained separately.')
(OUTPUT/'result.json').write_text(json.dumps(proof,indent=2)+'\n');sys.exit(not result.wasSuccessful())
