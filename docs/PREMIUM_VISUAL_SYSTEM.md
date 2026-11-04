# DTOS v1.14.0 visual system — implementation ledger

Baseline: v1.13.7, a5b5da90fa6604e77b2e902df27378a3c4866aa3.
The two user-supplied screenshots govern the whole product, not only Trade.
iPhone/editor controls and example player data are not product requirements.

## Boundaries

Presentation only: preserve canonical assessments, values, evidence, freshness,
authorization, account/league/franchise isolation and provider-free requests.
Current Visual, DINS and External Visual Mirror remain retired.

## Audit findings

- Shared styling had three competing sequential design-system definitions.
- Repeated oversized page/feature headers delayed primary content.
- The account switcher occupied a permanent large panel and grew with membership count.
- Home signal rows showed directional arrows but had no destinations.
- Mobile header actions were hidden wholesale, including useful primary actions.
- Player portraits were small circular thumbnails; the reference favors stronger identity.
- Specialized Trade/Team HQ styles needed composition migration; a shared palette
  alone was not acceptance.

## Implementation phases

- A: shared tokens, compact shell, accessible league disclosure and SVG navigation — implemented and locally audited.
- B: bilateral offer cards, real player links, native offer details — implemented; focused dynamic workflow checks passed.
- C: franchise portraits, canonical assessment before lineup, roster/pick styling — implemented and locally audited.
- D: compact Market summary, filter-preserving pagination, stronger player dossier — implemented and locally audited.
- E: linked visual standings, season cards, pick assets, mobile activity rows and safe matchup franchise links — implemented; local browser and history checks passed.
- F: ranked manager identity, score/confidence hierarchy, subordinate integrity diagnostics — implemented; populated profile locally inspected.
- G: Home action signals, reduced repeated introduction, shared Commissioner and account/settings treatment — implemented; local route/interaction checks passed.
- H: local authenticated real-router journey passed on 18 surfaces across two accounts, three leagues, mobile and desktop. Live production audit remains a post-deployment gate.

## Shared strategy

`src/ui/theme.py` owns canonical tokens and shared component layout. Existing
variable names alias those tokens for specialized renderers. No frontend framework,
font download, or new runtime dependency. Compact page headings preserve useful
mobile actions; the five existing destinations remain fixed at the mobile bottom.
Account switching uses a native disclosure with unchanged authenticated POST/CSRF
forms, keeping all memberships available without eagerly loading league runtimes.

## Interaction corrections

| Element | Expected destination | Correction |
| --- | --- | --- |
| Home ranking signal | League briefing | Real anchor |
| Home roster/pick signal | Active franchise assets | Real scoped anchor |
| Home trade signal | Active franchise Trade Center | Real scoped anchor |
| Account league switcher | Existing membership activation | Compact disclosure, unchanged forms |
| Trade player identity | Canonical player dossier | Real player anchor |
| View trade details | Evidence for this offer | Native disclosure rather than blank builder |
| Market pagination | Same filters and franchise | Context-preserving query |
| Matchup franchise | Known Team HQ | No fabricated team-zero link |
| FOIS identity | Same-league executive profile | Real profile anchor |
| League standings | Corresponding Team HQ | Whole franchise row |

## Evidence

Focused evidence (not a final candidate gate):

- Obsolete 190px test replaced after real Chromium layout checks at 320/390/768/1280/1600 widths: no overflow, actions visible, 44px controls, disclosure usable, content flow and mobile safe-area clearance preserved.
- Shared design + visual contracts: 18 passed.
- Authenticated real-router browser journey: passed across two accounts, three leagues and mobile/desktop; provider calls forbidden.
- Canonical Team Assessment + design + navigation: 25 passed.
- FOIS presentation + navigation: 15 passed.
- Market read-cache + navigation: 17 passed.
- Python compilation passed for presentation components/routes.
- Earlier focused batch had one obsolete CSS-rule-order expectation; replaced with the actual single-column responsive contract and reran the affected tests successfully.
- A temporary preview launch without repository import path failed before startup; restored the diagnostic process environment, with no product change.
- Expanded browser audit initially found provider-table overflow on player dossiers in every mobile league context. The provider table now has a keyboard-focusable horizontal scroll region; the annual history table already had correct containment. Recheck: transaction tests plus expanded browser journey, 7 passed (51.747s).
- Commissioner Desk now uses the shared authenticated shell. Its obsolete test required the removed independent JavaScript sync action; replacement proves exactly one CSRF-bearing sync form and one primary navigation. Eight tests passed.
- Trade browser/builder/repair/intelligence focused suite: 26 passed (24.145s).
- History archive/progress focused suite: 17 passed.
- Account presentation/visual focused suite: 13 passed.
- Touched presentation files pass Ruff and whitespace checks. Public CSS export is explicit, retaining import compatibility.
- Manual local browser inspection covered Home, Trade offers and workflows, Team HQ, League, Market, player dossier, picks, matchups, populated FOIS/profile, Front Office and Commissioner Desk, with small-phone/mobile/desktop views. Synthetic fixture portraits validate composition, not real player photography. Production visual judgment remains required.

The first full regression ran 1,359 tests in 525.561s and retained 17 failures:
three hardcoded prior-release metadata assertions; retired player-title and
icon-free navigation markup assertions; and twelve Trade accessibility subcases
that attempted to focus a disclosure inside the intentionally hidden pre-evaluation
assistance panel. Corrections use centralized metadata, the new player identity and
decorative-icon navigation contracts, and explicitly test both hidden and visible
post-evaluation panel states. No product semantics or thresholds changed for these
test corrections. Focused revalidation precedes the canonical pipeline.

The corrected candidate then passed all 1,359 regression tests inside the canonical
validator (520.427s), compilation, Ruff, dependencies and routes (250 registrations,
234 OpenAPI paths, zero duplicates). HTTP smoke rejected only the retired Market
marketing headline; startup and process cleanup passed. The revised Market smoke
contract requires a GET form targeting `/market` with query, position, availability
and sort controls, while retaining the dataset/evidence checks. Missing controls and
incorrect destinations fail closed. Focused design/warming validation: 25 passed.
The earlier metadata recheck also exposed two stale build-number assertions, now
bound to centralized build metadata; both rechecked successfully.
Focused tracked HTTP recheck passed startup, full smoke, graceful shutdown and
process cleanup (run `606aaaa7106f456d99ef1c1b8bf2d48c`). The final canonical sequence
now validates the complete corrected tree; earlier red logs remain preserved.
The following canonical attempt exposed two ambient-storage fixture errors
(`sqlite3.OperationalError: unable to open database file`): historical search and
secondary runtime publication used the process-global default FOIS repository.
Both fixtures now own real temporary FOIS storage and explicitly reject calls to
the ambient database-path factory. Secondary projection storage is temporary too.
The affected modules passed 31 tests in 3.517s in the same execution environment.
No production database or FOIS implementation changed.

The next canonical run passed 1,359 regression tests (483.247s) and all preceding
gates, then exposed the same ambient FOIS database access failure in HTTP startup.
Read-only diagnosis found the shared temporary file owned by a different local
sandbox identity; no permissions or existing data were changed. The HTTP worker
now owns its default temporary FOIS and checkpoint stores through server teardown,
including forced child shutdown, while explicit database/storage-root overrides
remain authoritative. A subsequent focused HTTP attempt exposed an obsolete
unique semantic-fingerprint constraint in the ambient local checkpoint database;
the same synthetic 100→200→100 sequence succeeds with the current fresh schema.
This is validation-state isolation, not a production schema migration.

Focused startup succeeded, but Market remained warming beyond the unchanged
60-second readiness deadline in two retained HTTP diagnostics. The first included
the default 30-second background delay; the immediate-kickoff diagnostic used the
same `DTOS_BACKGROUND_START_DELAY=0` fixture setting as Linux, without skipping
canonical work or changing latency limits. Final focused HTTP proof with both
current run-owned stores is pending. Seventeen storage/lifecycle tests passed,
including override preservation, current schema, unique run paths and cleanup.
An initial test reader was corrected to close its SQLite connection explicitly
before Windows directory cleanup. Disposable failed-run databases were removed;
existing shared databases and non-sensitive diagnostic logs were preserved.

The startup-only diagnostic localized the continuing readiness delay to
`sleeper_sync`: at 80.73s the startup fence still awaited canonical synchronization,
with zero builds and FOIS generation inactive. Logged Sleeper HTTP responses were
successful; synchronization completed about 92s after those responses. This does
not establish a network failure or a visual-rendering cause.

The diagnostic then exposed a real validation cleanup bookkeeping defect:
untagged multiprocessing descendants survived their run-tagged server, and the
server-only process check missed them. Two children were correlated to their
recorded parent PIDs and stopped; their disposable store was removed. The tracked
server now remembers owned descendants before parent exit, verifies complete
teardown, and refuses unrelated/reused process identities. Thirty-five focused
storage/lifecycle/process tests pass. The next focused HTTP proof starts without
those orphaned workers. No startup or intelligence implementation was modified.

After the cleanup correction, the clean-process HTTP run still exceeded the
60-second readiness deadline. A 20-second stack-only diagnostic identified
`services.sleeper._sync_sleeper → player_history_evidence → records → _season_records`:
the same historical season chain was being expanded once per rostered player.
The narrow correction batches that read once per league/synchronization and
preserves per-player ordering, full counts, the 1,000-row aggregation boundary,
missing evidence and source metadata. No schema, scoring formula, provider
behavior, durable cache or intelligence semantics changed. Sixty focused history,
equivalence and runtime-isolation tests passed (3.499s); Ruff passed. The bounded
stack diagnostic and corrected teardown left no orphaned Python processes.

The batched-history HTTP proof still failed the unchanged 60-second Market
readiness gate. Synchronization now reached FOIS about 16.25s after smoke start;
the compute child remained active until cleanup. A separate 40-second stack-only
diagnostic localized cold FOIS work to historical trade evaluation → franchise
state reconstruction → nearest market checkpoint → global checkpoint reads,
including repeated SQLite connection/WAL setup. Read counts and a safe
generation-scoped reuse policy are not yet proven. No FOIS/checkpoint-reader
implementation was changed. Final canonical/CI/release/production acceptance
remain blocked; no commit, push, PR, tag or deployment has occurred.

Live local previews use isolated synthetic accounts and deterministic fixture images, not production data.

### Authorized FOIS checkpoint performance correction

The user authorized this narrow correction within the unreleased v1.14.0 candidate.
One read-only SQLite snapshot spans the FOIS compute flight. Its bounded LRU stores
only canonical global checkpoint projections (1,024 entries / 8 MiB serialized
evidence maximum), not historical evaluations or private league state. The same
projection helper serves cached and uncached reads; per-event/as-of/direction,
league/franchise/transaction and evaluator-method selection is not cached or changed.
The portable generation hashes observation fields plus reference trigger/knowledge
evidence and schema/read-contract versions, in explicit order. It is streamed,
not a retained database copy. SQLite data_version on the same connection fences
concurrent writes; it is not used as a portable generation. Changed evidence rejects
the flight, and the parent verifies the content generation again before publication.
All flight state is discarded on success/failure; no cross-flight cache survives.

Focused correction evidence: 67 tests passed in 18.666s, including historical
equivalence/no-hindsight/missing evidence, distinct event/as-of/league/franchise
inputs, observation/reference/method invalidation, concurrent-write rejection,
bounded eviction, restart/cross-process deterministic generation/output, and
last-valid publication preservation after a generation change during IPC. Ruff passed.
Early new-test failures were fixture issues: an unchanged semantic event ID was
correctly deduplicated rather than introducing a new checkpoint, and narrow import
order bypassed the established application initialization boundary. Both corrected;
no evaluator semantics changed. Prior failure evidence remains retained.

Cold focused benchmarks (not full release acceptance):

| Shape | Cold process | FOIS compute | Step 4 | Checkpoint storage reads / reuse hits |
| --- | ---: | ---: | ---: | ---: |
| Established Linux fixture: 12,322 assets, 30,726 player events, 231 trades | 30.557s | 29.019s | 8.283s | 0 / 0 (historical fixture rosters have no asset lists) |
| Retained multi-season facts with 1,376 isolated synthetic market checkpoints | 16.008s | 14.293s | 12.293s | 655 / 26,557 |

Both produced 10 assessments and evaluated 231 trades, with zero provider calls/raw
request-history scans. The populated-evidence flight retained 831,430 serialized
bytes; child RSS at completion was 132,956,160 bytes (not a measured peak).
Temporary fixture stores were removed. The initial populated diagnostic label
`historical_trades=1985` counted all canonical transactions, not trades; the
231 evaluated-trade metric is authoritative and the diagnostic label is corrected.
The earlier empty-checkpoint local startup diagnostic completed FOIS in 16.866s,
but included a sandbox-blocked Sleeper sync and overlapping focused tests, so it
is not used as an authoritative readiness/latency proof. No threshold changed.

No commit, PR, release, deployment, or production change for v1.14.0 yet.
The overhaul is not complete until all phases and required acceptance gates pass.

### Final-gate fixture diagnostics (retained failures)

The corrected FOIS product tree passed full regression in 499.357s plus compilation,
Ruff, dependencies, whitespace and route/OpenAPI checks (250 registrations, 234
paths, zero duplicate registrations). Canonical HTTP failed the unchanged 60s
Market deadline: the local fixture inherited production's 30s deferred startup,
then synchronization and 12.539s FOIS work left insufficient construction time.
The HTTP fixture now defaults to immediate kickoff, matching the existing Linux
fixture; explicit delay overrides and production defaults remain unchanged.

The focused HTTP follow-up exposed a separate Matchups timeout. Bounded route,
coroutine and pure-compute diagnostics localized this to durable market snapshot
serialization against an ambient 6,093,270-byte local warehouse. Main-loop handling
was not the stalled work. The same calculation with in-memory persistence disabled
completed each market stage in 14–28ms (diagnosis only); a fresh fully durable store
also completed, with final market stages 1.204–1.548s and 371,123 bytes persisted.
Validation now owns a fresh durable warehouse alongside its other temporary stores,
preserving explicit storage overrides and cleanup. No production persistence,
market evaluator, scoring, timeout or latency threshold was changed for this issue.
Seven focused fixture ownership/override/failure-cleanup tests and Ruff passed.
The earlier red canonical and HTTP events remain evidence, not successful gates.

Final local canonical validation passed all 10 gates in 678.837s: regression
528.506s, routes/OpenAPI 250/234 with zero duplicates, tracked full HTTP smoke
128.128s, and process cleanup passed. The preceding isolated HTTP proof also
passed all route groups with graceful cleanup (52438b98e8f848c284af7185a46e1308).
This is pre-release evidence only; Linux/PR and production gates remain required.
