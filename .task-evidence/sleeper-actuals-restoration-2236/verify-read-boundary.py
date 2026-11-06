"""Supplemental measured ordinary-read boundary; not a new source or live test."""
import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/app')
b=Path('/evidence');m=json.loads((b/'source.json').read_text());head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip();assert (head,tree)==(m['candidate'],m['tree']);assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
spec=importlib.util.spec_from_file_location('restoration_fixture',b/'restoration_fixture.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);records=[]
for default in [True,False]:
    case=module.ActualRestorationTests('test_reads_do_not_rebind_or_acquire_after_publication')
    try:
        f,data=case.fixture();restored=case.restore(data,default=default)
        with patch('services.player_evidence.bind_retained_actuals',side_effect=AssertionError('unexpected read preparation')) as bind,patch('services.sleeper.sleeper_get',side_effect=AssertionError('unexpected provider read')) as provider:
            responses=case.render(f,restored)
            assert [r.status_code for r in responses]==[200,200,200]
            bind.assert_not_called();provider.assert_not_called()
            records.append(dict(path='default' if default else 'connected',response_statuses=[r.status_code for r in responses],binding_calls=bind.call_count,sleeper_get_calls=provider.call_count,native_source_generation=responses[-1].json()['valuation']['canonical_production']['source_generation']))
    finally:case.doCleanups()
result=dict(candidate=head,tree=tree,passed=True,records=records,scope=__doc__,fixture_sha256=hashlib.sha256((b/'restoration_fixture.py').read_bytes()).hexdigest(),limitations='Counts are explicit entry-point spies after fixture construction and cache restoration, not packet counters. Original matched probe source_requests=0 was a descriptive offline-fixture field, not an independently instrumented transport counter. This supplement leaves original logs/JSON unchanged. Existing source/canonical tests and network-none runtime independently establish the source contract; no live parity is claimed.')
(b/'read-boundary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
