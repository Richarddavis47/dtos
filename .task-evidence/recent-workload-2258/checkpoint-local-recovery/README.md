# Recent workload — exact-source local recovery

PR347 remains draft; production is unchanged. Candidate `ca685099dd6f7d95090fcee732f0ad3287a50ca6`, tree `4d455c93174f246f242f724e23de5fed44ecb4fb`.

All13required hosted jobs passed, including4555canonical tests/all10gates under2GiB; original manifests and15artifact checksums were independently verified. The first complete local run had4551passes and4errors after actual capacity deferrals. Its original records remain distinct. One matched4-case driver-budget pair passed under both settings, with lower driver footprint at128MiB; this does not reconstruct original full-prefix residency.

**The same-source full local rerun is RUNNING, not passed.** No release, merge or deployment has occurred. NEXT_ACTIONS.md identifies the durable controller and remaining guarded work. No app source, admission arithmetic, test assertions, timing thresholds or production setting changed during recovery.

Original consoles are split at UTF8 boundaries into <=60KB files. Concatenate each ordered manifest part list to reconstruct the exact original SHA256. No logs were reconstructed. Fixtures and public-source research are distinct from owner-live acceptance; no owner browser or physical Safari acceptance is claimed. Earlier focused source/screens are in the existing checkpoint-focused directory of this evidence branch.
