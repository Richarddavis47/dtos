from pathlib import Path
import ast,hashlib,json,subprocess,shutil
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');source=Path('/workspace/dtos')
def git(*args):return subprocess.check_output(['git',*args],cwd=source,text=True).strip()
head,tree=git('rev-parse','HEAD'),git('rev-parse','HEAD^{tree}')
m=dict(baseline='1e1234fbcf7ca18f3862e5cdeac1451780e51b49',baseline_tree='4051883efb1f225dcd71e07f1998e45c9d96fb39',candidate=head,tree=tree,version='1.22.23',build=2238,pr=327,source_branch='fix/resident-refresh-reference-release',status='VALIDATING; not merged or released')
(b/'source.json').write_text(json.dumps(m,indent=2)+'\n')
with (b/'candidate-production.patch').open('wb') as f:subprocess.run(['git','diff','--binary',m['baseline'],head],cwd=source,stdout=f,check=True)
method=source/'services/league_maintenance.py';text=method.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='ensure_periodic_refresh');code=''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno]);sha=hashlib.sha256(code.encode()).hexdigest()
comparison=json.loads((r/'memory-final-comparison-summary.json').read_text());assert sha==json.loads((r/'memory-final-shipping-1.json').read_text())['original_maintenance_sha256']
(b/'measurement-source-association.json').write_text(json.dumps(dict(final_candidate=head,final_tree=tree,matched_measurement_candidate=comparison['source'],matched_measurement_tree=comparison['tree'],shared_production_function_sha256=sha,qualification='Formal baseline-function/shipping pairs ran on509. Final108 changes only the resource acceptance tool; the full production refresh function is byte-identical. Final108 resource and mandatory gates are separate.'),indent=2)+'\n')
(b/'REPORT.md').write_text(f'''# Resident-refresh ownership — release review

Status: VALIDATING. No merge, immutable release or deployment claimed here.

Baseline v1.22.22/build2237: `{m['baseline']}` / `{m['baseline_tree']}`.
Candidate v1.22.23/build2238: `{head}` / `{tree}`. PR#327.

## Confirmed cause and chosen correction

The resident maintenance coroutine retained a completed worker for the next interval. Its task result or failed traceback could pin a superseded full source publication after a separate legitimate replacement. This is unnecessary task ownership, distinct from current warm contexts, request pins, persistent recovery data and allocator retention. The worker's local reference is now dropped after terminal processing. Repeated cancellation drains the existing writer through shield before close/release. No eviction or immutable-catalog sharing is implemented. Existing periodic schedule, persistence, failure qualification and source publication remain unchanged.

## Measured impact and limits

Three matched full restore/publication pairs in real2GiB/no-swap/twoCPU/offline Python3.14.3 containers show obsolete settled retained-memory reductions of54.652,56.281and56.176MiB. A failed-worker pair recovers54.801MiB. Exact native facts/disclosures digests agree. During an active-reader control the old source intentionally remains, then releases only after its reader. Peaks are approximately403MiB and materially unchanged. No smaller restoration allowance is supported or proposed. Measurement includes actual cache decoding, native binding, projection restoration and canonical publication; verification clocks and GC/allocator trim are disclosed in methods and counters.

The matched pairs used commit509; its complete production refresh function is identical in final108. The fixture payloads are source-compatible public disposable data, not a privateGranite profile. In the first hosted Python3.12 run, logical release returned only~10.7MiB immediately and recovery correctly deferred. The fixture had incorrectly assumed sufficient immediate allocator return. Final recovery explicitly relieves its own remaining pressure and checks actual admission before one real restore. It does not attribute recovery to the code change alone. Original failure and canceled superseded suites remain separate.

## Safeguards

No current/active source eviction, catalog/account overlay sharing, cache format change, source loss, provider acquisition or retry loop. Full16× physical cache basis,2GiB cap, FOIS768MiB and Trade256+128MiB reserves are unchanged. Native Sleeper results, exact zeros/negatives/precision, scoring, pick identity, submitted lineups, neutral/Custom mathematics, saved preferences and FOIS provenance remain unchanged. Genuine incompatibility and unsafe capacity still defer/reject.

## Production boundary

Authorized Render management evidence confirms the baseline and retained logs/metrics, but cannot provide the current serving process's full ownership snapshot. This session has no authenticated Render Shell/SSH executor; the existing browser connector reports disconnected. The unchanged external401 binding is not retried. MainChat's previous local token200 is supplied evidence, not reproduced. No private cache decoded, no Granite entry or Trade/sync/FOIS workload initiated. Fresh preflight, conditional entry and independent completed-week actual-score parity remain HELD until existing authorized live access is available. No synthetic result proves Granite recovery, production causation or long-term leak freedom.

Final gate counts and immutable/deployed identity will be added only after verified completion.
''')
print(head,tree)
