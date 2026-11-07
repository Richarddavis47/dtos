# Exact methods and commands

This continuation does not change application source. Baseline and tested head:1e1234fbcf7ca18f3862e5cdeac1451780e51b49; tree4051883efb1f225dcd71e07f1998e45c9d96fb39.

The retained run-constrained.py uses the established production Python3.14.3 runtime/image SHA2c9de92bf8e05a79587f6edba94052cf614c984a5cb81a62613871388cd6533e, UID1000, --memory=2g, --memory-swap=2g, --cpus=2, --network=none. The session's runtime-layer mount is not a portable image download. The repository's existing canonical workflow/Docker dependencies describe how that established runtime is built. No proxy or credential configuration was changed; offline containers do not contact providers.

Existing fixture JSON and projection SQLite bytes are reused. fixtures.json supplies their exact SHA256, sizes and fixed public source links. The original producer methods are in the prior fixed evidence commit; no fixture was rebuilt to a target file size. The four current payloads range45,659,982–45,679,653bytes. Projection DB SHA43541f6a3c738d0ebeac0794cdfd7c009bd27f450816919315b824b512a7b708 remains unchanged.

## Primary decoder comparison

From the retained task folder:

```
python run-reconciliation.py
```

The exact24commands, timestamps, logs and return codes are in results/invocations.json. Each invokes:

```
python run-constrained.py /evidence/reconcile-restoration.py --decoder standard --fixture oneqb --repeat 2
python run-constrained.py /evidence/reconcile-restoration.py --decoder shipping --fixture oneqb --repeat 2
```

The same pattern covers superflex, oneqb-diverse and oneqb-unicode, repeats2–4, alternating execution order. Each JSON records method/source/payload/digest hashes. The pair1results remain exploratory records, excluded from the final12pair medians. Original raw stdout/stderr is retained for every command.

Both sides use the unmodified shipping semantic digest. Only prep.load_cache_json changes between standard and shipping. Other patches merely point the existing cache lookup at the exact fake file and add identical measurement wrappers around the real binding function. No admission, telemetry, lifecycle, reconstruction or publication behavior is mocked. Owned raw copies are fsynced before the baseline sample; full file pages are included. Kernel peak capture precedes graph/digest instrumentation.

## Clean lifecycle and conditional recovery

```
python run-constrained.py /evidence/clean-lifecycle-reconciliation.py --decoder shipping
python run-constrained.py /evidence/clean-lifecycle-reconciliation.py --decoder standard
python run-constrained.py /evidence/clean-lifecycle-reconciliation.py --decoder shipping --pressure
python run-constrained.py /evidence/clean-lifecycle-reconciliation.py --decoder shipping --detach-prototype
```

The initial executed methods are retained separately because later method refinements added the actual pure guard for pressure sizing and the explicit unshipped prototype switch. Primary matched shipping/prototype JSONs have the identical instrumentation hash. Clean lifecycle runs do not graph-walk or serialize the entire publication before cleanup. GC/native trim is explicit harness instrumentation, not a new production feature. Removing container-owned scratch is separately observed so declining file pages cannot be mistaken for anonymous-memory reclamation.

The pressure fixture touches bounded anonymous pages below the2GiB limit. It calls the real restoration guard and actual restore path. It records a true deferral, then explicitly closes its known-idle unpinned fixture context, remeasures raw usage and completes a real restoration under the same retained pressure. No application eviction-policy change is claimed. The prototype only reserializes public identity metadata in a disposable process; it is not shipped and is rejected as a remedy.

## Structural opportunities

```
python run-constrained.py /evidence/analyze-retained-components.py
```

This analysis reads only the already published disposable one-QB file. It examines decoded cached data BEFORE native rebinding/publication. Its hypothetical content-equal alias graphs are bounds, not safe mutation contracts, resident RSS or full-lifecycle peak savings. It creates no permanent warehouse and changes no application source.

## New regression and comparison integrity

```
python run-constrained.py -m unittest -v tests.test_cache_json tests.test_cache_restoration_admission tests.test_restoration_unused_memory tests.test_sleeper_actual_restoration tests.test_fois_navigation_reliability.WorkerTimeoutReliabilityTests tests.test_league_entry_coordination
python run-constrained.py /evidence/test_reconciliation_analysis.py
python run-constrained.py /evidence/reconciliation_analysis.py
```

Results:63application-focused tests;12comparison-integrity tests;12matched primary pairs verified. These are new executions. The integrity tests reject digest, source, instrumentation, payload and publication differences, incorrect limits, OOM, setup-dominated peaks and incomplete cleanup.

## Previous mandatory validation, explicitly reused

```
python reconcile-baseline-validation.py
```

No application diff exists. Existing4,250local and4,250hosted regression results, ten gates each,640/644canonical entries and12required hosted jobs apply to the exact unchanged tree4051883. Latest job outcomes and original hosted ZIP SHA are rechecked. These are NOT new full-suite executions. The prior immutable release and full readable originals remain linked in baseline-validation-reuse.json and the main report. No gate was waived for a proposed new source tree; no new source tree or application release is proposed.

## Access and incomplete work

One existing Opera list-tabs request returned UNAVAILABLE / Browser not connected. No Render Shell/SSH executor is exposed. The unchanged external inspection binding401 was not retried. No private cache decoding, Granite entry, Trade search, sync, FOIS rebuild, cache clear, restart or settings mutation occurred. Fresh public readiness is a separate observation. The access failure and one setup import-path error are identified in attempt-qualifications.json, not presented as passing application controls or reconstructed original logs.
