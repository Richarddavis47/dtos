"""Generate only absent local capture sidecars, outside original canonical evidence."""
from pathlib import Path
import json,subprocess,datetime
from common import BASE as B,load_source,docker_base,image_record,digest
s=load_source();local=json.loads((B/'local-verified.json').read_text());assert local['all_local_gates_passed'] and local['tests']==4435
out=B/'local-capital-capture';assert not out.exists();out.mkdir();runner=B/'local-capital-capture-runner.py';name='dtos-local-capital-capture-2250';cmd=docker_base(s)+['--name',name,'--env','DTOS_COMPARE_EVIDENCE=/evidence/local-capital-capture',image_record()['Id'],'python','/evidence/'+runner.name,'tests.test_trade_capital_browser']
record=dict(source=s,command=cmd,runner_sha256=digest(runner),started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason='Successful complete canonical tests did not request DTOS_COMPARE_EVIDENCE sidecars; two unchanged methods are rerun solely for independent local captures. The original canonical publication remains unchanged.',original_local_manifest_sha256=digest(B/'local-canonical/manifest.json'))
(B/'local-capital-capture-invocation.json').write_text(json.dumps(record,indent=2)+'\n')
with (B/'local-capital-capture-original.log').open('xb') as sink:r=subprocess.run(cmd,stdout=sink,stderr=subprocess.STDOUT)
record.update(exit_code=r.returncode,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),container_absent_after=not subprocess.check_output(['docker','ps','-a','--filter','name=^/'+name+'$','--format','{{.ID}}'],text=True).strip());assert digest(B/'local-canonical/manifest.json')==record['original_local_manifest_sha256'];(B/'local-capital-capture-invocation.json').write_text(json.dumps(record,indent=2)+'\n');assert r.returncode==0 and record['container_absent_after']
print('Two actual local capital browser controls and clean captured sidecars completed; full canonical originals untouched.')
