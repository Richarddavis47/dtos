"""Final-source controls; original console and measured cgroup retained."""
import json,subprocess,hashlib
from pathlib import Path
B=Path(__file__).resolve().parent;S=Path('/workspace/dtos-franchise-progress-2250');source=json.loads((B/'source.json').read_text())
r=Path('/workspace/2249-sleeper-relevance/focused-final-runner.py').read_text().replace('assert report[\'tests\'] == 123','assert report[\'tests\'] == 103\nassert not report[\'skipped\']\nassert report[\'memory_limit\'] == 2147483648')
import textwrap
preamble,body=r.split("root = Path('/tmp/relevance-focused')",1)
r=preamble+'\ndef main():\n'+textwrap.indent("root = Path('/tmp/relevance-focused')"+body,'    ')+"\nif __name__ == '__main__':\n    main()\n"
(B/'focused-exact-runner.py').write_text(r);out=B/'focused-exact';out.mkdir()
cmd=['docker','run','--rm','--init','--user','1000:1000','--memory=2g','--memory-swap=2g','--cpus=2','--network=none','-v',str(S)+':/app:ro','-v','/workspace/dtos/.git:/workspace/dtos/.git:ro','-v',str(B/'focused-exact-runner.py')+':/runner.py:ro','-v',str(out)+':/output','-e','DTOS_EXPECTED_HEAD='+source['candidate'],'-e','DTOS_EXPECTED_TREE='+source['tree'],'-e','DTOS_COMPLETED_TRADE_OBSERVATIONS_EVIDENCE=/output/franchise-progress','-e','DTOS_FOLLOWTHROUGH_EVIDENCE=/output/followthrough','-e','DTOS_CURRENT_HISTORY_EVIDENCE=/output/current-history','-e','HOME=/tmp','-e','NODE_OPTIONS=--max-old-space-size=256','-e','GIT_CONFIG_COUNT=1','-e','GIT_CONFIG_KEY_0=safe.directory','-e','GIT_CONFIG_VALUE_0=/app','-w','/app','dtos-canonical314:2245','python','/runner.py',*['tests.'+x for x in ['test_fois_process_execution','test_franchise_trade_progress','test_completed_trade_observations','test_franchise_timeline_coverage','test_history_followthrough','test_current_season_franchise_history','test_completed_trade_observations_browser','test_history_followthrough_browser','test_franchise_timeline_browser','test_current_season_history_browser']]]
(B/'focused-exact-invocation.json').write_text(json.dumps(dict(source=source,command=cmd,runner_sha256=hashlib.sha256(r.encode()).hexdigest(),expected_tests=103),indent=2)+'\n')
with (out/'original-console.log').open('x') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
print('Final focused exit',result.returncode);print((out/'original-console.log').read_text()[-3000:]);raise SystemExit(result.returncode)
