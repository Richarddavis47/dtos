"""One standard authorized Actions dispatch, with exact-ref source checks."""
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import sys
import time

b = Path('/workspace/2244-trade-comparison')
stage = sys.argv[1]
assert stage in {'preparation', 'publication'}
operation = 'prepare' if stage == 'preparation' else 'publish'
plan = json.loads(Path('/workspace/dtos-publisher-2244/.github/release-plans/2244.json').read_text())
publisher = json.loads((b / 'publisher-source.json').read_text())['publisher']
assert plan['finalized']
repo = 'repos/' + plan['repository']


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', repo + '/' + path], text=True))


assert api('git/ref/heads/release/2244-actions-publisher')['object']['sha'] == publisher
existing = b / (stage + '-run.json')
if existing.exists():
    previous = json.loads(existing.read_text())
    actual = api('actions/runs/' + str(previous['id']))
    assert actual['head_sha'] == publisher and actual['event'] == 'workflow_dispatch'
    print('Existing dispatch retained:', actual['id'], actual['status'], actual['conclusion'])
    raise SystemExit(0)
if stage == 'preparation':
    assert json.loads((b / 'recovery-offline-verified.json').read_text())['all_native_recovery_guards_passed']
    assert api('git/ref/heads/main')['object']['sha'] == plan['baseline']
else:
    merge = json.loads((b / 'merged-source.json').read_text())
    assert merge['tree'] == plan['tree'] and merge['validated_tree_unchanged']
    assert api('git/ref/heads/main')['object']['sha'] == merge['merge_commit']
    assert json.loads((b / 'prepared-attachment-verification.json').read_text())['native_all_attachment_bytes_read_back']
started = datetime.now(timezone.utc).isoformat()
command = ['gh', 'workflow', 'run', 'canonical-release-recovery.yml', '--repo', plan['repository'],
           '--ref', 'release/2244-actions-publisher', '-f', 'release_operation=' + operation]
if stage == 'publication':
    command += ['-f', 'preparation_run_id=' + str(json.loads((b / 'preparation-run.json').read_text())['id'])]
request = dict(stage=stage, publisher=publisher, candidate=plan['candidate'], tree=plan['tree'],
               requested_at=started, command=command, mechanism='Standard existing authorized GitHub Actions workflow_dispatch; no Cloud release-asset upload')
(b / (stage + '-dispatch-request.json')).write_text(json.dumps(request, indent=2) + '\n')
# No repeated dispatch on an ambiguous or failed transport.
subprocess.run(command, check=True)
for _ in range(10):
    runs = api('actions/workflows/canonical-release-recovery.yml/runs?event=workflow_dispatch&branch=release%2F2244-actions-publisher&per_page=20')['workflow_runs']
    matches = [r for r in runs if r['head_sha'] == publisher and r['event'] == 'workflow_dispatch'
               and datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')).timestamp()
               >= datetime.fromisoformat(started).timestamp() - 2]
    if matches:
        assert len(matches) == 1, 'Ambiguous dispatch; hold instead of choosing an arbitrary run'
        run = matches[0]
        existing.write_text(json.dumps(run, indent=2) + '\n')
        print(stage, run['id'], run['html_url'], run['status'])
        break
    time.sleep(3)
else:
    raise RuntimeError('Dispatch accepted but exact run not visible in bounded lookup; inspect retained request, never dispatch again blindly')
