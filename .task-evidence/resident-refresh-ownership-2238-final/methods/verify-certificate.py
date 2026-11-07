"""Verify original Actions certificate and API attachment digests, without Cloud uploads."""
from pathlib import Path
import json,hashlib,subprocess,sys,zipfile
b=Path('/workspace/2238-resident-refresh');stage=sys.argv[1];assert stage in {'preparation','publication'}
m=json.loads((b/'source.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2238/.github/release-plans/2238.json').read_text());publisher=json.loads((b/'publisher-source.json').read_text())['publisher'];a=json.loads((b/(stage+'-certificate-metadata.json')).read_text());p=b/(stage+'-certificate.zip')
assert len(p.read_bytes())==a['size_in_bytes'] and 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()==a['digest'] and a['workflow_run']['head_sha']==publisher
repo='repos/'+plan['repository']
def api(t):return json.loads(subprocess.check_output(['gh','api',repo+'/'+t],text=True))
run=api('actions/runs/'+str(a['workflow_run']['id']));assert run['head_sha']==publisher and run['status']=='completed' and run['conclusion']=='success' and run['event']=='workflow_dispatch'
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 out=json.loads(z.read('outcome.json'));certificate=json.loads(z.read('publication.json'));validation=json.loads(z.read('assets/VALIDATION.json'));manifest=json.loads(z.read('assets/evidence-manifest.json'))
 operation='prepare' if stage=='preparation' else 'publish'
 assert out['passed'] and out['operation']==certificate['operation']==operation
 assert out['candidate']==certificate['candidate']==validation['candidate']==manifest['candidate']==m['candidate']
 assert certificate['tree']==validation['tree']==manifest['tree']==m['tree'] and certificate['publisher']==publisher and certificate['release_id']==plan['draft_id']
 assert validation['canonical']['passed'] and validation['local_canonical']['passed'] and validation['local_preflight']['passed'] and validation['local_resident_refresh']['passed']
 assert validation['canonical']['head']==validation['local_canonical']['head']==m['candidate'] and validation['product_test_executions']==plan['product_tests'] and validation['version']==plan['version'] and validation['build']==plan['build']
 entries={x['name']:x for x in certificate['attachments']};assert len(entries)==len(certificate['attachments'])==23
 assert len(manifest['files'])==21 and {x['name'] for x in manifest['files']}==set(entries)-{'SHA256SUMS','evidence-manifest.json'}
 for item in manifest['files']:assert item==entries[item['name']]
 sums=dict(line.split('  ',1)[::-1] for line in z.read('assets/SHA256SUMS').decode().splitlines());assert set(sums)==set(entries)-{'SHA256SUMS'}
 assert all(sums[name]==item['sha256'] for name,item in entries.items() if name!='SHA256SUMS')
 for name in ['VALIDATION.json','evidence-manifest.json','SHA256SUMS','prior-attempts.json']:
  data=z.read('assets/'+name);assert len(data)==entries[name]['bytes'] and hashlib.sha256(data).hexdigest()==entries[name]['sha256']
 if stage=='publication':
  ready=json.loads(z.read('production-smoke.json'));(b/'publisher-production-smoke.json').write_text(json.dumps(ready,indent=2)+'\n')
release=api('releases/'+str(plan['draft_id']));assert release['tag_name']=='v1.22.23' and len(release['assets'])==23
assert {x['name'] for x in release['assets']}==set(entries)
for item in release['assets']:
 expected=entries[item['name']];assert item['state']=='uploaded' and item['size']==expected['bytes'] and item['digest']=='sha256:'+expected['sha256']
if stage=='preparation':assert release['draft'] and not release['immutable'] and certificate['draft'] and certificate['main']==plan['baseline']
else:
 merged=json.loads((b/'merged-source.json').read_text())['merge_commit'];assert not release['draft'] and release['immutable'] and not certificate['draft'] and certificate['immutable'] and certificate['main']==merged
(b/('prepared-publication.json' if stage=='preparation' else 'published-publication.json')).write_text(json.dumps(certificate,indent=2)+'\n')
(b/('prepared-attachment-verification.json' if stage=='preparation' else 'published-attachment-verification.json')).write_text(json.dumps({'candidate':m['candidate'],'tree':m['tree'],'publisher':publisher,'attachments':certificate['attachments'],'native_all_attachment_bytes_read_back':True,'cloud_api_digests_match_certificate':True,'certificate_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'scope':'Exact approved Actions publisher verified every attachment byte through native readback. This separate reader verifies original certificate checksum/source and all GitHub API asset digests; it does not claim a second Cloud binary readback.'},indent=2)+'\n')
print(stage,'certificate verified;23attachment hashes match; source and final outcomes agree.')
