# Batch 4 release acceptance — v1.18.0 / build 1800

## Implementation freeze

Implementation is frozen for required validation. Later changes require a concrete
gate failure, focused correction and identification of invalidated evidence.
The working candidate is on `codex/v1.18.0-fois-pick-intelligence`; no release/tag
or production deployment is claimed. v1.17.2 remains immutable.

The canonical repository validator contains ten steps, including full regression,
routes/OpenAPI and tracked HTTP startup/smoke. It is run once rather than running
an immediately duplicated standalone regression first. Linux ordinary,
archive-warmed, combined-read and lightweight browser remain separate required
pre-deployment gates. Corrected live proof necessarily follows deployment.

## Bounded implementation checklist

| Boundary | Evidence / implementation status |
|---|---|
| Results, playoff qualification/byes and season structure | Accepted source-backed Results panel; Richard 5 completed seasons, 4 playoffs, 3 byes, 3 Final Fours, 1 final, 1 championship; Results 86.52/B only |
| GM tenure and franchise continuity | Accepted active attribution and two-league proofs; seasonal precision remains disclosed |
| Trading process/outcome | Active supported magnitudes and limitations; volume is sample, not quality; outcomes do not rewrite process |
| Drafting | Exact timestamp limitation remains honest; unsupported process/alternative grades unavailable |
| Waivers | Successful actions only; unknown FAAB distinct from source-supported zero; scoped process/outcome evidence |
| Roster Construction | Historical references retain anchor precision; unavailable dimensions not graded negatively |
| Quality/confidence/strengths | Active category aggregation, minimum supported categories, explicit provisional composite, unavailable categories not weaknesses |
| FOIS cross-league | Accepted active Day Traders and bounded Super Flexxxin decision panels; no new export required |
| Pick identity/ownership/history | Accepted 120/90 production ownership reconciliation; original franchise separate from current owner; transfer return chains preserved |
| Pick Market | Prepared compatible external quotes, source-adapter round correction, shared scale, generic/range/exact identity and unavailable safeguards |
| Range/confidence | Shared source-bound interval admission; UNKNOWN/LOW on present real evidence; no Market/current-owner forecast; exact slot requires established evidence |
| Range history/storage | Bounded semantic transitions, methodology reasons, zero-growth unchanged replay |
| Portfolio | Year/round/original-franchise/range/confidence distributions; no legacy scalar |
| Prepared reads/parity | Source-backed authenticated candidate A→B→A exact fingerprints; local 16–20 ms; preparation measured separately |
| Legacy score sweep | Active Pick scalar outputs removed; Trade acquisition prices preserved; 47 affected tests passed |

Detailed evidence: `BATCH4_ACTIVE_QUALITY_PANEL.json`,
`BATCH4_SECOND_LEAGUE_ACTIVE_PANEL.json`, `BATCH4_PICK_HISTORY_AND_PARITY.md`,
`BATCH4_PREPARED_READ_CHECKPOINT.md`, `BATCH4_PREPARED_PICK_READ_PANEL.json`.
Older progress documents contain chronological open-item lists superseded by
these accepted checkpoints; they are not new unresolved implementation findings.

## Pending acceptance

- Canonical ten-step validator, Linux three scenarios, lightweight browser.
- PR, immutable tag/release and deployment.
- Production disk admission before explicit FOIS/Pick publication/backfill.
- Corrected live Picks timings and full semantic multi-league parity.
- Active production FOIS/Trade/Team HQ/Brain/Competitive Window checks.
- Bounded growth, unchanged replay, controlled restart and post-restart reuse.
- Cleanup and synchronized tracked main; preserve Richard's reference files.

Batch 4 is NOT COMPLETE. Batch 5 is NOT STARTED.

## Pre-deployment read-only disk baseline

Existing Render service: `srv-d9ctp8navr4c73agtnrg`, My Workspace, standard plan,
one instance, 2 GiB disk mounted at `/var/data/dtos`, auto-deploy main enabled.
No infrastructure setting was changed. Dashboard Shell initially failed to fetch;
one refresh restored the existing shell. No SSH key, export or helper was created.

Read-only stdlib filesystem measurement on 2026-09-13:

- Filesystem total: 2,077,073,408 bytes.
- Used: 1,013,264,384 bytes; free: 1,047,031,808 bytes.
- Available inodes: 130,752.
- FOIS: 149,123,072 bytes.
- Projection store: 340,770,816 bytes.
- Global evidence: 115,113,984 bytes.
- Intelligence checkpoints: 12,226,560 bytes; WAL 0, SHM 32,768 bytes.
- Metadata (Pick range history target): 49,152 bytes.

This is a baseline, not final expected-write admission or post-release growth proof.
No database was opened or changed for this measurement. Because merging triggers
deployment, storage admission must be resolved before merge rather than assuming
that automatic startup will wait for a later manual publication command.

Bounded two-league publication estimate (not a guarantee): accepted derived manager
reports total 2,380,887 bytes. Allow twice that size plus 1 MiB for 210 compact Pick
states/index overhead: **5,810,350 bytes logical allowance**. No new canonical source
payload copies are part of this operation. For conservative admission, additionally
reserve twice the entire current FOIS file (298,246,144 bytes) for staging/WAL overlap,
plus 128 MiB temporary allowance and the existing 128 MiB disk reserve used by the
repository backfill admission pattern. Total allowance: **572,491,950 bytes**, below
the observed 1,047,031,808 bytes free by 474,539,858 bytes. This is an allowance, not
a proposal to copy the full FOIS database. Actual league-scoped publication remains
bounded and transactional. No global NFL re-backfill is authorized by this estimate.
Refresh free space before merge/publication if the validation interval materially
changes the baseline, and measure actual growth/replay afterward. Stop on an
unexpected write pattern rather than consuming the allowance blindly.

## First canonical validation and focused corrections

The first canonical run stopped at regression: 1,784 tests in 426.248 seconds,
7 failures and 9 errors. No merge/deployment occurred. The preceding six gates
passed. Focused reproduction classified the failures as stale fixture/contracts:
missing original-franchise IDs in Team HQ fixtures; repeated placeholder pick
identities; retired internal pick curves/range ranking; Results-only overall FOIS;
activity-only Trading grades; and guaranteed recommendations without supported
benefit. Tests now enforce the accepted explicit unavailable/evidence semantics.
Canonical duplicate-identity rejection and recommendation gates remain unchanged.

The browser fixture selected an unpriced pick and incorrectly required a completed
valuation. It now proves both the honest unavailable response with retained proposal
and successful valuation after fixture-only external generic quote publication.
Both mobile and desktop still exercise editing, retention, ownership change and
navigation. Focused 81-test reproduction left only a tuple/list assertion mismatch;
the corrected affected 10-test Trade/browser run then passed. Application source was
unchanged by these test corrections. Full canonical recheck is required and pending.

## Local required-gate results

Canonical recheck `42efdcb13a934207bbf6c0c65978fd2d` passed its first eight steps,
including full regression (409.531 seconds) and routes/OpenAPI (252 method
registrations, 234 paths, no duplicates). HTTP then failed on Windows progress
snapshot replacement (`WinError 5`), not a demonstrated route-contract error.
An uncoordinated direct progress-file read overlapped diagnostic publication;
future inspection must use the existing lock-aware reader. Failure evidence is
retained in `.validation/batch4-canonical-recheck.log`.

That failure exposed a cleanup defect: diagnostic recording could throw before
server teardown. The validation-only worker now records I/O failure as a failed
gate while still executing cleanup; 35 focused storage/progress/lifecycle tests
pass, including injected permission failure and required teardown. No product
code or acceptance threshold changed. The exact orphaned run was stopped through
its existing shutdown control; run-scoped and subsequent general process checks
confirmed no server remained.

Only the invalidated HTTP gate was rerun, as allowed by the requested evidence
reuse policy. Run `99bbd4c9f76e42ef9477e6d7708ab8e2` passed startup (13.280s),
HTTP smoke (47.130s), cleanup (13.403s, graceful), and process verification.
Final separate process check also passed. Focused compilation/lint and whitespace
passed after the worker correction. Thus all ten required local step contracts
have passing evidence across the canonical run and focused rerun; this is **not**
a claim that one uninterrupted canonical invocation passed ten steps.

PR Linux/browser and all corrected production acceptance remain pending.
