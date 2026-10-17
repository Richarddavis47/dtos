# Public launch audit: cold league source recovery

Baseline: v1.21.60/build2160, `4a21fefcad98154ac0c4385785ac1c0835acb257`. Main and production matched before implementation. Prior unchanged-source audit evidence is retained in `.validation/public-launch-2160/`; this follow-up preserves its physical-device and unfamiliar-human acceptance limits.

## Verified failure and narrow correction

The real Sleeper sync producer catches an upstream failure and correctly retains the last valid data. On a cold selected league there are no such facts. The canonical hydrator nevertheless continued into FOIS with empty data, returning HTTP500. A normal authenticated Home reproduction with a controlled upstream404 proved this; timeout/null-source and recovery-route controls reproduced it too. Account logical records stayed unchanged. Account, health and static requests also unnecessarily entered the selected-league hydration path, obstructing recovery and lightweight liveness.

Require nonempty supported data after the existing source sync and before restore/FOIS/context publication. Reuse the existing retryable LeagueRuntimeError contract. Retained valid data continues through the accepted path; numerical evidence, source freshness and projections are unchanged. Unrelated programming exceptions are not broadly suppressed.

Account/control, exact liveness/readiness and static routes do not consume canonical league facts. Keep their existing outer authentication, session, CSRF and account-revision checks; account actions still explicitly prepare their intended authorized league before committing user intent. Consumer routes retain their existing account/league admission. No source, valuation or account-authority policy is relaxed.

For browser navigation, show a compact source-unavailable page with the saved league name, preserved-account explanation, same-origin retry, Your account and Choose a connected league actions. API/default JSON status/reason semantics remain, with no-store responses. No automatic retry or background work is added.

An actual discovery-outage control also showed that Your leagues hid existing authorized connections behind another source-failure page. When discovery fails and active saved connections exist, render only those existing records, explicitly marked saved/not refreshed, without fabricated team counts. Their activation still runs existing preparation and authorization. With no saved connection, preserve the existing503 guidance. No membership or preference is created or modified by fallback rendering.

## Acceptance and preservation

Actual producer→runtime→normal-account middleware→Home/API tests cover404, timeout, null source, later retry, retained facts, source-independent account/health/static controls, CSRF, switching to a prepared existing league, discovery outage and unrelated exceptions. Native browser controls cover320×432/375×667/390×844/desktop, visible focus, readable44px actions, no document overflow and keyboard recovery. Source failures and storage tests use disposable state only.

Existing atomic imports, exact picks, Trade/Balance/Preview/Adopt/reset, original prior-assessment totals/reasoning, Market/projection parity, legal lineups, Dynamic Needs/GM/history and retained FOIS contracts are unchanged. No new schema, permanent data, archive, cache or paid service. Existing2GiB/500ms requirements and all release gates remain mandatory.

Automated Chromium/WebKit results are author-operated. Physical iPhone/Safari and genuine unfamiliar-user comprehension remain separate, unperformed acceptance items unless independently supplied.

## Lifecycle correction discovered during release validation

The first ordinary hosted lifecycle failed at server shutdown: the existing15-second graceful bound escalated to SIGKILL. Original artifacts show zero OOM counters and a1.343GB effective memory peak. The log identifies cancellation at the scratch-database preparation thread followed by directory-not-empty cleanup; a deterministic barrier control confirms that cancellation previously removed the directory before its writer stopped.

Shield and drain that existing bounded scratch preparation before cleanup, then propagate cancellation. No new worker, timeout increase, published-score recalculation or storage contract. Existing spawned-compute cancellation/reaping and score-equivalence controls remain. The full FOIS process regression module now runs in ordinary lifecycle CI. Superseded validation evidence remains preserved; all canonical and hosted gates must pass again on the corrected commit.
