# Completed franchise trade observations — sealed validation

The existing Franchise History page now leads with a compact factual summary: completed trade transactions, first-round pick transfers acquired and sent, the number of trades containing those transfers, observed completion dates, sample size and coverage limits. Supporting original trade links remain in an accessible disclosure. Missing history remains unknown. This is not a manager-intent model or a Trade/FOIS input.

Baseline v1.22.25/build2240: `55eeb20f27c7e3380c1c4f70e3f2151a7ea1d5e8` / tree `f620d835c7b687d79d602ee5304f328aae95edef`. Candidate `8355f19a0ae89ad8ceaee17a1e89f3d586be9660` / tree `d8ee85a9fe6b9f54c3bd31140fa2f9c8267dcd7f`. PR https://github.com/Richarddavis47/dtos/pull/330 . Target v1.22.26/build2241. This report seals validation before merge; native publication and production receipts establish final release status separately.

## Existing behavior and useful gap

League and Team HQ already expose source-qualified franchise trade participation, aggregate supported pick transfers, coverage, historical owner qualifications and sampled references. FOIS and Trade Center retain separate prepared evidence and scoring. Those features were audited and preserved.

Franchise History had the stronger source-linked transaction timeline, exact pick directions, season coverage and ambiguous continuity handling, but no compact first-round transfer/deal summary or completion-date window across all timeline pages. One display-only accumulator extends that existing factual pipeline; it does not create another history or intelligence engine.

## Real retained replay, fixtures and live boundaries

The existing October12,2026 read-only Sleeper capture `tests/fixtures/trade_timeline_sources.json` has SHA256 `012de53aeefa4cfb4cb7de717910fa829f399b23d6f6ad7962598afe8c76833f`. Its partial Day Traders sample contains two completed trades. Canonical replay for franchise4 supports two observed completed trades, three firsts acquired in one trade and one first sent in one trade. Completion timestamps span March1 to October11,2026. Received exact picks include PICK-2026-R1-ORIG8, PICK-2027-R1-ORIG7 and PICK-2028-R1-ORIG7; sent includes PICK-2026-R1-ORIG5. Original franchise does not become its sending/current owner. Source references include1333655835015942144 and1414718106177122304.

The Arkham capture contains no completed trades but partial source acquisition: its rendered totals are unknown, not zero. The separate Day recent-news capture overlaps a transaction and is not added as independent activity. The older22-trade source capture has eight first-round transfers in seven transactions; raw source coverage alone does not prove every older roster's continuity with today's franchise. These bounded screens are not fresh live observations or complete seasons. `retained-coverage-screen.json` preserves each capture's distinct source hash, count and window.

The five recorded matched cases compare retained Day expectations directly against original source rows, plus explicitly disposable multi-team, partial-pick, supported-zero and unknown-history controls. Synthetic linked seasons exercise ownership changes, duplicate records/legs, unlinked identities, future/unknown clocks, failed refresh, pagination and cross-league/account isolation. They are never presented as newly acquired historical facts. No source provider was called.

## Counting and qualification

The accumulator consumes the existing canonical timeline archive and completed-movement admission before pagination. Source-league plus transaction-ID conflicts remain withheld. A relevant franchise counts one completed transaction, regardless of asset count. A multi-team exchange preserves sender/receiver and each pick's year, round and original franchise. Multiple firsts are multiple asset transfers but one deal; duplicate identical legs collapse. A later completed movement of the same exact pick is another transfer. All supported first-round pick years are included, and same-season picks are not silently called future capital.

Pending, rejected, cancelled, unknown-status attempts, waivers, non-trade corrections and draft selections are excluded from the completed-trade sample. Linked season continuity, observed franchise identity and supported membership are required. Unlinked/unconfirmed records are excluded with a count and reason. Incompatible source seasons and changed source revisions cannot publish a coherent numeric summary.

Pick counts can be zero only when exact-pick consideration is complete within the observed sample; unknown missing consideration cannot produce zero. Positive partial counts remain lower bounds. An empty history supports zero only under complete compatible source coverage. Undated completed trades contribute to their observed season sample, not an invented date range: the UI exposes the dated-trade denominator. The observed completion date span is not proof that every intervening source period was acquired. Season cards retain acquired/missing/failed and last-valid qualifications.

Every new observation is explicitly franchise history. A manager change does not backdate behavior to the successor. Exact takeover timing, present intent, willingness, acceptance probability, motives and historical decision quality remain unestablished. FOIS remains RETAINED / NOT REVALIDATED.

## Surface and resource preservation

Only services/franchise_timeline.py and src/ui/franchise_timeline.py implement this feature, with regressions, release metadata/docs and its hosted test inclusion. Protected source paths are byte-unchanged: Trade qualification/counterparty scoring, Neutral/Custom math, Sleeper-only results/projections, scoring/optimizer/eligibility, exact picks, submitted lineups, saved preferences/rankings, accounts, FOIS formulas and lifecycle/admission.

It reuses already-read prepared history with constant counters, at most12 trade references and at most4 listed exact picks per direction per reference. Full existing events and pagination remain below. No new provider request, page-render source acquisition, sync, FOIS generation, Trade search, worker/lease, permanent source database or heavy preparation. The2GiB cap, restoration16×, FOIS768MiB and Trade256+128MiB policies are unchanged. Existing normal-entry middleware can still defer a cold context; this feature does not bypass it.

Actual existing routes/theme in Chromium cover320×432,375×667,390×844 and1280×900. Eight retained-replay/controlled source records prove counts versus unknown, visible primary facts, keyboard/focus, emulated touch,44px targets, no horizontal overflow, no disclosure request and contextual Back from a supporting trade to the same History origin. The original separate History→trade→pick→player→later trade journey remains required and passes. Physical iPhone/Safari and comprehensive screen-reader acceptance are unverified.

## Final mandatory validation

- Final committed feature/browser controls: **18 tests**. Broader **106** preliminary executions are preserved as precommit, not relabeled final source validation. The final browser/feature records carry exact head/tree and clean-source identity.
- Local Python3.14.3: **4,308 tests**, zero failures/errors/skips, **all ten canonical gates**, 654 manifest entries checksum-verified. Clean writable checkout, UID1000, real2,147,483,648-byte cgroup, no extra swap, two CPUs and no external network. Lifetime kernel peak 2136805376 bytes; elapsed 2977.0s. Full-suite peaks do not establish spare production capacity.
- Hosted canonical: **4,308 tests**, all ten gates, 658 manifest entries, original ZIP/API digest/size/CRC and every payload verified. Kernel peak 2081431552 bytes; elapsed 4316.7s. All **13 required hosted jobs** passed; Product recorded **821** executions (647+35+139). Product, My Team, Welcome/security, navigation, timeline, projection cross-version, Linux/Windows tooling and all three Linux lifecycle modes remain distinct evidence.
- Three final-source local native controls and fourteen original noncanonical hosted archives satisfy exact-source specialized preflight, actual completion, deferral/recovery, cancellation/timeout/worker/scratch cleanup and resource/liveness guards. Native Sleeper0/-2.125 are preserved. Deferred operations are not counted as completion. These disposable controls do not prove live league entry or spare current capacity.
- Tooling-only publisher: **53 guards**, compilation, lint, workflow semantics and final frozen-plan evidence verification pass locally and are independently rerun by the established native Actions publisher. Its branch is never merged into application main. It verifies23 attachment bytes before normal expected-head merge and again around immutable publication.

Original failures, incomplete/preliminary method outcomes and limitations remain separate in PRIOR_ATTEMPTS.md and the prior archive. The first14-test run had one equivalent-UTC-spelling assertion failure; the later source-instant control preserved all counts/directions. The first external helper lacked its import path. An invalid merge-helper draft was caught by compile before execution, and its original source survives while the interactive error console was not independently retained. No unarchived uncommitted source is reconstructed as original. Scratch recovery retained the8GiB prerequisite and removed only digest-matched immutable successful download copies or clean tracked working copies, preserving original failed evidence and source refs.

## Production and independent acceptance

Public readiness verified baseline2240 and its exact commit. This session's browser connector is disconnected and no Render Shell executor is attached. The unchanged external401 was not retried, and no new credential/relay or authentication path was created. Authenticated live franchise acceptance remains unverified. Post-release public readiness, assets and authentication-boundary smoke receipts remain separate from private history inspection.

No cold production entry, provider backfill, forced sync, FOIS rebuild, Trade search, cache clear, restart, infrastructure change or saved-user-data mutation was performed. Follow SCOUT_HANDOFF.md for one optional existing-warm authenticated history read and stop on resource deferral. This release does not establish Granite recovery, more infrastructure capacity, present manager motivation or acceptance likelihood.
