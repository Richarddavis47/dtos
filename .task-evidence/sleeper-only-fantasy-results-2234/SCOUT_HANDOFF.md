# Independent acceptance: Sleeper fantasy results, build 2234

Source candidate: `c5fa998ab7df024a3ac543e5a191447e92d3c889`; tree: `6ca249dddd6c798b56e1d2a067c63afa9b759a4f`. Baseline: v1.22.18/build2233, `38f23ecc607d38d986af5c1c20ae57fffeb8f827`. Consult the final publication certificate for the merged/deployed commit, immutable v1.22.19 tag and verified attachment checksums. This handoff is acceptance guidance, not independent Scout approval.

## Verify the release and original evidence first

1. Verify PR323, the immutable release target and production `/health/ready` agree on v1.22.19/build2234. The merged application tree must equal the candidate tree above. Publishing/evidence branches are separate; their tooling and documentary trees are not the application tree.
2. Verify SHA256SUMS and every canonical artifact manifest entry. Check both original local and hosted full-console success, matching start/stop test events, zero failures/errors/skips and all ten gate completions. Read earlier failed/cancelled attempts separately; do not add their counts to final acceptance. Readable console chunks concatenate byte-for-byte to the original console hashes.
3. Check the twelve mandatory hosted jobs against this exact candidate. Inspect real2GiB/no-swap container and cleanup evidence, including healthy Trade execution, unsafe-pressure deferral, recovery, actual cancellation/timeout and FOIS/Sleeper protections. A deferred worker is not a completed worker.

## Bounded source and customer verification

Use the owner's already-authorized signed-in account and an already warm, compatible selected league where safely available. Do not force league hydration, synchronization, FOIS work, Trade discovery, cache clearing, service restart, settings changes or ranking/method changes. Do not request/export inspection credentials. If the authorized session or a safe prepared runtime is unavailable, mark authenticated acceptance HELD and retain fixture/source verification separately.

- Read the selected player's dossier and existing Market API/detail. Confirm the actual-result authority is `sleeper-matchup-actuals-v1`, source is Sleeper, and league, season, week, scoring fingerprint and admitted source generation agree. NFLverse usage/reference analysis must remain separately labeled and cannot fill missing fantasy results.
- Compare one supported completed week's individual score with the existing authorized native Sleeper league matchup response: the exact player-map and ordered starter values must agree, or DTOS must withhold the conflicting result. Preserve source precision in the API; display uses the established two-decimal Sleeper web convention. Team custom-point adjustments are not individual points.
- A bounded native-source observation retained with this task found Granite, season2026/week8/player4984 at26.56 in both fields. Its retrieval timestamp and response hashes are in `native-sleeper-selected-score.json`. This is a fresh public native-source observation plus an exact-code frozen-slice/component replay, **not** an owner-authenticated DTOS route observation, a complete season capture, or a claim that an older183.82 total is correct. A later source correction may legitimately differ; pin each comparison's context and observation time.
- Confirm windows explicitly describe completed-week **score observations**, observed totals and coverage. Unknown participation must not become games played or PPG. Live/unconfirmed/future placeholder weeks cannot enter completed windows. Byes, DNPs, absent free agents and taxi/IR membership do not invent a score. Explicit zero/negative values remain numeric.
- Inspect known source gaps and retained/last-valid qualifiers. Batch observation boundaries are not exact HTTP receipt or provider-publication timestamps; unretained receipt times stay unknown. Current compatible scores remain usable, while an explicit point-in-time request requires the relevant known receipt evidence.
- Confirm supported values survive a normal admitted cached-runtime restoration and that old cached NFLverse result disclosures do not reappear. Do this with disposable fixtures unless it is already observable read-only; do not force a production reload/sync to manufacture the condition.
- Review public historical result summaries: games-played/PPG stay unset without participation evidence, observation counts and partial subtotals are explicit, incomplete averages are withheld, and non-Sleeper derived records cannot fill actual scores. Retained historical/FOIS grades remain RETAINED / NOT REVALIDATED.

## Focused independent fixture controls

In an approved disposable Python3.14 environment with an actually enforced2GiB/no-swap limit and existing dependencies, run `python -m unittest -v tests.test_sleeper_actual_results tests.test_current_production_coverage tests.test_current_production_browser tests.test_historical_retained_admission tests.test_historical_snapshot_integrity tests.test_trade_decision_experience` on the exact candidate. No new production data acquisition is needed. Follow repository resource isolation; do not bypass admission or treat deferral as execution.

Review the controls for zero, negative, null/invalid, contradictory fields, duplicate ownership, starter/bench/IR/taxi/unrostered boundaries, league/season/scoring isolation, completion/live/corrections, source failure/last-valid recovery, unknown clocks and explicit point-in-time boundaries. Expected individual scores come directly from retained fixture source values, not fantasy scoring reconstructed by the new implementation. The one-QB/K/DEF and Superflex controls use their own source contexts. Neutral/Custom prices, exact picks, projection/optimizer policy and bilateral verdicts remain independent.

Check320×432,375×667,390×844 and desktop, including keyboard focus, disclosures, touch emulation and no page overflow. Expand weekly evidence without a new request or preparation. Chromium touch emulation is not physical iPhone/Safari or comprehensive assistive-technology acceptance.

## Limits

Matchup retention does not cover every NFL player or establish games played/full-season acquisition. Prior-season actuals need their own admitted Sleeper league-season evidence. Unknown/incompatible source contexts and score conflicts remain withheld; no NF fallback fills them. Existing2GiB capacity/admission limits can still defer cold restoration or heavy work. Controlled cleanup does not prove long-term leak freedom. No live owner Trade search or saved preference/ranking/lineup mutation was performed.
