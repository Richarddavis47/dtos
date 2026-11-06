"""Reuse the verified production runtime; real 2 GiB, no external network."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

cache = Path('/workspace/2223-focused314/runtime314-layer-cache-id.txt').read_text().strip()
assert re.fullmatch('[a-f0-9]{64}', cache)
runtime = '/var/lib/docker/vfs/dir/' + cache
image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'dtos-canonical314-flat:2223'], text=True))[0]
assert image['Id'] == 'sha256:2c9de92bf8e05a79587f6edba94052cf614c984a5cb81a62613871388cd6533e'
assert not any(any(s in v.split('=', 1)[0].upper() for s in ('TOKEN', 'SECRET', 'PASSWORD', 'PROXY')) for v in image['Config']['Env'])
args = ['docker', 'run', '--rm', '--init', '--user', '1000:1000', '--memory=2g', '--memory-swap=2g', '--cpus=2', '--network=none']
for name in ['usr', 'bin', 'lib', 'lib64', 'etc', 'opt', 'var', 'root', 'run']:
    args += ['--mount', f'type=bind,src={runtime}/{name},dst=/{name},readonly']
for item in image['Config']['Env']:
    args += ['--env', item]
for name in ('DTOS_EXPECTED_HEAD', 'DTOS_LINEUP_DETAIL_EVIDENCE', 'DTOS_FRANCHISE_HISTORY_EVIDENCE', 'DTOS_CURRENT_HISTORY_EVIDENCE', 'DTOS_FOLLOWTHROUGH_EVIDENCE'):
    if name in os.environ:
        args += ['--env', name + '=' + os.environ[name]]
source = os.environ.get('DTOS_RESOURCE_SOURCE', '/workspace/dtos')
args += ['--env', 'NODE_OPTIONS=--max-old-space-size=256', '--volume', source + ':/app:ro',
         '--mount', 'type=bind,src=/workspace/dtos/.git,dst=/workspace/dtos/.git,readonly',
         '--env', 'GIT_CONFIG_COUNT=1', '--env', 'GIT_CONFIG_KEY_0=safe.directory', '--env', 'GIT_CONFIG_VALUE_0=/app',
         '--volume', '/workspace/history-followthrough:/evidence', '--workdir', '/app',
         'dtos-canonical-runtime-mounts:2223', '/usr/local/bin/python', *sys.argv[1:]]
raise SystemExit(subprocess.run(args).returncode)
