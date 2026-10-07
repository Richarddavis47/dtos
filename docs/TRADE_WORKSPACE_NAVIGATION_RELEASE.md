# Trade workspace identity and navigation — v1.21.15 / build 2115

## Demonstrated root cause and security classification

Current main was reconciled at d7b56fec3129aae45c14a719aa3b9f1311b7e887
(v1.21.14). Two independent boundaries used `workspace_context_changed`:

- `authorize_workspace` validates the authenticated session binding, selected
  membership league, controlled franchise and schema before evaluator entry.
- Five search/repair/comparison completion guards discard results if canonical
  league/Market/projection evidence changed during computation.

The browser mapped either rejection to “This workspace belongs to a different
account, league or franchise. Reload before evaluating.” That is not a truthful
classification of an evidence publication. A deterministic real authenticated
Trade For request with a Market generation publication during its first candidate
assessment produced HTTP 422 and that code. Its authenticated workspace binding
was exactly unchanged. The identical request then returned three valid offers.

This is demonstrated classification F: conflated evidence-generation and identity
failures. It does not prove which publication occurred in Scout's live session;
no authenticated live trace of that event is available. No cross-account exposure,
authorization bypass or tenant isolation defect was demonstrated in the audit or
fixtures. This release does not suppress a real identity warning.

## Authoritative identity and state trace

The session cookie resolves AccountStore's account/session/CSRF and active league
membership. AccountContextMiddleware validates CSRF, rejects unauthorized league
paths and overrides private-route league/front-office query values from that
membership. LeagueContextMiddleware resolves the corresponding request-scoped
runtime. ContextVars propagate through `asyncio.to_thread` (`run_manager_read`);
no singleton account or default-league swap is involved.

HTML workspace account/franchise context originates from this server resolution;
URL target/owner values are not authentication. The player ownership boundary
resolves the actual Trade For owner. `/api/trades/workspace` supplies the current
session/account/league/franchise binding, ownership generation, assets and CSRF.
The browser's sessionStorage key is that binding, not a manager name or roster ID.
Only proposal/preview/adoption/locks/strategy/anchors are restored from it; stored
state does not become authoritative authentication. A changed binding clears the
preceding temporary workspace according to the existing single-workspace policy.

Every POST supplies the server-issued binding and controlled franchise. The
backend revalidates them and current ownership. Current/adopted proposals retain
precedence over URL defaults; Build My Own explicitly clears the prior proposal
and target anchors while preserving exact protections. Full navigation initializes
from the server again. Browser back/forward tests use full navigation; a separate
pagehide fixture exercises the BF-cache lifecycle (route interception disables
native BF-cache in the browser test transport).

## Correction

Canonical completion guards now return `canonical_evidence_changed`. Genuine
workspace/session/franchise/league errors retain their original codes and checks.
No data inputs, calculations, source freshness policy, lineup math, candidate
budgets, ranking or authorization rules change.

The browser freezes the outgoing proposal/binding/strategy/target/locks. Only the
new evidence-refresh error permits one retry with that identical payload, and
only while the captured intent revision remains current. A second refresh stops
with truthful feedback and enabled retry controls; it cannot loop. An identity
error never retries, refreshes a binding or reinterprets an old proposal under a
new session. The recovery link opens `/trades` through normal authentication.

Page departure invalidates pending results and run ownership, clears an obsolete
loading state and makes a restored workspace usable. Completion of old work
cannot replace a newer result or enable controls while a newer run is pending.
No distributed cancellation or new persistent state/cache is introduced.

## Deterministic acceptance and regression coverage

- `tests.test_trade_navigation_identity`: real mid-search publication, unchanged
  identity, mixed-generation discard, same-binding three-offer retry, all five
  evidence guards, real middleware/CSRF isolation with colliding IDs and concurrent
  requests, legitimate league activation, same-league different-account and
  same-account different-session rejection before engine entry.
- `tests.test_trade_navigation_browser`: actual Cheaper API and dossier route,
  Daniels/McBride adoption/reload → Build My Own → dossier → Trade For, target
  owner, unchanged exact locks and request identity, back/forward/deep-link/reload,
  one-retry limit, actionable identity rejection, strategy/navigation changes
  during original and retry requests, new-run loading-state protection, changed
  binding and isolated browser state. Responsive Chromium: 320/375/390px.
- Existing canonical asset facts, ownership/free-agent, exact picks, Market/strategy
  invariance, discovery/performance/diversity, Shop/Trade For, Make It Cheaper,
  preview/Keep Original/adoption, multi-asset reload, technical identifiers and
  evidence-table tests remain unchanged and in release coverage.
- No additional per-navigation identity/provider/ownership query is introduced.
  Stable requests keep one POST. A genuine evidence publication may cost one
  extra evaluation/search; this is bounded and visible, not a latency SLA.

Required release validation remains the canonical ten-gate validator (including
full regression, Ruff, compilation, diff checks, route/OpenAPI, tracked HTTP and
cleanup), browser/identity/isolation regressions, ordinary/archive-warmed/combined
cgroups at unchanged 2 GiB limits, recovery/quiescence and all GitHub CI jobs.
Production acceptance is read-only and must report authenticated access limits.

## Independent Scout live handoff

On the deployed v1.21.15 / build 2115, adopt the Daniels/McBride Cheaper offer →
Build My Own → McBride dossier → Trade For without reloading. Check correct
account, league, franchise, McBride's real owner and returned packages. If canonical
evidence publishes during search, one bounded refresh retry is appropriate; a
false “different account” warning is not. Continuing publications must produce
an honest refresh explanation with usable controls.

Repeat with a pending search, back/forward, deep link and reload. Confirm valid
adopted multi-asset proposals, exact protections and required targets survive the
appropriate transitions. A real mismatch must remain blocked and offer current
Trade Center recovery; do not cross account boundaries or submit trades.

Smoke Recommended/Next Five timing/diversity, Shop, opponent-owned Trade For,
Cheaper, exact locks, preview/Keep Original/Adopt, free-agent actions and canonical
prices. Check feedback and actions at 320/375/390 responsive Chromium. Label that
separately from physical iPhone/Safari, which is not claimed here.

Keep cold Recommended timing (~24 seconds previously), Next Five loading feedback
below the visible viewport and physical-device coverage separate. Do not expand
this release into those workstreams.
