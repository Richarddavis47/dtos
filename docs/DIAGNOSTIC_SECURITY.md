# Diagnostic authorization and public probes

Legacy `/api/inspect` is a **private, read-only** semantic interface. It accepts an
active account session in its authorized league or the existing inspection-token
context with a complete configured league/franchise scope. It is protected even
when optional development authentication is disabled. A router dependency also
fails closed if the router is mounted without the account boundary.

An ordinary member may inspect league-scoped collections and its own franchise
team/front-office details, but cannot select a foreign league or inspect another
member's franchise-specific diagnostic record. This does not restrict existing
in-league product pages. Privileged inspection may inspect league franchises
within its configured authorized league. A valid operator header determines that
scope even if an unrelated session cookie accompanies it. No new credential,
admin role, relay, session or account-registration mechanism is added.

Explicit conflicting league query parameters, including duplicates, fail with a
generic 403 before runtime acquisition. The router verifies authorized league,
selected runtime and actual source league agree before reading facts. An absent
or mismatched source returns generic 503 without the default league payload.

Protected successes and errors use `Cache-Control: no-store, private` and vary
on Cookie and inspection authorization. `/api/inspect/operations` retains its
existing separate GET-only, exact opaque-token and parameter boundary. A user
session cannot authorize operations inspection.

## Public allowlist

- `/health/live`: status and version; HTTP 200 independently of data readiness.
- `/health`, `/health/ready`: status, version/build/deployment identity; HTTP
  200 when ready and 503 otherwise. Readiness reason is public-safe fixed text.
- `/api/status`: status and version/build/deployment identity; HTTP 200.

Trailing-slash redirects preserve the same safe responses. These routes do not
acquire league runtimes or query historical progress. They do not return league
IDs, roster/owner/pick counts, raw cached errors, source paths, worker/memory
metrics, history progress or provider failure payloads. Existing Render liveness
and readiness paths and status semantics are unchanged.

Detailed platform/data health and `/api/inspect/health` expose shared operational state. They require the existing inspection credential with configured scope; an ordinary member session is insufficient, including when development authentication is optional. Market health remains available in its authorized league context. Existing authenticated resource tools and CSRF-protected measurement remain available. Runtime inventory keeps harmless aggregate counters but filters runtime rows, source errors and active league identities to the member’s authorized league; the existing operator context retains its shared inventory. Authorized monitoring sends the
existing inspection credential and configured scope. `/api/inspect/health`
continues to provide operator-authorized resource/history diagnostics. API account health
only returns safe schema/storage-kind status; account context/list handlers keep
their existing session checks.

Validation smoke uses the same authenticated contract. Only the isolated,
non-Render loopback validation worker may provision an ephemeral *test* value
for that existing variable when none was supplied; caller-provided credentials
are untouched and restored after server cleanup. Nothing provisions production
credentials.

The public welcome candidate remains isolated and unreleased. This security
release does not authorize public promotion or beta expansion. No real private
production league records are retrieved to prove the defect or its correction.

Related legacy search, weekly-report and manual-sync handlers use the same existing private HTML policy as their corresponding private APIs. Anonymous requests redirect to sign-in before data access or sync work; authorized mutations still require CSRF. Retired static inspection files have no registered static-directory mount or download handler and are not republished. Robots and sitemap contain fixed route URLs only.

The standalone Linux identity cgroup gate uses a caller-supplied complete existing inspection context for its private Market-health read. Missing credentials fail clearly; it does not create a production credential or silently exempt the route.


## Handled runtime failures

League acquisition (default and secondary contexts) and explicit runtime validation/hydration never use exception text as a public reason. HTTP 422 returns `league_runtime_not_found`; HTTP 503 returns `league_runtime_unavailable`. Responses keep their invalid/failed status and useful retry/connected-league recovery. The existing outer diagnostic 500 remains `diagnostic_unavailable`.

API and HTML failures use private/no-store headers. Request IDs remain on the existing observability boundary. Bounded `league_runtime_failure` server records contain type, operation, correlation and at most six file/function/line locations, without exception messages, chained messages, locals, request credentials, paths or source IDs. Detailed retained operational state continues through its existing protected inspection contract. Member runtime health displays an unavailable explanation instead of a cached raw exception, without changing shared state or operator evidence.
