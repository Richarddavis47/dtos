"""Preserve prior original payload bytes under explicit historical prefixes."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

b = Path('/workspace/2229-release/final-scheduled')
parent = b.parent
pub = Path('/workspace/dtos-publisher-2229/.github/release-plans')
archive = pub/'2229-prior.zip'
saved = b/'prior-before-scheduling.zip'
if not saved.exists(): archive.replace(saved)
payloads = {}
with zipfile.ZipFile(saved) as old:
    assert old.testzip() is None
    manifest = json.loads(old.read('prior-manifest.json'))
    for row in manifest['files']:
        data = old.read(row['name'])
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
    for name in old.namelist():
        payloads['prior-through-63ef/'+name] = old.read(name)
recovery = b/'recovery-before-scheduling.zip'
if not recovery.exists(): recovery = pub/'2229-recovery.zip'
with zipfile.ZipFile(recovery) as old:
    result = json.loads(old.read('local-canonical/result.json'))
    assert result['head'] == '63efcdde1573f9cbf2bc5b2bd02984d3d477064f'
    for name in ['result.json','manifest.json','SHA256SUMS','unittest-console.log',
            'canonical.log','canonical-trace.jsonl','memory.jsonl','tests.jsonl']:
        payloads['superseded-63ef-success/'+name] = old.read('local-canonical/'+name)
for name in ['resource-diagnosis.json','pr-reference-reconciliation.json',
        'local-scratch-setup-failure.log','publisher-preliminary-lint.log',
        'scratch-reclamation.json','scratch-dependencies.json','scratch-bytecode.json']:
    payloads['scheduling-reconciliation/'+name] = (b/name).read_bytes()
payloads['scheduling-reconciliation/browser-collection-isolation.py'] = (parent/'browser-collection-isolation.py').read_bytes()
payloads['scheduling-reconciliation/collection-isolation.log'] = (parent/'collection-isolation.log').read_bytes()
payloads['scheduling-reconciliation/collection-isolation-result.json'] = (parent/'collection-isolation/result.json').read_bytes()
payloads['README.md'] = b'''Prior evidence only; never final-source acceptance.
The original failed/canceled/incomplete attempts and withdrawn experiments are preserved byte-identically under prior-through-63ef/. Its own original manifest remains intact. The old passing63ef local run is superseded for final-source acceptance; selected original console/memory/source records are under superseded-63ef-success/. The full old archive and original failed hosted ZIP remain in the immutable a55bc6865682f99b7e43c93238823d5c0eca50e0 handoff, not rewritten here.
The final candidate is dcacecf1fee73abd981e39e8bc8c722838ddf026/tree752cfe006296bcaf879472183d100fa9df940fbb. A measured scheduling correction runs the unchanged normal-capacity browser journey before accumulated full-suite fixture state. Original assertions, Trade admission/reserves and enforced2GiB policy remain unchanged. The separate final-source canonical/hosted artifacts, not these prior records or the isolation experiment, must establish mandatory completion.
One local scratch prerequisite setup failed before execution and one scoped publisher lint setup attempted a read-only cache. Their original logs remain separate; the former was corrected by removing only regenerable/byte-verified duplicate scratch and the latter by --no-cache, without weakening assertions or permission changes. Original baseline HTML/report loss remains explicitly documented in historical evidence. No recreated evidence is represented as an original. Cleanup observations do not prove indefinite leak freedom.
'''
rows = []
pattern = re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,data in sorted(payloads.items()):
        if Path(name).suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:
            assert not pattern.search(data), name
        z.writestr(name,data)
        rows.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    meta = json.loads((b/'source.json').read_text())
    z.writestr('prior-manifest.json',json.dumps(dict(candidate=meta['candidate'],tree=meta['tree'],
        scope='prior-attempts-only',original_archive_sha256=hashlib.sha256(saved.read_bytes()).hexdigest(),
        files=rows),indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for row in rows: assert hashlib.sha256(z.read(row['name'])).hexdigest() == row['sha256']
assert archive.stat().st_size < 100*1024**2
print('Prior original payloads',len(rows),'bytes',archive.stat().st_size,
      'SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
