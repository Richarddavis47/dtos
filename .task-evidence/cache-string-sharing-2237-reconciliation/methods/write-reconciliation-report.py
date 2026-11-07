from pathlib import Path
import json
b=Path('/workspace/2237-cache-duplication');r=b/'reconciliation';s=json.loads((r/'verified-summary.json').read_text());mib=lambda x:f'{x/1048576:.2f}'
rows='\n'.join(f"| {x['fixture']} | {mib(x['standard_peak'])} → {mib(x['shipping_peak'])} | {mib(x['standard_retained'])} → {mib(x['shipping_retained'])} | {x['standard_seconds']:.3f} → {x['shipping_seconds']:.3f} |" for x in s['medians'])
x=json.loads((r/'oneqb-shipping-2.json').read_text());e=x['ordered_exclusive_graph_bytes'];union=x['union_graph_bytes'];catalog=e['players']+e['normalized_players'];pressure=json.loads((r/'clean-shipping-pressure.json').read_text());shipping=json.loads((r/'clean-shipping-matched.json').read_text());proto=json.loads((r/'clean-shipping-detached-prototype.json').read_text())
def stage(obj,label):return next(x for x in obj['stages'] if x['label']==label)
plain=shipping['initial'];closed=stage(shipping,'all_owned_runtimes_closed');unlinked=stage(shipping,'after_scratch_unlink')
text=f'''# League restoration memory reconciliation — PARTIAL customer outcome; no new release

The decoder-only comparison is now corrected and reproducible. The earlier build2237 study changed both the decoder and a digest helper, so it cannot isolate decoder savings. Twelve new matched pairs support decoder-only peak savings of {mib(s['peak_saving_bytes_range'][0])}–{mib(s['peak_saving_bytes_range'][1])}MiB and retained savings of {mib(s['retained_saving_bytes_range'][0])}–{mib(s['retained_saving_bytes_range'][1])}MiB in these disposable structures. They do not establish Granite recovery. No further application correction or production release is justified by the available evidence.

## Baseline, access and outcome

Fresh public readiness confirms v1.22.22/build2237, commit `1e1234fbcf7ca18f3862e5cdeac1451780e51b49`, tree `4051883efb1f225dcd71e07f1998e45c9d96fb39`. Repository main is clean and unchanged. No application branch/PR, version, tag, release, deployment, infrastructure, credentials or user data was changed by this continuation. Evidence commits are documentation/artifact handoff only.

Live preflight, one conditional Granite entry and independent Sleeper actual-score parity are HELD. One existing Opera connector capability request returned UNAVAILABLE / Browser not connected. This environment has no Render Shell/SSH executor or associated controllable authenticated browser runtime. The unchanged external inspection binding was not retried after its prior401. Main Chat's earlier Render-local identity200 remains supplied evidence, not a new measurement. No Granite entry, source synchronization, Trade search, FOIS rebuild, cache clear, manual restart or preference change occurred. [Fresh public identity](results/production-public-readiness.json) and [exact access boundary](results/access-boundary.json) are separate from private admission.

## What was wrong with the original comparison

In the retained `profile-combined.py`, mode `candidate` selected the shipping decoder **and** entered `patch.object(engine,'_semantic_digest',side_effect=stream)`. Mode `plain` used the standard decoder and shipping digest. Its description that only the decoder varied was inaccurate. This was a measurement confound, not a change in production digest behavior or evidence that the released application failed its safety tests.

The immutable release, original profiles and method are unchanged. [Original measurements and hashes](results/original-measurements-preserved.json) locate them. The [corrigendum](CORRIGENDUM.md) replaces the decoder-only causal claim; it does not rewrite history or reinterpret old values as new captures.

## Corrected method and full lifecycle

Four previously published structural payloads are reused byte-for-byte: one-QB/K/DEF, Superflex, high-cardinality metadata and Unicode. There is no new same-size padding study. The real identity normalization, native matchup/results preparation, projection publication and canonical consumer paths produced these cohorts. They contain10,788catalog identities,991modeled production consumers and2,592fictional native observations across nine source weeks. They are field-dense and missing reference analysis; those distributions are not verified against private Granite. No private production cache is available or was decoded/exported.

Each of three repeats uses fresh disposable containers with the same clean source, Python3.14.3, pinned image `sha256:2c9de92bf8e05a79587f6edba94052cf614c984a5cb81a62613871388cd6533e`, UID1000, two CPUs, actual2GiB limit, zero swap and no external network. Within each pair only the loader changes: standard `json.load` or shipping `load_cache_json`. Digest implementation/source hash, full instrumentation hash, fixture SHA, projection database and complete resulting publication digest match. The comparison verifier rejects changes to those fields and rejects OOM, orphaned resources, unavailable completion or a kernel peak dominated by earlier setup.

Each run streams/fsyncs an exact fixture copy into container-owned scratch before the initial sample. Its charged file pages remain in raw cgroup usage; none are discounted or cleared. Stages cover decode, native evidence binding/reconstruction, runtime materialization, projection restoration and canonical publication. Kernel high-water readings occur immediately before/after that entire operation. The final peak must exceed the earlier setup peak. Initial/post-publication raw, anon, file, inactive-file and process counters are retained in every result. Five-ms Python samples may miss GIL-bound C-decoder peaks, especially Unicode. Kernel counters are primary. Deep graph accounting and full-value verification happen **after** the measured operation and are not counted as its peak.

Median of three matched pairs; memory figures are incremental raw cgroup MiB, not absolute process RSS:

| Payload | Kernel peak, standard → shipping | Retained after publication, standard → shipping | Seconds, standard → shipping |
|---|---:|---:|---:|
{rows}

[All24original results and commands](results/verified-summary.json) retain exact bytes, absolute baselines/peaks and per-stage clocks. The JSON files include full stage counters; figures in this table do not turn into a reservation. Decode is slower in these controls. Matching source/value digests establish fixture parity, not an independent live Sleeper comparison.

## Dominant remaining costs

The one-QB shipping result's unique source-data graph is {mib(union)}MiB. In an explicitly ordered attribution, raw player catalog containers/text contribute {mib(e['players'])}MiB and normalized identities add {mib(e['normalized_players'])}MiB: together {mib(catalog)}MiB, about {100*catalog/union:.1f}% of that graph. Canonical production adds {mib(e['canonical_player_production'])}MiB and the valuation report adds {mib(e['valuation_intelligence'])}MiB. This order-dependent attribution is not resident RSS; separate standalone component graphs overlap. It does not explain private container usage.

Derived Sleeper actuals are only {mib(x['component_standalone_graph_bytes']['derived_actuals'])}MiB standalone in this cohort. Consumer disclosures after actual binding are {mib(x['component_standalone_graph_bytes']['consumer_disclosures'])}MiB standalone. They are not the dominant raw/normalized catalog cost. Serialized source catalog and normalized records total30,308,432bytes; native season matchups269,636bytes; derived actuals603,568bytes. The4,033,965byte production envelope and8,896,693byte valuation envelope contain nested groups and must not be added to their children.

The Unicode sensitivity demonstrates another material transient: nearly unchanged45.67MB serialized bytes can require a much wider whole-file Python string. Its shipping peak is about277MiB versus146MiB in the base one-QB control. This does not prove Granite contains that structure. A byte/stream parser would need separate precision, Unicode, duplicate-key, file-pinning and cancellation proof; changing parser technology is not a narrow demonstrated fix here.

The decode-only opportunity analysis finds991identical missing-reference rows and four disclosure value groups. Hypothetical aliases reduce those standalone graphs by8.70MiB and19.41MiB respectively. These are **not additive full-lifecycle savings**. That script examines decoded cached rows **before** native rebinding/publication. Actual rebinding already replaces disclosures with a different compact representation. Current disclosures are independent mutable `asdict` containers; sharing them could couple mutations. The all-missing reference cohort is particularly favorable to deduplication and is not representative private evidence. No aliasing or omitted-field optimization is shipped.

## Cleanup, retention and pressure

Clean lifecycle controls use no graph walk or full JSON digest before cleanup. Three close/reopen cycles retain a second warm league. Runtime weak references disappear, current-history source references are removed, workers are absent, scratch is removed and OOM counts remain zero. These finite controls do not establish long-term leak freedom.

In the matched shipping control, two-warm incremental usage reaches {mib(stage(shipping,'two_warm_2')['cgroup_current_bytes']-plain['cgroup_current_bytes'])}MiB. After all owned runtimes close and disclosed harness GC/trim, anonymous memory is still {mib(closed['anon']-plain['anon'])}MiB above initial. After scratch unlink, raw usage is only {mib(unlinked['cgroup_current_bytes']-plain['cgroup_current_bytes'])}MiB above initial because roughly87MiB of charged file pages have disappeared. **That raw decline must not be described as equivalent anonymous-memory release.** Public identity retention and allocator behavior remain relevant; no exact leak or complete attribution of residual anonymous memory is established. Existing production cleanup is unchanged.

An explicit public-identity detachment prototype keeps values equal but raises one-warm usage by {mib(stage(proto,'one_warm')['cgroup_current_bytes']-proto['initial']['cgroup_current_bytes']-(stage(shipping,'one_warm')['cgroup_current_bytes']-plain['cgroup_current_bytes']))}MiB and two-warm usage by {mib(stage(proto,'two_warm_2')['cgroup_current_bytes']-proto['initial']['cgroup_current_bytes']-(stage(shipping,'two_warm_2')['cgroup_current_bytes']-plain['cgroup_current_bytes']))}MiB. It lowers the final post-close raw increment by about {mib((closed['cgroup_current_bytes']-plain['cgroup_current_bytes'])-(stage(proto,'all_owned_runtimes_closed')['cgroup_current_bytes']-proto['initial']['cgroup_current_bytes']))}MiB, but that trade-off does not justify shipping. It is an unshipped disposable hypothesis, not an application correction.

The actual2GiB pressure control correctly defers with about791MiB headroom and no competing heavyweight operation. Its unchanged real guard requires {mib(pressure['cases']['required_capacity'])}MiB for the45,671,736byte fixture. The fixture owner then closes a known-idle, unpinned context and measures {mib(pressure['cases']['raw_usage_released'])}MiB less raw usage; headroom reaches about848MiB and one real restore completes under the same retained pressure. This demonstrates a **conditional recovery opportunity**, not permission to evict production contexts or proof that such an eligible context exists in Granite's process. The manager currently trims excess warm residency after successful hydration; moving that earlier could discard an existing valid context when new hydration fails and needs ownership/background-work/persistence evidence. No scheduling/eviction change was made.

## Ranked options and customer impact

1. **Eligible idle-runtime lifecycle recovery, only when established.** This has the clearest measured practical effect:57MiB freed allowed the controlled request to cross the unchanged admission boundary. First establish actual residency, pinned/active requests and background ownership through authorized running-process evidence. Preserve active contexts and valid last-known data. Earlier eviction trades availability of an old warm context for a new one and may require expensive reopening. No production victim is established, so automatic pre-eviction is not a proven safe patch.
2. **Generation-bound, immutable public-catalog sharing across resident leagues.** The modeled raw/normalized graph offers tens of MiB per duplicate cohort, larger than actual-result adaptation. Existing mutable source views, per-publication provenance, identity corrections and source clocks must first be shown safe to share. It is a broader ownership contract, not a one-line deduplication correction. Same-priced or same-size catalogs do not prove compatible source identity.
3. **Narrow missing-template/derived persistence work.** Exact identical structures exist, but the graph bounds above do not prove publication-peak savings and mutable aliasing is unsafe. Any compact persistence must retain a full conservative expansion/admission basis and measure reconstruction/binding together. Compression or dropping derived bytes must never manufacture headroom by hiding later allocations.
4. **Retain truthful deferral until capacity genuinely returns.** This preserves safety but leaves access unreliable. The identity-detachment prototype is rejected. Lowering16×, subtracting arbitrary file cache, active-context eviction, blind retries or an infrastructure purchase are not justified by this study. A larger plan is not established as technically necessary; no plan change occurred.

The supplied November6Granite sample35,531,769/670,416,896/702,726,032bytes remains historical. Its exact unchanged arithmetic still defers. The present paired measurements neither replace a fresh preflight nor establish the earlier503cause or current admission state. No release is warranted solely from these fixture savings or a diagnostic refinement.

## Validation and evidence status

- New application-focused regression:63passed on current shipping source, including cache/parser, source binding/rendered consumers, admission, cancellation/timeout and league-entry controls.
- New comparison-integrity regression:12passed, including rejection of digest/source/instrumentation mismatches, incompatible payloads, changed publication values, wrong limits, OOM and incomplete cleanup.
- Primary measurements:24completed restorations /12matched pairs /fourretained fixtures /threerepeats. Complete source/payload/digest equality is required; a deferral is never counted as completion.
- Separate pressure case:one safe deferral, explicit fixture-owner release and one completed recovery; no production eviction.
- Existing build2237full release evidence is reused **only because the exact application tree is unchanged**:4,250local and4,250hosted tests, ten gates each,640/644manifest entries and12required hosted jobs. Latest job outcomes and original hosted ZIP SHA are rechecked. Those full suites are **not new executions** for this continuation. [Reuse receipt](results/baseline-validation-reuse.json).
- All original records are preserved. Early pair1is excluded from final medians; graph-contaminated cleanup is not presented as clean lifecycle proof. A setup import-path error and browser UNAVAILABLE result are separately described in [attempt qualifications](results/attempt-qualifications.json). Original logs were not recreated.

No application diff exists, and there is no new PR/tag/build/deployment to review. The current build2237release remains immutable. Sleeper-only exact results/projections, zero/negative/missing/conflicting handling, source/scoring/season/generation boundaries, neutral/Custom separation, submitted lineups, exact picks, historical provenance, account isolation and all existing memory/lifecycle policies remain unchanged.

[Readable original logs](LOG_INDEX.md) · [full methods](METHODS.md) · [complete Scout acceptance](SCOUT_HANDOFF.md) · [checksums](SHA256SUMS). The live leg remains unresolved rather than being substituted by fixtures.
'''
(r/'README.md').write_text(text)
(r/'CORRIGENDUM.md').write_text('''# Measurement corrigendum; immutable evidence preserved

The build2237 original `profile-combined.py` candidate mode also patched `engine._semantic_digest` to a streaming helper. Plain mode did not. Its earlier decoder-only description is therefore unsupported by that comparison. This is a methodology correction, not a discovered production digest change or failed application gate.

The original immutable release, profiles, scripts and bytes remain unchanged and are referenced with their original hashes in original-measurements-preserved.json. New decoder-only results use the exact deployed source, identical payload/digest/instrumentation/environment and complete resulting publication equality. They are new disposable measurements, not recreated original logs or Granite measurements.

The new12matched-pair results broadly support a similar sized decoder effect in these controls. They do not retroactively isolate the old captures or establish Granite recovery, a private restoration peak, the earlier503cause or live Sleeper parity. See README.md and verified-summary.json for exact counts and qualifications.
''')
