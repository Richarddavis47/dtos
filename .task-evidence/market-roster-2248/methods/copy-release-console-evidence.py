"""Preserve exact decoded release-job text in bounded, readable UTF-8 parts."""
import hashlib
import json
from pathlib import Path
import shutil

B = Path(__file__).resolve().parent
T = Path('/workspace/cache-sharing-handoff/.task-evidence/market-roster-2248')
controller = json.loads((B / 'publisher-controller.json').read_text())
for meta in sorted((B / 'release-decoded-originals').glob('*-transfer.json')):
    row = json.loads(meta.read_text())
    assert row['source'] == controller['commit']
    assert row['exact_decoded_text_utf16_length_verified']
    path = meta.with_name(str(row['job']) + '.log')
    raw = path.read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    target = T / 'release-job-consoles' / str(row['job'])
    target.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(meta, target / 'transfer.json')
    chunks = []
    start = 0
    while start < len(raw):
        end = min(start + 60000, len(raw))
        while end < len(raw) and raw[end] & 0xc0 == 0x80:
            end -= 1
        assert end > start
        chunks.append(raw[start:end])
        start = end
    rows = []
    for i, chunk in enumerate(chunks, 1):
        name = f'part-{i:03}.log'
        (target / name).write_bytes(chunk)
        rows.append(dict(name=name, bytes=len(chunk), sha256=hashlib.sha256(chunk).hexdigest()))
    assert b''.join(chunks) == raw
    (target / 'parts.json').write_text(json.dumps(dict(
        job=row['job'], controller=controller['commit'],
        application_candidate=row['application_candidate'],
        bytes=len(raw), sha256=row['sha256'], parts=rows,
        scope='Original MCP decoded release-controller job text with its newline map; not raw HTTP bytes.'
    ), indent=2) + '\n')
methods = T / 'methods'
methods.mkdir(exist_ok=True)
for name in ['verify-release-certificate.py', 'restore-release-decoded-job-logs.py', 'copy-release-console-evidence.py', 'write-final-report.py', 'finalize-readable-handoff.py', 'verify-published-handoff.py', 'verify-production-smoke.py']:
    shutil.copyfile(B / name, methods / name)
print('Copied original decoded release-job consoles with exact whole/part checksums.')
