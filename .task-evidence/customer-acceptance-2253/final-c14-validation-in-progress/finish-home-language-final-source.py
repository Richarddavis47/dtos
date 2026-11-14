"""Finish the admitted C12 captures, preserve them, then validate one confirmed Home display gap."""
from common import *
import time,datetime,collections,shutil
C12='59cfe3c3bf7daf9fd9c7e9b5f50d6b5b11f2c140';old=load_source();assert old['candidate']==C12
while not (BASE/'current-final-extra-native-ready.json').exists():time.sleep(10)
assert json.loads((BASE/'current-final-extra-native-ready.json').read_text())['source']==old
assert_checkout(old);A=BASE/'attempt-c12-complete-validation-home-wording-gap';assert not A.exists();A.mkdir();write_json(A/'source.json',old)
names=['local-canonical','fixture','canonical-invocation.json','canonical-harness-extraction.json','local-verified.json','readable-console','local-container-cleanup.json','local-container-state-original.json','local-container-stdout-original.log','local-canonical-integrity-original.log','fixture-isolation-exact','fixture-isolation-invocation.json','fixture-isolation-ready.json','fixture-isolation-exact-container-original.json','focused-exact','focused-exact-invocation.json','focused-ready.json','focused-exact-container-original.json','harness-contract-exact','harness-contract-exact-invocation.json','harness-contract-ready.json','local-preflight','local-restoration-unused','local-resident-refresh','resource-preservation-verified.json','visual-final','visual-review-main-final.json','reviewed-main-pixel-reuse.json','c12-main-pixel-proof.json','visual-review-final-sheets','post-full-acceptance-ready.json','current-final-extra-native-ready.json','local-capital-capture','local-capital-capture-invocation.json','local-capital-capture-original.log','retained-history-probe-original.log','retained-history-probe-invocation.json','retained-history-feature.json','local-history-capture','local-history-capture-invocation.json','local-history-capture-original.log','discovery-final','discovery-final-invocation.json','customer-test-population-final.json','host-canonical-verified.json','host-canonical-readable','hosted-originals','hosted-artifacts-verified.json','hosted-delivery-verified.json','hosted-final-records.json','hosted-final-records-original-private.json','validation-runs.json','artifact-download-queue.json','readable-product-original','hosted-decoded-originals','product-test-counts.json','partner-history','team-need','protections','current-native-sidecar-provenance.json','prior-package-final.zip','prior-package-final-complete.json','source-preservation-final.json','source-findings-final.json','final-candidate.patch','final-candidate-patch.sha256','WORK_STATUS.json','current-seven-state-review.jpg','host-canonical-integrity-original.log','host-native-integrity-original.log','scratch-recovery-completed.json','preserved-archives-restored.json','closed-evidence-temporarily-preserved.json','closed-evidence-restored.json']
names += [p.name for p in BASE.glob('after-*-59cfe3c3*')]
for n in dict.fromkeys(names):
 p=BASE/n
 if p.exists():assert not (A/n).exists();p.rename(A/n)
(A/'README.md').write_text('C12 completed4504/all10 local and hosted, all13 required jobs and current fixture captures. Actual seven-state Home review found the primary prepared cost still used legal-replacement production; no release occurred. One shared display adapter correction and matched regression require final-source validation. These originals remain valid on C12, not rebound to a later source. No original memory-replay exact-cause claim.\n')
patch=BASE/'pending-home-card-language.patch';subprocess.run(['git','apply','--check',str(patch)],cwd=SOURCE_CHECKOUT,check=True);subprocess.run(['git','apply',str(patch)],cwd=SOURCE_CHECKOUT,check=True);subprocess.run(['git','diff','--check'],cwd=SOURCE_CHECKOUT,check=True)
subprocess.run(['git','add','src/ui/home_trade_opportunities.py','tests/test_customer_acceptance_followup.py'],cwd=SOURCE_CHECKOUT,check=True);subprocess.run(['git','commit','-m','Use the shared plain-language explanation on Home trade cards'],cwd=SOURCE_CHECKOUT,check=True)
S=old|dict(candidate=command('git','rev-parse','HEAD',cwd=SOURCE_CHECKOUT),tree=command('git','rev-parse','HEAD^{tree}',cwd=SOURCE_CHECKOUT));write_json(BASE/'source.json',S);assert_checkout(S)
write_json(BASE/'WORK_STATUS.json',dict(source=S,status='FINAL_HOME_PRIMARY_COST_CORRECTION_FOCUSED_THEN_REQUIRED_VALIDATION',previous_originals=str(A),release='PR342 remains draft; no source merge/publication/deployment. Prior passing source is preserved, not claimed current.'))
def run(label,args):
 assert_checkout(S)
 with (BASE/('c13-'+label+'-original.log')).open('x') as f:r=subprocess.run(args,cwd=BASE,stdout=f,stderr=subprocess.STDOUT)
 print(json.dumps(dict(phase=label,exit=r.returncode,at=datetime.datetime.now(datetime.timezone.utc).isoformat())),flush=True);assert r.returncode==0,label
def wait(name):
 r=json.loads((BASE/name).read_text())
 while True:
  d=json.loads(command('docker','inspect',r['container']))[0]
  if not d['State']['Running']:return d
  time.sleep(10)
run('focused-start',['python','start-focused-v5.py','triage-c13-home','tests.test_customer_acceptance_followup','tests.test_front_office_brief','tests.test_front_office_brief_browser','tests.test_customer_trade_experience.CustomerTradeJourneyTests.test_compact_offer_review_compare_and_back_keeps_original_work']);wait('triage-c13-home-invocation.json');run('focused-collect',['python','collect-focused.py','triage-c13-home'])
run('discovery-start',['python','start-discovery-final.py']);d=wait('discovery-final-invocation.json');assert d['State']['ExitCode']==0 and not d['State']['OOMKilled'];iv=json.loads((BASE/'discovery-final/discovery.json').read_text());prior=json.loads((A/'discovery-final/discovery.json').read_text());assert iv['tests_discovered']==4504 and not iv['loader_errors'] and collections.Counter(iv['test_ids'])==collections.Counter(prior['test_ids']);subprocess.run(['docker','rm',d['Id']],check=True,stdout=subprocess.DEVNULL)
run('push-final-source',['git','-C',str(SOURCE_CHECKOUT),'push','origin',S['branch']])
for mode,receipt in [('normal','fixture-isolation-invocation.json'),('features','focused-exact-invocation.json')]:
 run(mode+'-start',['python','start-controls-durable.py',mode]);wait(receipt);run(mode+'-collect',['python','collect-controls-durable.py',mode])
run('harness-start',['python','start-harness-contract.py']);wait('harness-contract-exact-invocation.json');run('harness-collect',['python','collect-harness-contract.py'])
run('resource',['python','run-local-resource.py']);run('input-cleanup',['python','cleanup-verified-fixture-copies.py','current'])
print('Focused/normal/preservation/harness/native passed; full local launch needs source-bound scratch preservation and unchanged official harness.',flush=True)
write_json(BASE/'c13-pre-full-ready.json',dict(source=S,passed=True,scope='Focused and preservation controls complete; full local, hosted, visual and publisher remain mandatory.'))
