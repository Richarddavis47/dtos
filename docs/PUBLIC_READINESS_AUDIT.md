# Public-readiness audit and narrow corrections

Baseline: v1.21.58/build 2158, `8c2d6e26a3f1873d1baccce977a9ec20697dee36`. Remote main and `/health/ready` matched before implementation; no overlapping feature PR was open. The user-supplied October 15 decisions, accepted repository contracts and supplied Scout findings govern this audit. A separate private Blueprint or full independent Scout artifact was not present in the repository; reading one is not claimed.

## Before-change inventory and evidence

| Journey / shared boundary | Existing behavior | Audit decision |
|---|---|---|
| Anonymous entry → account → sign in/create | Account middleware, opaque sessions, CSRF and authorized membership; no league guessed | Preserve authentication/authorization; isolated new-user and separate-account controls |
| Connect Sleeper | Actual AccountService HTTP client raises `httpx.HTTPError`; route only catches invalid identity / duplicate link | P2: timeout produces HTTP 500, no useful recovery. Reproduced real client → authenticated POST and Chromium |
| Discovered league → Add | Discovery and membership source calls are outside a source-failure boundary | P2: timeout in either stage gives HTTP 500. Preserve exact membership admission and prior active scope |
| Manual import / discovery error | Invalid ID and outage conflated; errors have no retry destination | P3: distinguish invalid input from temporary source failure; useful local retry, no provider retry loop |
| Sign in → recovery | Recovery route works but is not linked from sign in | P3: expose existing recovery, do not change authentication policy |
| Home → My Team / Trade | Compact identity, news vs hypothetical opportunities; explicit bounded discovery | Preserve; responsive first-use, two-league and no-hidden-search tests |
| Roster / HQ / League | Existing legal-lineup/source qualifications, own/opponent context and exact picks | Preserve; existing producer/HTTP/phone/tenure tests |
| Trade → Preview/Keep/Adopt/Adjust/Balance/Reset | Shared evaluator, target-preserving Balance, tab-local bounded drafts | Preserve; actual canonical publisher/evaluator/released-client journeys |
| Fresh incomplete → previous assessment | Previous counterparty absolute totals and package replacement text already saved, not shown | P3: additive assertions fail at all four widths; display saved evidence only in prior-attributed disclosure |
| Market/dossiers/standings/matchups/reports/settings/commissioner/history | Existing shared routes and source contracts | Audit current routes and existing regression/browser suites; no decorative redesign |

Reproduction artifacts are under `.validation/v159-public-readiness/`. The first fixture run exposed a test-only `self.fail` collision; corrected naming and same-origin TestClient reproduce the application failures without changing application code. Before-change failures are retained separately. Existing assertions are preserved and new prior-evidence assertions are additive.

## Narrow implementation boundary

Reuse account shell and actual source/client contracts. Catch known upstream HTTP failures at account actions; distinguish bad input from temporary failure, retain prior account/league authority, and provide a same-origin recovery action. Never suppress unrelated programming exceptions or grant guessed membership. Reuse already-bounded retained diagnostics to show absolute lineup evidence and the existing complete package explanation; no additional stored fields, calculations or requests.

No new engine, database/table, archive, snapshot, polling, permanent account fixture or paid infrastructure. New-account provisioning is isolated and disposable; live accounts/drafts/strategies are not modified. Existing roster/projection/Market/FOIS math and source identity remain unchanged. Responsive Chromium is author-run, not physical Safari or Scout-independent acceptance.

## Confirmed additional controls and corrections

- Failed runtime preparation reproduced HTTP 500 and a prematurely saved membership. Source preparation now completes before the existing membership/series writes; known HTTP/runtime failures preserve the previously active league and allow retry. No new transaction/table/store is introduced.
- 320px account input extended to x316 outside a card ending at x307; 72px content-box fields also pushed actions downward. Apply border-box within the account shell and readable 16px controls. No site-wide layout redesign.
- Native pending form submission lacked visible in-page status. Add accessible Connecting/Preparing feedback, duplicate-submit protection and pageshow recovery without persistence or polling. The browser fixture uses a real local HTTP server; intercepted redirect requests are not used as evidence of successful navigation.
- Live Market returned one transient 503 followed by a normal 200. The shared warming middleware demonstrably emits raw JSON for browser navigation. Preserve default JSON/API/HEAD contracts and add HTML only for a browser requesting `/market`; same Retry-After and background admission, escaped same-origin retry URL, Home/My Team recovery. No blind automatic retries. A route-level warming race uses the same presentation.
- The existing retained `counterparty_summary` contains the complete package replacement explanation, while `strategic_fit` horizons retain absolute totals; deep roster diagnostics may be omitted by the existing bounded budget. Render only these already-saved facts. Retention schema/budgets/functions remain unchanged; no reconstruction of missing solver details.

## Validation and readiness boundaries

All existing mandatory gates remain required. New actual-source HTTP controls use disposable normal accounts and the real AccountService with a deterministic HTTP transport for Sleeper, not production account provisioning. Authenticated live browsing uses normal authorized sign-in and read-only routes; production user drafts, strategy and league-selection settings are not modified. Live Day/Arkham source inspections remain separate from isolated A→B→A accounts/strategies and source-failure fixtures.

Physical iPhone/Safari and a true external new manager's comprehension are separate acceptance gaps. No claim of universal public readiness or Scout-independent execution follows solely from green tests. Final measured outcomes, exact source/CI/deployment identity and a qualified readiness verdict are recorded in the release handoff.

Browser authentication throttling also reproduced a bare JSON status with no wait instruction. HTML form requests now receive the existing wait period and return action; default JSON, HTTP 429, Retry-After, attempt counters and all security policy remain unchanged. Failed switching of an already-connected league reproduced the same preparation-ordering defect: both HTML and API paths now prepare an already-authorized current-series membership before changing active intent. The existing store rechecks authority when activation commits.
