"""Verify published evidence bytes through GitHub's standard public archive."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile

b = Path('/workspace/2233-release')
checkout = Path('/workspace/current-production-handoff')
relative = '.task-evidence/current-production-coverage-2233'
root = checkout / relative
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True).strip()
assert subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/evidence/current-production-coverage-2233'], cwd=checkout, text=True).split()[0] == commit
manifest = json.loads((root / 'manifest.json').read_text())
rows = manifest['files'][:]
for name in ('manifest.json', 'SHA256SUMS'):
    data = (root / name).read_bytes()
    rows.append(dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
archive = b / 'published-evidence-download.zip'
url = 'https://codeload.github.com/Richarddavis47/dtos/zip/' + commit
with urlopen(Request(url, headers={'User-Agent': 'DTOS-evidence-verification'}), timeout=60) as response, archive.open('wb') as sink:
    total = 0
    while chunk := response.read(1024 * 1024):
        total += len(chunk)
        assert total < 750 * 1024**2, 'Unexpected public archive size'
        sink.write(chunk)
prefix = 'dtos-' + commit + '/' + relative + '/'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for row in rows:
        name = row['name']
        assert not name.startswith('/') and '..' not in Path(name).parts
        info = z.getinfo(prefix + name)
        assert info.file_size == row['bytes']
        data = z.read(info)
        assert hashlib.sha256(data).hexdigest() == row['sha256'], name
raw = 'https://raw.githubusercontent.com/Richarddavis47/dtos/' + commit + '/' + relative + '/'
def check_raw(name):
    with urlopen(Request(raw + quote(name, safe='/'), headers={'User-Agent': 'DTOS-evidence-verification'}), timeout=30) as response:
        data = response.read(256 * 1024)
    assert data == (root / name).read_bytes()
    return dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
with ThreadPoolExecutor(max_workers=3) as pool:
    readable = list(pool.map(check_raw, ['README.md', 'LOG_INDEX.md', 'SCOUT_HANDOFF.md']))
report = dict(observed_at=datetime.now(timezone.utc).isoformat(), evidence_commit=commit,
    candidate=manifest['candidate'], tree=manifest['tree'], merge=manifest['merge'],
    archive_url=url, archive_bytes=archive.stat().st_size,
    archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    all_published_payload_bytes_matched=True, verified_files=len(rows),
    verified_payload_bytes=sum(r['bytes'] for r in rows),
    manifest_sha256=hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest(),
    readable_raw_checks=readable,
    scope='Actual GitHub public download; every manifest payload plus manifest/checksum list verified. Separate raw readable report/index/Scout files verified. No private account or production operations.')
(b / 'published-readable-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
