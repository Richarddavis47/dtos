"""Source-fingerprinted disposable controls under enforced container limits."""
import os
from pathlib import Path
import sys
import json
import subprocess
import unittest
from datetime import datetime, timezone
root = Path('/tmp/relevance-focused')
root.mkdir()
for key, name in {'CACHE':'cache.json','PROJECTION_DB':'projections.sqlite3','METADATA_DB':'metadata.sqlite3','INTELLIGENCE_CHECKPOINT':'intelligence.sqlite3','FOIS_DB':'fois.sqlite3','HISTORY_DB':'history.sqlite3','ACCOUNT_DB':'accounts.sqlite3'}.items():
    os.environ['DTOS_'+key+'_FILE'] = str(root/name)
os.environ.update(DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_FIXTURE_ROOT=str(root),DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'),DTOS_HISTORY_STORAGE_ROOT=str(root))
sys.path.insert(0,'/app')
suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
result = unittest.TextTestRunner(verbosity=2).run(suite)
cg=Path('/sys/fs/cgroup')
report=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),dirty=subprocess.check_output(['git','status','--porcelain'],text=True).splitlines(),observed_at=datetime.now(timezone.utc).isoformat(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),memory_limit=int((cg/'memory.max').read_text()),peak=int((cg/'memory.peak').read_text()),events=dict(line.split() for line in (cg/'memory.events').read_text().splitlines()))
Path('/output/result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
raise SystemExit(not report['passed'])
