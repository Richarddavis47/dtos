# My Team roster need → Recommended Trades — build 2243

The implementation lets a manager carry one supported, current starter or replacement-depth need into Recommended Trades, review or change the position, and explicitly Generate. This is a scoped search preference, not a saved franchise strategy or a promise of a qualifying deal. This validation record is sealed before the guarded merge/publication sequence. It does not itself establish deployment; the separate final publication and production receipts identify the actual result.

## Source and confirmed gap

Verified baseline: v1.22.27 / build 2242, commit `d412c89cc2f3ca252f68f363e304eb2773863e97`, tree `ca1345adc5ede802e5a286c69892657d5e1abdc1`.

Final candidate: `e89178166fa2d90431666675487df85ad207f751`, tree `9a6fb02bd00b789f6566cfb59f70868972b3ed2d`, branch `feat/my-team-trade-need-2243`, draft PR [332](https://github.com/Richarddavis47/dtos/pull/332). Proposed version v1.22.28 / build 2243. A version increment in candidate metadata does not establish a published release.

Baseline source already had canonical positional need flags, general My Team Trade shortcuts, a Shop-only positional preference, and Recommended opportunity-type controls. It did not have the requested current prepared-need handoff into Recommended Trades or an incoming-position selector there. Asset-picker position filters only narrowed displayed assets. The implementation extends the existing request-only session-filter boundary; it does not replace Shop, generation, evaluation, scoring or eligibility.

## Customer behavior

- The authorized own franchise's currently supported canonical starter need takes precedence over a replacement-depth need. Existing position order and legal eligibility are reused; no new need score or strategy is inferred.
- My Team adds one contextual action such as **Explore RB trades**, with the supported week and a starter-versus-depth reason. Original general Trade shortcuts remain available. Missing, stale, failed-refresh or unmappable evidence supplies no guessed position.
- The destination reauthorizes membership and freshly qualifies the matching prepared diagnostic. A fingerprint binds existing account/session, league/franchise ownership, week and diagnostic/projection generations. It is context identity, never authorization.
- Recommended shows **Incoming player position**, a visible reason and a 44px Clear target. A fresh explicit handoff focuses the filter below the contextual Back bar. Change or clear requires no search. Only explicit Generate submits the filter.
- The filter applies to received players, allowing mixed player/pick returns. QB/RB/WR/TE reuse existing supported canonical player positions and actual FLEX/Superflex eligibility. K/DEF remain in legal lineup evidence; unsupported market positions use the general shortcut.
- Strategy, Neutral/Custom mode and the independent Evaluate draft are preserved. Editing opportunity type preserves the My Team position reason. Editing position changes its origin to manual. Reload preserves a manual override, including when the earlier hint has expired; a new stale handoff applies none.
- Up to eight original offer contexts are retained in bounded, existing tab storage, clearly separated as earlier/not revalidated. They are not relabeled as matching the new filter. Start New Trade clears this temporary context. League/account changes remain subject to existing scoped workspace authorization.
- The existing opportunity-type control remains editable while a search is pending. Its handler retires and invalidates the exact pending request, preserves the Evaluate draft, and prevents a late response from appearing under the new filter. No replacement search starts automatically.

## Verification scope

Final-source focused acceptance:24tests passed: ten new handoff controls, eight prior partner-history controls, the existing retained-history browser control, four real canonical-harness lifecycle controls and the original pending-response regression. The original existing stale-response browser journey plus ten new tests also passed after the in-flight filter correction. Four responsive sizes: 320×432, 375×667, 390×844 and 1280×900. Authenticated disposable source-compatible fixtures cover 1-QB/FLEX/K/DEF and Superflex, starter/depth, current/stale/missing/failed refresh, actual explicit evaluation, prior results, Custom/draft preservation, reload/Back, manual edits, reset and league switch. Keyboard/focus, touch emulation, 44px controls, unobscured label and zero overflow passed. Physical iPhone/Safari is unverified.

Three source-pinned enforced-2-GiB controls passed: metadata preflight, native-results restoration/unused-memory recovery, and resident-refresh ownership. Existing specialized publisher guards verified source identity and every relevant assertion. These disposable results do not establish production spare capacity or live Granite recovery. Full local/hosted results will be sealed separately only after their original consoles, gate traces and manifests are verified.

The new browser controls use real authenticated routes and the shared evaluator. They do not seed a successful recommendation or bypass resource admission. The retained Day Traders descriptive-history replay is a separate unchanged destination control, not evidence of a newly qualified live offer.

## Preservation

The source-object comparison in `preservation-review.json` verifies 18 protected boundaries byte-identical to baseline: canonical intelligence/evaluator, projection service, Market/valuation, FOIS, lifecycle/admission, Sleeper, player evidence, league preparation, rankings, strategy session, history, calculator, workspace identity, Shop and bounded search policy. The only evaluation-path change is the requested incoming-position session filter; final bilateral verdicts, candidates/caps and independent evaluation are unchanged. Position-filtered results do not replace the broad Home opportunity cache.

No new provider calls, source database, anonymous preparation, worker, background search, polling, runtime admission reserve or infrastructure was introduced. The 2 GiB cap, Trade 256+128 MiB and FOIS 768 MiB policies remain unchanged. Submitted lineups, exact picks, saved settings and source evidence are untouched. No production sync, FOIS rebuild, Trade search, preference/ranking/goal/lineup mutation or real trade submission was performed.

## Failures and qualifications

Original failed precommit fixture/scope/readiness assertions, lint attempts, superseded phone placement/Back-bar findings and transition controls remain separate. Canceled full suites are not passes. A preliminary exact-source launch stopped at the unchanged 8 GiB scratch prerequisite before tests; a later launch omitted observer wiring and was stopped as incomplete. No permissions, resource limit or assertion was weakened.

Both d30 and c6 hosted Product runs completed with the same two errors in the existing 390/1280 stale-response journey: the newly disabled opportunity-type control could not be changed during generation. Their original complete logs are retained. An earlier note mistakenly called d30 successful because a cancellation request said it had already completed. Original job records establish FAILURE; the inaccurate note is preserved with an explicit correction. The application handler, not the assertion or admission policy, was corrected in final candidate fa321bc1.

The first superseded source's Linux ordinary lifecycle attempt failed a 2,891.658ms body handoff while FOIS was active. Its exact cause remains unresolved; memory was below the 2 GiB cap and OOM counters were zero. One bounded rerun of that failed job with unchanged controls passed; subsequent sources' three Linux modes passed on first attempts. That result is not claimed as a universal latency fix.

An earlier CLI/API GitHub request returned HTTP 401. After the environment resumed, the existing approved authorization worked through supported gh authentication status and ordinary API reads. Its earlier failure cause remains unproven. No credential was created, exported, rotated or relayed. Release assets use only the established guarded Actions GITHUB_TOKEN publisher, with preparation, byte readback, expected-head merge and immutable publication kept as separate guarded phases.

Private owner-browser acceptance is unavailable in this session: no Work-mode browser controller/authorized app session or Render Shell is exposed. Public readiness and source/deployment metadata are separate observations. The pre-existing external DTOS inspection 401 was not retried. Fixture acceptance must not be presented as authenticated live owner acceptance.

## Canonical CI deadline and evidence correction

The prior fa321bc1 hosted run completed4188/4326tests without a recorded assertion failure before the4500second wrapper timeout; only six canonical gates completed. It is a failed/incomplete result. Matched test/occurrence timing was1.568xlocal; remaining138tests took37.8local seconds (about59seconds at the observed ratio, an estimate not a completion claim). No OOM was recorded. The wrapper killed only the validator parent, allowing its test child to write briefly after manifest generation. The original ZIP outer API digest/CRC are valid, but its original tests.jsonl and unittest-console.log do not match the original inner manifest. Those bytes and mismatches remain preserved without repair.

E891gives the complete unchanged validator80minutes inside the existing85minute job, with an82minute step, while keeping every application timeout/assertion and2GiB/two-CPU/network-none limit unchanged. It stops/reaps its owned group and captured detached descendants on timeout before sealing evidence. Four focused controls prove actual execution, nonzero failure preservation and real detached-writer timeout cleanup with stable subsequent hashes. Complete final-source validation is required anew. This does not change production cancellation, FOIS/Trade reserves or lifecycle policy.

The environment resumed with working existing CLI authorization. Supported authentication status confirmed the expected owner and normal Actions reads succeeded; the exact earlier401cause remains unproven. No credential creation/export/rotation or authentication-policy change occurred. A CLI log redirect separately received403 at its storage destination; the existing GitHub connector retrieved the original215629byte log. The failed transport is distinct from the actual canonical timeout.

## Sealed exact-source final validation

Observed 2026-11-10T03:19:19.888982+00:00. This section records completed validation before guarded publication. The separate final deployment receipt is authoritative for release status.

| Scope | Result |
| --- | --- |
| Clean writable local Python 3.14.3, enforced 2 GiB / two CPU / network none / UID 1000 | 4,330 completed tests, 10/10 gates; 672 SHA-verified original manifest entries; 2894.839s |
| Hosted exact-source canonical | 4,330 completed tests, 10/10 gates; 658 SHA-verified original manifest entries; 4656.699s |
| Hosted required jobs | 13/13 passed: canonical, Product, My Team, beginner navigation, Welcome/security, historical timeline, projection cross-version, resident refresh, Ubuntu/Windows tooling and all three Linux lifecycle modes |
| Product / separate Welcome-security executions | 831 (657 + 35 + 139) / 412 passed, original complete consoles retained |
| Focused / publisher | 24 final-source focused tests / 68 scoped publisher controls, lint, compile and permission/source review passed |
| Phone / touch | Four sizes and three CDP touch sizes passed; physical iPhone/Safari not tested |
| Artifact integrity | 15 original GitHub ZIPs match API size/digest, ZIP CRC and all specialized source-bound guards |

Local kernel lifetime peak: 2122182656 bytes; hosted: 2131144704 bytes. OOM and OOM-kill counters were zero. These include disposable validation workloads/pressure; they are not proof of spare production capacity. Original per-stage samples, process records, cleanup and qualifications remain in the archive. Test repetitions are execution counts, not a claim of that many unique cases.

Local and hosted artifact populations differ by output capture: local has 18 additional partner-history reports/screenshots enabled by its documented capture variable; hosted has four environment/build/bytecode files absent locally. Both original manifests are independently verified. The hosted Welcome artifact separately contains the source-bound partner-history captures. See local-hosted-manifest-reconciliation.json; neither inventory count substitutes for completed tests.

Original workflow results:

- [Canonical release recovery](https://github.com/Richarddavis47/dtos/actions/runs/42739412855)
- [Product browser journeys](https://github.com/Richarddavis47/dtos/actions/runs/42739412871)
- [Validation tooling](https://github.com/Richarddavis47/dtos/actions/runs/42739412821)
- [Linux Asset Market lifecycle](https://github.com/Richarddavis47/dtos/actions/runs/42739413077)

Earlier original failures, cancellations and incomplete attempts remain separately qualified in PRIOR_ATTEMPTS.md, Prior-attempts.zip and the byte-verified [prior-originals snapshot](https://github.com/Richarddavis47/dtos/tree/480da5e97a793d167c2ca68be3a01b9796f6b7f2/.task-evidence/my-team-trade-need-2243-prior-originals). No original failed inner manifest was rewritten.
