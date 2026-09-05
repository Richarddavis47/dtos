# Account / league / franchise isolation — v1.13.1

## Boundaries

| Data or cache | Scope | Boundary |
| --- | --- | --- |
| Account, membership list | Account | AccountStore account ID; normalized membership rows |
| Session, CSRF, account chrome | Session | Current AccountContext; never shared rendered bytes |
| Sleeper normalized data and runtime | League | RuntimeStateProxy / CanonicalLeagueContext |
| Home evidence fragment | League + franchise + generation | Retained generation and selected roster |
| Market evidence fragments | League + generation + franchise + query | Selected canonical runtime, bounded caches |
| FOIS leaderboard fragment | League + model + generation | Repository league query and render key |
| FOIS profile / behavior / bilateral evidence | League + franchise | Canonical league identity; wrong rows rejected |
| Brain / decision / Team HQ / trade intelligence | League + franchise + source snapshot | Explicit canonical data; intelligence snapshot key |
| Valuation freshness | League | Active runtime state, not configured singleton |
| Player dossiers | League + franchise | Active canonical data and selected manager context |
| NFL identity, approved market observations | Global | Shared public evidence; no per-league market-history copy |
| Historical season contexts | League series + season | Canonical continuation identities, not display names |

AccountContextMiddleware derives trusted league and roster from the authenticated
membership; caller query strings cannot override them. LeagueContextMiddleware
uses a ContextVar, not a mutable process-global selection. Sleeper synchronization
passes the selected league ID to league/users/rosters/picks/drafts/matchups and
transaction endpoints. Warm switching reuses retained state; cold hydration is
bounded by the existing runtime manager. No additional provider calls are added
by this correction.

## Defects and corrections

1. Market cached `page()` output, including another request's account identity,
   membership controls, and CSRF fields. Keep existing body caches; compose chrome
   outside shared cache lookup on every request.
2. FOIS had the same full-response caching boundary. Cache only leaderboard body;
   render account chrome after lookup.
3. Valuation's app registration passed default STATE while its data was active-
   league scoped. Pass the existing RuntimeStateProxy so synchronization freshness
   and calibration observe the same league as the data.
4. The new registration test assumed flat FastAPI routes. Installed FastAPI uses
   included-router containers. Discover recursively and assert the public GET
   endpoint exists before checking the actual dependency.
5. FOIS warming could select the only persisted league when data was unavailable.
   Authenticated membership now supplies the selected league even during warming;
   another league's sole persisted profile cannot become fallback evidence.
6. Player dossiers used a hardcoded Day Traders career-history label. The label
   now comes from the selected league and remains HTML-escaped. Production also
   demonstrated that secondary runtimes did not hydrate their Sleeper season
   chain. Cold authorized runtime hydration now schedules the same bounded,
   league-keyed disposable-cache worker used by default startup. It does not
   restore HistoricalStore or substitute another league's events. Archive work
   and lifecycle admission run off the request event loop. Reopening a cold
   runtime retries unavailable/evicted caches; warm requests do not fetch facts.
7. A deterministic runtime-close probe showed the history adapter still retained
   the exact secondary data object after runtime eviction. Context close now
   releases only that matching operational reference. A stale close cannot
   remove a newer runtime, other leagues remain intact, and disposable season
   facts/checkpoints are untouched. A 500-runtime close regression proves the
   adapter does not accumulate those closed operational contexts.
8. Periodic synchronization and startup historical market resolution were still
   default-only. Resident secondary runtimes now own one maintenance loop at the
   existing interval; inactive memberships create none. History resolution takes
   explicit runtime state/Market/league identity. Eviction awaits current writers,
   then releases the operational context. Existing resource admission serializes
   heavy work and all requests remain provider-free.

## Regression proof

- Inspection-first, independent-account, and renewed-session rendering preserve
  identical evidence but never reuse account/session chrome.
- Two real account contexts, three leagues, identical names, player IDs and roster
  IDs pass authenticated middleware, repeated A2/A1 switching and concurrent A/B
  requests. Hostile query league and roster IDs cannot override membership.
- All 500 stored memberships are activated and mapped correctly without runtime
  hydration; 500 six-season continuing series remain 500 front offices.
- Prior v1.13.0 tests retain fail-closed wrong-league evidence handling and global
  trend reuse, plus direct/switch and concurrent intelligence equivalence.

## Production audit status

Before deployment, authenticated v1.13.0 observations confirmed correct active-
league headers on Home, Team HQ, League/rankings, matchups, history, transactions,
picks, Market, calibration, settings and trade entries across A/B. Actual roster,
owner options and history availability differed by league. FOIS reproduced the
known Inspection chrome contamination. Player expansion/dossier retained the
active league. These observations are diagnosis, not acceptance of v1.13.1.

Full candidate validation, Linux lifecycle and post-deployment acceptance remain
required. No claim of universal empirical coverage is made: deterministic tests
prove identity invariants, while production checks exercise authorized accounts.
