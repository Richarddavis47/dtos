# Contextual Back — build 2210

## Existing navigation and correction

Build 2209 used ordinary multipage links plus isolated return links. Its Market dossier links already carried search context in some flows; Trade already retained exact drafts under a session/league/franchise/tab binding. Fixed parent links could not express League → My Team or Trade → Market → dossier → Market → Trade. My Team's hidden shared header required placing Back in its visible franchise heading. Player projection week navigation replaced the entire history state, losing unrelated entry identity. Departing Trade did not preserve all temporary filters and cancellation state.

| Surface | Existing contract | Added behavior |
| --- | --- | --- |
| Home / Brief | Five primary destinations; explicit discovery | Back beside page title when a meaningful preceding page exists; no discovery |
| My Team / Roster / Depth / Capital | One page with named anchor shortcuts; shared header hidden | One visible Back in franchise heading; explicit section anchors count, ordinary disclosures do not |
| League / standings / matchups | Real submitted lineup and official standings remain independent | Shared Back preserves preceding route and known week/query context |
| History / FOIS / franchise | Existing guarded preparation and parent links | Shared contextual return, safe League fallback; no historical work added |
| Market / search | Server-side query/filter/selection URLs | Preserve exact supported search URL and browser entry scroll/focus |
| Player dossiers | Specific supported origin links; projection week replaces URL | Contextual chain takes priority; validated specific origin or Market fallback; week replacement preserves other history state |
| Trade / Generate / Evaluate / Builder / Trade For / Shop | Existing exact draft, preview and revision/source safeguards | Contextual return restores draft and bounded temporary filters; retained evaluations remain not revalidated; departure cancels pending work |
| My DTOS | Saved server rankings; local editor filters | Restore search/position/page in native entry state after fresh authorized read; no ranking writes |
| Account / league selection / recovery pages | Independent authenticated account shell | Same Back and context identity; sign-in/create/recover/Welcome excluded |
| Market warming / league recovery HTML | Existing safe recovery and retry controls | Back remains available without acquiring another runtime; API error contracts unchanged |

## State and authorization

Native browser history is the traversal authority. A single tab-local sessionStorage ledger records at most 32 relative destinations and 64 KiB UTF-8, expiring after two hours. It stores bounded scroll and focus identifiers, not packages, prices, ranking rows or credentials. The scope is the unchanged existing Trade workspace binding over authenticated account, session, selected league and controlled franchise. The existing tab marker distinguishes tabs. Browser entry identity merges into existing history state rather than replacing it.

Only allowlisted same-origin routes/query keys and explicit My Team section anchors are recorded. External referrers, action/refresh URLs and credential parameters are not replayed. Duplicate destinations and redirects are skipped; replacement navigation remains replacement navigation, preventing parent/dossier loops. Direct entry has a safe relevant parent fallback. Browser storage failure is explained and does not pretend work was saved.

GET /api/account/navigation-context returns only the opaque binding and controlled My Team path. Existing middleware authenticates it without runtime acquisition; responses are private/no-store. It is not an authorization grant. Back validates current scope before traversal. Account/league/franchise changes and expired/revoked sessions clear old navigation and invalidate Trade state. A transient verification failure retains the page and offers retry/reload instead of claiming authorization failed. Delayed checks are aborted and cannot override later navigation. Cached pages are suspended until fresh context verification before reuse. Every destination retains its existing server authorization; client state cannot grant access.

## Trade restoration versus fresh entry

Contextual Back reuses the existing bounded Trade draft and native entry snapshot. It preserves exact sent/received packages and picks, counterparty, strategy, Neutral/Custom mode, targets/protections, preview/original/adopted state and supported temporary filters. It does not create a second recommendation cache. Temporary filter metadata is bounded. Existing workspace ownership, source and preference revision checks still run. Previously computed assessments are retained/not revalidated; no evaluation or discovery runs automatically.

Leaving cancels pending operations and invalidates late results. The returned page explains that an interrupted operation stopped. Explicit Build My Own handoff remains authoritative and is not overwritten by departure snapshots. A foreign history binding cannot resurrect a cleared draft.

Deliberate entry using the primary Trade destination still starts a fresh session according to established policy. It is distinguishable from Back. The existing Home boundary remains a deliberate end to the Trade session; this change does not promise indefinite draft restoration through unrelated visits. Start New/reset uses replacement bookkeeping without losing native history identity.

## Verification and limitations

Tests use disposable AccountStore → authorized ASGI HTTP → real loopback HTTP redirects → controlled Chromium. The prepared Market adapter uses the same fixture prices as Trade and avoids a cold source factory. This is not live source completeness or physical iPhone/Safari testing. Mutable journeys never touch production preferences or trades.

Controls cover League → My Team → Depth → Back; Market query → dossier → Back; Custom exact-pick Trade → Market → dossier → Back chain at four widths; Neutral return versus deliberate tab reset; pending cancellation; preview/Keep/Adopt/Adjust; stale source assessments; native Back/Forward, refresh, direct links and redirect loops; account/league changes and revoked sessions; delayed scope checks; disabled storage; bounded ledger and safe URL handling; My DTOS view restoration without writes. BF-cache transition controls are simulated PageTransitionEvents in Chromium, not a claim of physical browser lifecycle acceptance.

A dedicated prepared read test guards provider synchronization, projection preparation, history, FOIS and discovery factories and counts existing solver aliases. The context check adds one bounded authenticated request when Back or cached-page restoration requires validation. Normal navigation retains existing destination preparation behavior; Back introduces no new analytical factory. Full hosted regression, the canonical ten gates and lifecycle resource controls remain release requirements.

No calculation, trade threshold, price, projection, exact identity, historical grade, saved preference, public welcome or registration policy changes are authorized by this batch. Production memory headroom and broad latency clearance are not inferred from fixture success. Existing 2 GiB/500 ms protections remain unchanged.
