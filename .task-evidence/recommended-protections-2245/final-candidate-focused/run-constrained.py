from pathlib import Path
import subprocess,sys,os
source=os.environ.get('DTOS_TEST_SOURCE','/workspace/dtos-2245')
args=['docker','run','--rm','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','--env','HOME=/tmp','--env','NODE_OPTIONS=--max-old-space-size=256','--env','GIT_CONFIG_COUNT=1','--env','GIT_CONFIG_KEY_0=safe.directory','--env','GIT_CONFIG_VALUE_0=/app','--volume',source+':/app:ro','--volume','/workspace/dtos/.git:/workspace/dtos/.git:ro','--volume','/workspace/2245-recommended-protections:/evidence','--workdir','/app']
for name in ['DTOS_PROTECTIONS_EVIDENCE','DTOS_EXPECTED_HEAD','DTOS_COMPARE_EVIDENCE','DTOS_TEAM_NEED_EVIDENCE','DTOS_PARTNER_HISTORY_EVIDENCE','DTOS_COMPLETED_TRADE_OBSERVATIONS_EVIDENCE']:
 if name in os.environ:args += ['--env',name+'='+os.environ[name]]
prior=Path('/workspace/2244-trade-comparison/recovered-originals/local-restoration-unused/prior-study.zip')
if prior.exists():args += ['--volume',str(prior)+':/prior/Granite-cache-restoration-memory-profile.zip:ro']
args += ['dtos-canonical314:2245','python',*sys.argv[1:]]
raise SystemExit(subprocess.run(args).returncode)
