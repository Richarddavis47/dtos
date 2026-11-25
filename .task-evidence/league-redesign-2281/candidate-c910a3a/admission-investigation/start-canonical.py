"""Extract and run the official source-pinned validator under a real 2 GiB cap."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import textwrap

from common import BASE, SOURCE_CHECKOUT, assert_checkout, digest, load_source, write_json

source = load_source()
assert_checkout(source)
path = '.github/workflows/canonical-release-recovery.yml'
def original(revision):
    return subprocess.check_output(['git','show',f'{revision}:{path}'], cwd=SOURCE_CHECKOUT, text=True)
raw = original(source['candidate'])
assert raw == original(source['baseline'])
scratch = Path('/dev/shm/dtos-2281-canonical-' + source['candidate'][:8])
scratch.mkdir()
assert shutil.disk_usage(scratch).free > (8*1024+256)*1024**2
out = BASE/'local-canonical'
(out/'observer').mkdir(parents=True, exist_ok=False)
files = []
for name, checksum in {
    'runner.py': '574308d9f64252575970aa19ce113f603ccb9927f2c6a523e8c228869fd37cac',
    'observer/sitecustomize.py': '3f43288a099e49a3ed2dea36f977b596707589eaefd2656b40a3b9c6533be2d4',
}.items():
    marker = "          cat > .validation/canonical-release/" + name + " <<'PY'\n"
    assert raw.count(marker) == 1
    content = (textwrap.dedent(raw.split(marker,1)[1].split('\n          PY\n',1)[0])+'\n').encode()
    assert hashlib.sha256(content).hexdigest() == checksum
    ast.parse(content)
    (out/name).write_bytes(content)
    files.append(dict(name=name,sha256=checksum))
command = ['bash',str(BASE/'docker-validation.sh'),'create','dtos-canonical-2281',
           str(SOURCE_CHECKOUT),str(out.resolve()),str(scratch),'python','/output/runner.py']
container = subprocess.check_output(command,text=True).strip()
assert shutil.disk_usage(scratch).free > 8*1024**3
write_json(BASE/'canonical-invocation.json',dict(container=container,source=source,files=files,
    created_at=datetime.now(timezone.utc).isoformat(),command=command,
    wrapper_sha256=digest(BASE/'docker-validation.sh'),
    fixture_free_after_container_creation=shutil.disk_usage(scratch).free,
    toolchain='Read-only /usr and browser settings mounts from the pinned existing matching image. Thin bookworm container root avoids needless VFS copies. Browser /tmp uses the disk-backed writable layer and the Node heap setting matches hosted canonical. Diagnostic scratch retains its original 8 GiB guard. Real 2 GiB, 2 CPUs and no network.',status='RUNNING_NOT_PASSED'))
subprocess.run(['docker','start',container],check=True)
code = subprocess.check_output(['docker','wait',container],text=True).strip()
(BASE/'local-original-exit.log').write_text(code+'\n')
subprocess.run(['python',str(BASE/'collect-local-completion.py')],check=True)
