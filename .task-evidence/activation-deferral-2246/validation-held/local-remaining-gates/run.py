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
    PYTHONPATH="/output/observer:/app")

sys.path.insert(0,str(ROOT))
os.environ['DTOS_VALIDATION_RUN_ID']='2246-remaining-gates-c85458d20e7545e3b01e0e3ddde8ee91'
from src.platform.validation.release import default_steps
from src.platform.lifecycle import memory_snapshot
results=[]
for step in default_steps()[7:]:
 command=list(step.command)
 if step.name=='Process cleanup':command+=['--validation-run-id',os.environ['DTOS_VALIDATION_RUN_ID']]
 path=OUTPUT/(str(len(results)+1)+'.log')
 start=time.monotonic()
 with path.open('w') as f:r=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(name=step.name,command=command,exit_code=r.returncode,elapsed_seconds=time.monotonic()-start,log=path.name))
 print(step.name,r.returncode,flush=True)
 if r.returncode:break
proof=dict(candidate=os.environ['DTOS_EXPECTED_HEAD'],memory=memory_snapshot(),gates=results,passed=len(results)==3 and all(x['exit_code']==0 for x in results),scope='Only the three unchanged canonical commands not executed after failed unit gate. This does not turn the failed full canonical invocation into a pass.')
(OUTPUT/'result.json').write_text(json.dumps(proof,indent=2)+'\n')
sys.exit(not proof['passed'])
